"""Core git synchronisation engine.

All git access goes through a single re-entrant lock so the file watcher
(push), the scheduler (pull) and the web UI (manual actions) never run git
commands concurrently against the same working tree.
"""
import datetime
import logging
import os
import shlex
import subprocess
import threading

log = logging.getLogger("git")

SSH_DIR = "/data"
KNOWN_HOSTS_FILE = "/data/known_hosts"
PROVIDED_KEY_FILE = "/data/id_provided"   # a key pasted into the options
MANAGED_KEY_FILE = "/data/id_gitsync"     # a key generated/managed by the app
GITIGNORE_HEADER = "# === Managed by the Git Sync app — do not edit this block ==="
GITIGNORE_FOOTER = "# === End of Git Sync managed block ==="


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


class GitSync:
    def __init__(self, cfg):
        self.cfg = cfg
        self.repo = cfg.backup_path
        self.lock = threading.RLock()
        self.state = {
            "initialized": False,
            "paused": False,
            "pause_reason": "",
            "branch": cfg.branch,
            "remote": cfg.repository_url,
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "last_pull": None,
            "last_push": None,
            "last_error": None,
            "last_commit": "",
            "busy": "",
            "public_key": "",
            "key_type": "",
            "key_source": "",      # provided | file | generated | none
            "key_fingerprint": "",
        }

    # ------------------------------------------------------------------ #
    # Low level helpers
    # ------------------------------------------------------------------ #
    def _git(self, *args, check=True):
        cmd = ["git", "-C", self.repo, *args]
        log.debug("$ %s", " ".join(shlex.quote(a) for a in cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip():
            log.debug(result.stdout.strip())
        if check and result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError("git %s failed: %s" % (args[0], message))
        return result

    def status(self):
        with self.lock:
            snapshot = dict(self.state)
            snapshot.update(
                {
                    "auto_pull": self.cfg.auto_pull,
                    "auto_push": self.cfg.auto_push,
                    "pull_interval": self.cfg.pull_interval,
                    "push_debounce": self.cfg.push_debounce,
                    "backup_path": self.cfg.backup_path,
                }
            )
            return snapshot

    # ------------------------------------------------------------------ #
    # SSH / git configuration
    # ------------------------------------------------------------------ #
    def prepare_ssh(self):
        """Set up the SSH key (generating one if needed) so the public key is
        available in the panel even before the repository is connected."""
        with self.lock:
            self._setup_ssh()

    def _setup_ssh(self):
        os.makedirs(SSH_DIR, exist_ok=True)
        # Ensure the known_hosts file exists so ssh does not complain.
        open(KNOWN_HOSTS_FILE, "a", encoding="utf-8").close()

        key_path = None
        source = "none"

        key_lines = self.cfg.ssh_key
        if isinstance(key_lines, str):
            key_lines = key_lines.splitlines()
        key_lines = [line for line in (key_lines or []) if line is not None]

        if any(line.strip() for line in key_lines):
            data = "\n".join(line.rstrip() for line in key_lines).strip() + "\n"
            with open(PROVIDED_KEY_FILE, "w", encoding="utf-8") as handle:
                handle.write(data)
            os.chmod(PROVIDED_KEY_FILE, 0o600)
            key_path, source = PROVIDED_KEY_FILE, "provided"
        elif self.cfg.ssh_key_path and os.path.exists(self.cfg.ssh_key_path):
            key_path, source = self.cfg.ssh_key_path, "file"
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
        elif os.path.exists(MANAGED_KEY_FILE):
            key_path, source = MANAGED_KEY_FILE, "generated"
        else:
            # Nothing supplied: generate a managed key so there is a public key
            # to copy into the Git host as a deploy key.
            self._generate_keypair(
                MANAGED_KEY_FILE,
                self.cfg.ssh_key_type,
                self.cfg.ssh_key_comment,
            )
            key_path, source = MANAGED_KEY_FILE, "generated"
            log.info("No SSH key supplied — generated a managed key")

        opts = [
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=%s" % KNOWN_HOSTS_FILE,
            "-o", "IdentitiesOnly=yes",
        ]
        if key_path:
            opts = ["-i", key_path] + opts
        os.environ["GIT_SSH_COMMAND"] = "ssh " + " ".join(shlex.quote(o) for o in opts)

        self.state["key_source"] = source
        self.state["public_key"] = self._public_key(key_path) if key_path else ""
        ktype, fp = self._key_meta(key_path) if key_path else ("", "")
        self.state["key_type"] = ktype
        self.state["key_fingerprint"] = fp
        if key_path:
            log.info("Using SSH key %s (source: %s)", key_path, source)
        else:
            log.warning("No SSH key available; only HTTPS remotes will work")

    def _generate_keypair(self, path, key_type, comment):
        key_type = (key_type or "ed25519").strip().lower()
        if key_type not in ("ed25519", "rsa"):
            key_type = "ed25519"
        comment = (comment or "home-assistant-git-sync").strip()
        for stale in (path, path + ".pub"):
            try:
                os.remove(stale)
            except OSError:
                pass
        cmd = ["ssh-keygen", "-t", key_type, "-C", comment, "-N", "", "-f", path]
        if key_type == "rsa":
            cmd = ["ssh-keygen", "-t", "rsa", "-b", "4096",
                   "-C", comment, "-N", "", "-f", path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "ssh-keygen failed: %s" % (result.stderr.strip() or result.stdout.strip())
            )
        os.chmod(path, 0o600)
        log.info("Generated %s SSH key (%s)", key_type, path)

    def _public_key(self, key_path):
        pub = key_path + ".pub"
        try:
            if os.path.exists(pub):
                with open(pub, "r", encoding="utf-8") as handle:
                    return handle.read().strip()
        except OSError:
            pass
        result = subprocess.run(
            ["ssh-keygen", "-y", "-f", key_path], capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _key_meta(self, key_path):
        target = key_path + ".pub" if os.path.exists(key_path + ".pub") else key_path
        result = subprocess.run(
            ["ssh-keygen", "-l", "-f", target], capture_output=True, text=True
        )
        if result.returncode != 0:
            return ("", "")
        line = result.stdout.strip()      # e.g. "256 SHA256:abc comment (ED25519)"
        tokens = line.split()
        fingerprint = tokens[1] if len(tokens) >= 2 else ""
        ktype = line[line.rfind("(") + 1:-1] if line.endswith(")") and "(" in line else ""
        return (ktype, fingerprint)

    def generate_key(self, key_type=None, comment=None):
        """(Re)generate the managed SSH key and switch to it. Returns the
        public key so it can be copied into the Git host."""
        with self.lock:
            self._generate_keypair(
                MANAGED_KEY_FILE,
                key_type or self.cfg.ssh_key_type,
                comment or self.cfg.ssh_key_comment,
            )
            self._setup_ssh()
            if self.state["key_source"] != "generated":
                log.warning(
                    "A key is configured via options/ssh_key_path, so the "
                    "generated key will not be used until that is removed"
                )
            return self.state["public_key"]

    def _config_repo(self):
        # Mark every directory as safe — the config dir may be owned by a
        # different uid than the container user.
        subprocess.run(
            ["git", "config", "--global", "--replace-all", "safe.directory", "*"],
            capture_output=True, text=True,
        )
        self._git("config", "user.name", self.cfg.commit_author_name)
        self._git("config", "user.email", self.cfg.commit_author_email)
        self._git("config", "commit.gpgsign", "false")
        self._git("config", "pull.rebase", "false")

    def _ensure_remote(self):
        existing = self._git("remote", check=False).stdout.split()
        if "origin" in existing:
            self._git("remote", "set-url", "origin", self.cfg.repository_url)
        else:
            self._git("remote", "add", "origin", self.cfg.repository_url)

    def _remote_branch_exists(self):
        result = self._git(
            "ls-remote", "--heads", "origin", self.cfg.branch, check=False
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    # ------------------------------------------------------------------ #
    # .gitignore generation from include / exclude options
    # ------------------------------------------------------------------ #
    def _gitignore_content(self):
        includes = [p.strip() for p in (self.cfg.include or []) if p and p.strip()]
        excludes = [p.strip() for p in (self.cfg.exclude or []) if p and p.strip()]
        wildcard = {"*", "**", "**/*", ".", "./", "/"}
        whitelist = bool(includes) and not all(p in wildcard for p in includes)

        lines = [GITIGNORE_HEADER, ".git/"]
        if whitelist:
            lines += [
                "# Whitelist mode: only the paths listed under 'include' are tracked.",
                "*",          # ignore everything ...
                "!*/",        # ... but descend into directories ...
                "!.gitignore",  # ... and keep this managed file.
            ]
            for pattern in includes:
                lines.append("!" + pattern.lstrip("/"))
        if excludes:
            lines.append("# Excluded paths (these always win):")
            lines.extend(excludes)
        lines.append(GITIGNORE_FOOTER)
        return "\n".join(lines) + "\n"

    def _write_gitignore(self):
        target = os.path.join(self.repo, ".gitignore")
        desired = self._gitignore_content()
        try:
            with open(target, "r", encoding="utf-8") as handle:
                if handle.read() == desired:
                    return
        except OSError:
            pass
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(desired)
        log.info("Wrote managed .gitignore (%d include / %d exclude rules)",
                 len(self.cfg.include or []), len(self.cfg.exclude or []))

    # ------------------------------------------------------------------ #
    # Status helpers
    # ------------------------------------------------------------------ #
    def _is_protected(self, path):
        for pattern in (self.cfg.keep_remote_files or []):
            pattern = (pattern or "").strip().rstrip("/")
            if not pattern:
                continue
            if path == pattern or path.startswith(pattern + "/"):
                return True
        return False

    def _local_changes(self, ignore_gitignore=False, ignore_protected=False):
        porcelain = self._git("status", "--porcelain", check=False).stdout
        rows = []
        for line in porcelain.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip()
            if ignore_gitignore and path == ".gitignore":
                continue
            if ignore_protected and self._is_protected(path):
                continue
            rows.append(line)
        return rows

    def _remote_has_backup(self):
        """True if the remote branch already holds real backup content (i.e.
        files other than the protected repo-meta files and .gitignore)."""
        result = self._git(
            "ls-tree", "-r", "--name-only",
            "origin/%s" % self.cfg.branch, check=False,
        )
        if result.returncode != 0:
            return False
        for name in result.stdout.splitlines():
            name = name.strip()
            if not name or name == ".gitignore" or self._is_protected(name):
                continue
            return True
        return False

    def _preserve_files(self):
        """Restore protected repo-meta files (README, LICENSE, .github, …) from
        the last commit so the mirror does not delete them on the next push."""
        patterns = [p.strip() for p in (self.cfg.keep_remote_files or []) if p and p.strip()]
        if not patterns:
            return
        if self._git("rev-parse", "--verify", "HEAD", check=False).returncode != 0:
            return  # no commit yet, nothing to restore
        for pattern in patterns:
            self._git("checkout", "HEAD", "--", pattern, check=False)

    def _refresh(self, fetch=False):
        if fetch and self.cfg.repository_url:
            self._git("fetch", "origin", self.cfg.branch, check=False)

        self.state["dirty"] = bool(self._local_changes())

        rev = self._git(
            "rev-list", "--left-right", "--count",
            "origin/%s...HEAD" % self.cfg.branch, check=False,
        )
        if rev.returncode == 0 and rev.stdout.strip():
            try:
                behind, ahead = rev.stdout.split()
                self.state["behind"] = int(behind)
                self.state["ahead"] = int(ahead)
            except ValueError:
                self.state["behind"] = self.state["ahead"] = 0
        else:
            self.state["behind"] = self.state["ahead"] = 0

        last = self._git("log", "-1", "--pretty=%h %s (%cr)", check=False)
        self.state["last_commit"] = last.stdout.strip() if last.returncode == 0 else ""
        self.state["branch"] = self.cfg.branch
        self.state["remote"] = self.cfg.repository_url

    def _pause(self, reason):
        self.state["paused"] = True
        self.state["pause_reason"] = reason
        log.warning("PAUSED — %s", reason)

    def resume(self):
        with self.lock:
            self.state["paused"] = False
            self.state["pause_reason"] = ""
            log.info("Automatic sync resumed")

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #
    def ensure_repo(self):
        with self.lock:
            if not self.cfg.repository_url:
                raise RuntimeError(
                    "No repository_url configured. Set it in the app options."
                )
            os.makedirs(self.repo, exist_ok=True)
            self._setup_ssh()

            is_new = not os.path.isdir(os.path.join(self.repo, ".git"))
            if is_new:
                log.info("Initialising new git repository in %s", self.repo)
                self._git("init")
                self._git("symbolic-ref", "HEAD",
                          "refs/heads/%s" % self.cfg.branch, check=False)

            self._ensure_remote()
            self._config_repo()
            self._write_gitignore()

            if is_new and self._remote_branch_exists():
                # Adopt the existing remote history without touching local files.
                self._git("fetch", "origin", self.cfg.branch)
                self._git("reset", "--mixed", "origin/%s" % self.cfg.branch)
                log.info("Linked working tree to existing remote branch '%s'",
                         self.cfg.branch)
                # Only guard against overwriting a *real* existing backup. A
                # fresh repo that only holds README/LICENSE is safe to adopt.
                diverged = self._local_changes(
                    ignore_gitignore=True, ignore_protected=True
                )
                if self._remote_has_backup() and diverged:
                    self._pause(
                        "Local configuration differs from the existing remote "
                        "backup. Open the Git Sync panel and choose 'Restore from "
                        "remote' (remote wins) or 'Push local' (local wins) to "
                        "continue."
                    )
            elif is_new:
                log.info(
                    "Remote branch '%s' does not exist yet; it will be created "
                    "on the first push", self.cfg.branch,
                )

            self.state["initialized"] = True
            self._refresh(fetch=not is_new)
            log.info("Repository ready (branch '%s', remote '%s')",
                     self.cfg.branch, self.cfg.repository_url)

    def connect(self):
        """Attempt to initialise/connect the repository, surfacing any error to
        the panel instead of crashing (e.g. before the deploy key is added)."""
        try:
            self.ensure_repo()
        except Exception as err:  # noqa: BLE001
            self.state["last_error"] = str(err)
            log.error("Connect failed: %s", err)
            return False
        return True

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    def _commit(self, message=None):
        """Stage everything and commit. Returns True if a commit was created."""
        self._preserve_files()
        self._git("add", "-A")
        if not self._local_changes():
            return False
        text = (message or self.cfg.commit_message).replace(
            "{timestamp}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        self._git("commit", "-m", text)
        log.info("Committed: %s", text)
        return True

    def _merge_remote(self):
        result = self._git(
            "merge", "--no-edit", "origin/%s" % self.cfg.branch, check=False
        )
        if result.returncode != 0:
            self._git("merge", "--abort", check=False)
            raise RuntimeError(
                "Merge conflict with the remote branch; manual resolution required"
            )

    def push(self, message=None, auto=False):
        with self.lock:
            if not self.state["initialized"]:
                return
            if auto and self.state["paused"]:
                log.debug("Auto-push skipped (paused)")
                return
            self.state["busy"] = "push"
            try:
                self._write_gitignore()
                created = self._commit(message)
                self._refresh(fetch=True)
                if not created and self.state["ahead"] == 0:
                    log.debug("Nothing to push")
                    return
                if self.state["behind"] > 0:
                    log.info("Remote advanced by %d commit(s); merging first",
                             self.state["behind"])
                    self._merge_remote()
                self._git("push", "-u", "origin", self.cfg.branch)
                self.state["last_push"] = _now()
                self.state["last_error"] = None
                log.info("Pushed to origin/%s", self.cfg.branch)
            except Exception as err:  # noqa: BLE001 - surface to UI, keep running
                self.state["last_error"] = str(err)
                log.error("Push failed: %s", err)
            finally:
                self._refresh()
                self.state["busy"] = ""

    def pull(self, auto=False):
        with self.lock:
            if not self.state["initialized"]:
                return
            if auto and self.state["paused"]:
                log.debug("Auto-pull skipped (paused)")
                return
            self.state["busy"] = "pull"
            try:
                self._git("fetch", "origin", self.cfg.branch)
                self._refresh()
                if self.state["behind"] == 0:
                    log.debug("Already up to date with origin/%s", self.cfg.branch)
                    self.state["last_pull"] = _now()
                    self.state["last_error"] = None
                    return
                log.info("Remote is ahead by %d commit(s); pulling",
                         self.state["behind"])
                if self.state["dirty"]:
                    # Preserve local edits as a commit before merging.
                    self._commit("Local backup before pull {timestamp}")
                self._merge_remote()
                self.state["last_pull"] = _now()
                self.state["last_error"] = None
                log.info("Pulled latest changes from origin/%s", self.cfg.branch)
            except Exception as err:  # noqa: BLE001
                self.state["last_error"] = str(err)
                log.error("Pull failed: %s", err)
            finally:
                self._refresh()
                self.state["busy"] = ""

    def resolve(self, action):
        """Resolve a paused/diverged state. action = 'pull' or 'push'."""
        with self.lock:
            self.state["busy"] = "resolve"
            try:
                if action == "pull":
                    log.info("Resolving divergence: restoring from remote")
                    self._git("fetch", "origin", self.cfg.branch)
                    self._git("reset", "--hard", "origin/%s" % self.cfg.branch)
                    self._git("clean", "-fd", check=False)
                    self._write_gitignore()
                elif action == "push":
                    log.info("Resolving divergence: pushing local over remote")
                    self._write_gitignore()
                    self._commit("Initial backup {timestamp}")
                    self._git("push", "-u", "origin", self.cfg.branch)
                else:
                    raise RuntimeError("Unknown resolve action: %r" % action)
                self.state["last_error"] = None
                self.resume()
            except Exception as err:  # noqa: BLE001
                self.state["last_error"] = str(err)
                log.error("Resolve (%s) failed: %s", action, err)
            finally:
                self._refresh()
                self.state["busy"] = ""

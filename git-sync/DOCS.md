# Git Sync

Back up your Home Assistant configuration to a Git repository automatically, and
pull remote changes back down on a schedule. Includes a panel with manual
**Pull** and **Push** buttons.

## How it works

- **Auto push (backup on change):** the app watches the backup directory with
  `inotify`. When files change it waits for a short quiet period
  (`push_debounce`), then commits and pushes — so a burst of edits becomes one
  backup commit.
- **Auto pull (routine):** every `pull_interval` seconds the app fetches the
  remote. If the remote branch is ahead, it pulls (merging in the new commits).
- **Manual:** the panel always has **Pull now** and **Push now** buttons.

## Setup

### 1. Create a repository

Create an empty private repository on GitHub/GitLab/Gitea for your backups and
note its **SSH** URL, e.g. `git@github.com:youruser/ha-backup.git`.

### 2. Get an SSH deploy key

**Easiest — let the app generate one (recommended):** leave `ssh_key` and
`ssh_key_path` empty and just start the app. It creates a key automatically and
shows the **public** key in the **SSH deploy key** card of the panel. Pick the
algorithm with `ssh_key_type` (`ed25519` or `rsa`) and a label with
`ssh_key_comment`; you can also regenerate it from the panel (name + type).

1. Copy the public key from the panel.
2. Add it to your repo as a deploy key with **write access**
   (GitHub: *Settings → Deploy keys → Add deploy key*, tick *Allow write access*).
3. Click **Connect / retry** in the panel — no restart needed.

The private key stays inside the app (in `/data`) and is never displayed.

**Alternative — bring your own key:** generate one elsewhere
(`ssh-keygen -t ed25519 -f ha-backup-key -N "" -C "home-assistant"`), add the
`.pub` to the repo as a write deploy key, and either paste the private key into
`ssh_key` (one list entry per line, including the `BEGIN`/`END` lines) or drop
the file in `/ssl` and set `ssh_key_path: /ssl/ha-backup-key`.

> A GitHub deploy key can belong to **one repository only**. The app uses a
> single key, so it maps to a single backup repo.

### 3. Configure and start

Set at least `repository_url` and `branch`, then start the app and open the
**Git Sync** panel from the sidebar.

## Options

| Option | Description |
|---|---|
| `repository_url` | SSH (recommended) or HTTPS URL of the backup repo. |
| `branch` | Branch to pull/push (created on first push if missing). |
| `ssh_key` | Private deploy key, one list entry per line. Leave empty to auto-generate. |
| `ssh_key_path` | Path to an existing key file, used if `ssh_key` is empty. |
| `ssh_key_type` | Algorithm for the generated key: `ed25519` or `rsa`. |
| `ssh_key_comment` | Name/comment attached to the generated key. |
| `keep_remote_files` | Repo files the mirror must never delete (README, LICENSE, `.github`, …). |
| `backup_path` | Directory to sync. Default `/homeassistant`. |
| `auto_pull` | Enable the scheduled pull routine. |
| `pull_interval` | Seconds between remote checks. |
| `auto_push` | Commit & push automatically on local change. |
| `push_debounce` | Quiet period (seconds) before an auto push. |
| `commit_message` | Template; `{timestamp}` is substituted. |
| `commit_author_name` / `commit_author_email` | Identity for commits. |
| `include` | Seed only: optional whitelist used to create `.gitignore` on first run. |
| `exclude` | Seed only: patterns used to create `.gitignore` on first run. Edit the file afterwards. |
| `log_level` | `trace`…`fatal`. |

### Backup filters (.gitignore)

What gets backed up is controlled by a standard `.gitignore` at the root of the
backup directory. **This file is yours to edit** — via the **Backup filters**
card in the panel, the Home Assistant file editor, or any editor.

- The app **seeds** the `.gitignore` from the `include`/`exclude` options **only
  when none exists** (first run). After that it **never overwrites your edits**.
- The only time the app writes the file afterwards is when you **save it from the
  panel** (the *Backup filters* card loads the current file when you open the
  panel, lets you add patterns, and writes it only on **Save**).
- So `include`/`exclude` are just the **initial seed** — once a `.gitignore`
  exists, edit the file directly; changing the options won't touch it.

The seeded defaults exclude `secrets.yaml`, databases, logs, `.storage/`,
`.cache/`, `__pycache__/`, `deps/`, `backups/` and similar volatile, regenerable
or sensitive files.

> Note: `.gitignore` only stops **untracked** files. If you add a pattern for a
> file that's already in the backup, it won't be removed automatically — delete
> it once (it'll be committed as a removal) and the ignore keeps it out from then
> on.

## Repository layout: where backups go

The app mirrors your whole config to the **root of the chosen branch**. Two
clean layouts:

**A. Separate branch for backups (recommended).** Keep `main` for the repo's
presentation (`README`, `LICENSE`) and push backups to a dedicated **orphan**
branch (unrelated history), e.g. `backup`. Set `branch: backup` in the options.
If the branch doesn't exist yet, the app **creates it as an orphan on the first
push** — so you don't have to create it manually. To create it explicitly first:

```bash
git clone git@github.com:youruser/your-backup-repo.git
cd your-backup-repo
git checkout --orphan backup
git rm -rf . 2>/dev/null || true
git commit --allow-empty -m "Initialize backup branch"
git push origin backup
```

Then add the app's deploy key (write access) and set `branch: backup`.

**B. Everything on `main`.** Point the app at `branch: main` and keep your
`README`/`LICENSE` there too — see *Keeping README / LICENSE* below.

### Keeping README / LICENSE in the backup repo

When the backup branch **also** holds presentation files (layout B, or anything
the remote has that your config dir doesn't), they would normally be deleted on
the next push. List them in `keep_remote_files` (defaults: `README.md`,
`LICENSE`, `LICENSE.md`, `.github`) and they're restored from the remote on every
commit instead — they end up living in your config dir too, which Home Assistant
simply ignores. With layout A this rarely matters, since the `backup` branch
only holds your config.

## First-run divergence guard

If the backup directory is **not** yet a git repo but the remote branch
**already** contains a real backup (files beyond README/LICENSE/`.github`), the
app links to that history without touching your files. If your local config
differs from the remote, automatic sync **pauses** and the panel shows two
choices:

- **Restore from remote (remote wins):** `git reset --hard` to the remote state,
  overwriting local files. Use this when restoring onto a fresh instance.
- **Push local (local wins):** commit your local config and push it over the
  remote.

Pick one to clear the pause and resume automatic sync.

## Notes & limitations

- Merge conflicts (when the same lines changed locally and remotely) pause sync
  and show a **Merge conflict** card in the panel listing the affected files,
  with two one-click resolutions: **Keep my version (local wins)** or **Use
  remote version (remote wins)**. While a conflict is pending, automatic push
  and pull are held so nothing is committed with conflict markers.
- `secrets.yaml` is excluded by default. Think twice before backing up secrets
  to a remote, even a private one.
- Large `.storage`/database files are excluded to keep the repo small and avoid
  noisy commits.

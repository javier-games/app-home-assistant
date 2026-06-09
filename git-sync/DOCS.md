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
| `include` | Optional whitelist (gitignore syntax). Empty = track everything. |
| `exclude` | Paths never backed up (gitignore syntax). |
| `log_level` | `trace`…`fatal`. |

### Include / exclude

These are rendered into a managed block in a `.gitignore` at the root of the
backup directory.

- Leave `include` empty to back up everything except the `exclude` list.
- If you set `include`, it becomes a **whitelist**: only matching paths are
  tracked. `exclude` patterns always take precedence over includes.

The defaults exclude `secrets.yaml`, databases, logs, `.storage/`, `backups/`
and similar volatile or sensitive files. Remove items from `exclude` if you want
them backed up (be careful with `secrets.yaml`).

### Keeping README / LICENSE in the backup repo

The app mirrors your whole config to the **root of the branch**, so any file the
remote has that your config dir doesn't would normally be deleted on the next
push. To keep presentation files (so a dedicated backup repo can still have a
nice `README.md` and `LICENSE` on `main`), list them in `keep_remote_files`
(defaults: `README.md`, `LICENSE`, `LICENSE.md`, `.github`). These are restored
from the remote on every commit instead of being deleted — they end up living in
your config dir as well, which Home Assistant simply ignores.

This is what makes a **dedicated backup repo on `main`** work cleanly: keep your
LICENSE and README on `main`, point the app at `branch: main`, and your config
is backed up alongside them.

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

- Merge conflicts during an automatic pull are not auto-resolved: the merge is
  aborted and the error is shown in the panel. Resolve manually (conflicts are
  rare for single-instance backups).
- `secrets.yaml` is excluded by default. Think twice before backing up secrets
  to a remote, even a private one.
- Large `.storage`/database files are excluded to keep the repo small and avoid
  noisy commits.

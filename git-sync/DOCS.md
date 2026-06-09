# Git Sync

Back up your Home Assistant configuration to a Git repository automatically, and
pull remote changes back down on a schedule. Includes a panel with manual
**Pull** and **Push** buttons.

## How it works

- **Auto push (backup on change):** the add-on watches the backup directory with
  `inotify`. When files change it waits for a short quiet period
  (`push_debounce`), then commits and pushes — so a burst of edits becomes one
  backup commit.
- **Auto pull (routine):** every `pull_interval` seconds the add-on fetches the
  remote. If the remote branch is ahead, it pulls (merging in the new commits).
- **Manual:** the panel always has **Pull now** and **Push now** buttons.

## Setup

### 1. Create a repository

Create an empty private repository on GitHub/GitLab/Gitea for your backups and
note its **SSH** URL, e.g. `git@github.com:youruser/ha-backup.git`.

### 2. Create an SSH deploy key

On any machine:

```bash
ssh-keygen -t ed25519 -f ha-backup-key -N "" -C "home-assistant"
```

- Add the **public** key (`ha-backup-key.pub`) to the repository as a deploy key
  with **write access**.
- Paste the **private** key (`ha-backup-key`) into the add-on `ssh_key` option,
  one list entry per line, including the
  `-----BEGIN ...-----` / `-----END ...-----` lines. For example:

```yaml
ssh_key:
  - "-----BEGIN OPENSSH PRIVATE KEY-----"
  - "b3BlbnNzaC1rZXktdjEAAAAA..."
  - "...more lines..."
  - "-----END OPENSSH PRIVATE KEY-----"
```

  Alternatively, drop the key file in `/ssl` or `/share` and set
  `ssh_key_path: /ssl/ha-backup-key` instead of pasting it.

### 3. Configure and start

Set at least `repository_url` and `branch`, then start the add-on and open the
**Git Sync** panel from the sidebar.

## Options

| Option | Description |
|---|---|
| `repository_url` | SSH (recommended) or HTTPS URL of the backup repo. |
| `branch` | Branch to pull/push (created on first push if missing). |
| `ssh_key` | Private deploy key, one list entry per line. |
| `ssh_key_path` | Path to an existing key file, used if `ssh_key` is empty. |
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

## First-run divergence guard

If the backup directory is **not** yet a git repo but the remote branch
**already** contains a backup, the add-on links to that history without touching
your files. If your local config differs from the remote, automatic sync
**pauses** and the panel shows two choices:

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

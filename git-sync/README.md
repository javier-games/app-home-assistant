# Git Sync app

Back up your Home Assistant configuration to a Git repository on every local
change, and pull remote updates automatically on a schedule. Manual **Pull** /
**Push** buttons are available in the app panel.

See [DOCS.md](DOCS.md) for full setup and configuration details.

## Features

- 🔄 Auto **push** (backup) when local files change, debounced into one commit.
- ⏬ Auto **pull** on a configurable interval when the remote is ahead.
- 🖐️ Manual pull / push from an ingress web panel with live status.
- 🔑 SSH deploy key (pasted or from a file) or HTTPS remotes.
- 🎯 Include / exclude patterns via a managed `.gitignore`.
- 🛡️ Divergence guard that pauses and asks before overwriting on first setup.

# Changelog

## 1.0.0

Initial release.

- Back up the Home Assistant configuration to a Git repository.
- Automatic push (debounced) on local file changes via inotify.
- Automatic pull on a configurable schedule when the remote is ahead.
- Ingress web panel with manual **Pull** / **Push** actions and live status.
- SSH key support (pasted key or key file) plus HTTPS remotes.
- Include / exclude patterns rendered to a managed `.gitignore`.
- Divergence guard: on first setup, if the local config differs from an
  existing remote backup, automatic sync pauses and the panel offers an
  explicit "Restore from remote" or "Push local" choice.

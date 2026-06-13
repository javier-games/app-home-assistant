# Changelog

# [git-sync-v1.2.2](https://github.com/javier-games/app-home-assistant/compare/git-sync-v1.2.1...git-sync-v1.2.2) (2026-06-10)


### Bug Fixes

* **git-sync:** exclude .cache and __pycache__ by default ([d64c8d3](https://github.com/javier-games/app-home-assistant/commit/d64c8d395b8bc7f0b85c4592c3d5613f6bd7a82b))

# [git-sync-v1.2.1](https://github.com/javier-games/app-home-assistant/compare/git-sync-v1.2.0...git-sync-v1.2.1) (2026-06-10)


### Bug Fixes

* **git-sync:** handle unrelated histories in sync and conflict resolution ([f9ea8b6](https://github.com/javier-games/app-home-assistant/commit/f9ea8b6dc28d92346328291f68d9127ebae5602e))

# [git-sync-v1.2.0](https://github.com/javier-games/app-home-assistant/compare/git-sync-v1.1.0...git-sync-v1.2.0) (2026-06-10)


### Features

* **git-sync:** resolve merge conflicts from the web UI ([2f15449](https://github.com/javier-games/app-home-assistant/commit/2f154497a0154f300124f8ab1570e4a8471c4bd7))

# [git-sync-v1.1.0](https://github.com/javier-games/app-home-assistant/compare/git-sync-v1.0.0...git-sync-v1.1.0) (2026-06-10)


### Features

* **git-sync:** surface a clear panel error when ssh-keygen is unavailable ([f289e30](https://github.com/javier-games/app-home-assistant/commit/f289e306927aff237cec08eeab3e2149fdbd7566))

# git-sync-v1.0.0 (2026-06-10)


### Features

* **git-sync:** generate SSH keys in-app and preserve repo files ([134aa92](https://github.com/javier-games/app-home-assistant/commit/134aa92a8db08ee97b0bdd9c69b0458f03a49bea))

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

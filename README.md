# Home Assistant Apps by Javier García

Home Assistant app repository.

## Apps

### [Git Sync](./git-sync)

Back up your Home Assistant configuration to a Git repository on every local
change, and pull remote updates automatically on a schedule — with manual
pull/push buttons in the panel.

## Installation

1. In Home Assistant go to **Settings → Apps → App Store**.
2. Open the ⋮ menu (top right) → **Repositories**.
3. Add this repository URL:

   ```
   https://github.com/javier-games/app-home-assistant
   ```

4. The **Git Sync** app will appear in the store. Install it, configure the
   options (see the app docs), and start it.

## Versioning & releases

Each app is versioned **independently** with [SemVer](https://semver.org/), and
releases are automated with [semantic-release](https://semantic-release.gitbook.io/)
(via `semantic-release-monorepo`). The `.github/workflows/release.yml` workflow
runs on every push to `main` and, for each app, **only** cuts a release when a
commit changed one of that app's files.

When an app is released the workflow automatically:

- bumps `version:` in that app's `config.yaml`,
- updates the app's `CHANGELOG.md`,
- creates the git tag `‹app›-vX.Y.Z` (e.g. `git-sync-v1.2.0`) and a GitHub Release,
- commits the changes back to `main` with `[skip ci]`.

### Commit messages drive the version

Use [Conventional Commits](https://www.conventionalcommits.org/). The bump is
derived from the commit type:

| Commit | Result |
|---|---|
| `fix: …` / `perf: …` | patch (`x.y.Z`) |
| `feat: …` | minor (`x.Y.0`) |
| `feat!: …` or a `BREAKING CHANGE:` footer | major (`X.0.0`) |
| `docs:` / `chore:` / `refactor:` / `test:` … | no release |

The scope is optional but handy in a monorepo, e.g.
`feat(git-sync): add manual sync button`. What decides *which* app is released
is the **path of the changed files**, not the scope — so a `fix:` touching
`git-sync/` releases `git-sync` regardless of scope.

### Adding another app

Create `‹new-app›/` with its `config.yaml`, a `CHANGELOG.md`, a minimal
`package.json` (`name` = the app slug) and a `.releaserc.json` (copy the one in
`git-sync/`). The release workflow discovers it automatically — no workflow
changes needed.

> Note: the workflow pushes the version-bump commit and tags to `main`, so the
> `GITHUB_TOKEN` must be allowed to push there (relax branch protection for the
> actions bot, or use a dedicated token).

## License

Released under the [MIT License](./LICENSE).

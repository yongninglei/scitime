# Notes for AI assistants working in SciTime

SciTime is a macOS screen-time tracker for researchers. Its database is the user's
browsing and app history.

- **Never read the user's activity data.** That means `~/Library/Application Support/scitime/`,
  `~/Library/Logs/scitime/`, the iCloud `scitime/` folder, and the output of
  `scitime report`, `digest`, `now` or `dashboard`. Test with `uv run pytest` or
  `uv run scitime demo`, which uses a throwaway database of made-up data.
- **To change categories or rules** (the most common request), follow
  [docs/custom_categories.md](docs/custom_categories.md). Use `scitime categories`,
  `add-category`, `add-rule` and `which`. Don't hand-edit `rules.toml` unless the
  commands can't express the change.
- The user's rules live in `~/.config/scitime/rules.toml`.
  `src/scitime/default_rules.toml` is only the template for new installs.
- Run everything with `uv run …`.

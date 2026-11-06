# Notes for AI assistants working in SciTime

SciTime is a macOS screen-time tracker for researchers. Its database is the user's
browsing and app history.

- **Never read the user's activity data.** That means `~/Library/Application Support/scitime/`,
  `~/Library/Logs/scitime/`, the iCloud `scitime/` folder, and the output of
  `scitime report`, `digest`, `now` or `dashboard`. Test with `uv run pytest` or
  `uv run scitime demo`, which uses a throwaway database of made-up data.
- **To sort a website into a category** (the most common request), run
  `uv run scitime add-site <category> <site> ...`. It writes `~/.config/scitime/sites.yaml`.
  Keep to the existing categories (`scitime categories`). Check the result with
  `scitime which --url ...`.
- **For anything else** (new categories, apps, window titles, regex rules), follow
  [docs/custom_categories.md](docs/custom_categories.md): `add-category`, `add-rule`,
  `which`. Don't hand-edit the files unless the commands can't express the change.
- The user's files are `~/.config/scitime/sites.yaml` (websites, checked first) and
  `~/.config/scitime/rules.toml` (categories and rules). `src/scitime/default_rules.toml`
  is only the template for new installs.
- Run everything with `uv run …`.

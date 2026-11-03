# Your own categories and rules

SciTime sorts every app and website into a category with a list of rules in
`~/.config/scitime/rules.toml`. You can add categories and rules with four commands,
by hand, or by asking an AI assistant. This page is written for both you and your AI.

Rules are applied when a report is made, not when time is recorded, so a new rule also
re-sorts your past days. The menu bar picks a change up within a minute.

## The four commands

```bash
uv run scitime categories                      # list categories: key, label, colour, rules, focus
uv run scitime add-category KEY [--label "Shown name"] [--color "#rrggbb"] [--focus | --no-focus]
uv run scitime add-rule KEY --domain site.org  # or --app / --bundle / --url / --title / --detail
uv run scitime which --url https://site.org/x  # test: where would this go? records nothing
```

Run them from the SciTime folder (or add `--project /path/to/scitime` after `uv run`).

- **`KEY`** is a short name: lower case letters, digits and `_`, such as `grant_writing`.
- **`--focus`** makes the category count as *Research focus* on the dashboard.
  `--no-focus` keeps it out. Left out, only the built-in research categories count.
- If you leave out `--color`, a colour that is not in use yet is picked.
- Every change is checked before it is saved: the file must still be valid and every
  regex must compile. The previous version is kept as `rules.toml.bak`.
- Your rules go in a "my rules" block **above** the built-in rules. The first matching
  rule wins, so your rules always beat the defaults. This is how you move a site out of
  a built-in category.

## Examples

```bash
# A new category for grant writing, counted as focus time
uv run scitime add-category grant_writing --label "Grant writing" --focus
uv run scitime add-rule grant_writing --domain erc.europa.eu
uv run scitime add-rule grant_writing --title "proposal|grant"   # window titles (needs Screen Recording)

# Move a journal you read into Paper reading
uv run scitime add-rule paper_reading --domain journals.plos.org

# An app: by name, or by its bundle id
uv run scitime add-rule paper_reading --app "Skim|PDF Expert"
uv run scitime add-rule data_analysis --bundle 'org\.julialang\.'

# Teaching counts as its own thing, but only your course pages on the university site
uv run scitime add-category teaching --label "Teaching" --no-focus
uv run scitime add-rule teaching --domain moodle.example.edu

# Check it
uv run scitime which --url https://erc.europa.eu/apply
uv run scitime which --app Skim
```

## What a rule can match

Every field is a case-insensitive regex. If a rule has several fields, **all** of them
must match.

| Field | What it is | Example |
|---|---|---|
| `domain` | Website host, without `www.` | `sciencedirect.com` |
| `url` | The full URL of the front browser tab | `localhost:8501/` |
| `app` | App name as macOS shows it | `Skim\|PDF Expert` |
| `bundle` | App bundle id (exact app, any language) | `net\.sourceforge\.skim-app` |
| `title` | Window title (needs Screen Recording permission) | `\[SSH: ` |
| `detail` | Front terminal tab: `ssh:<host>` or `cli:<program>` | `^ssh:hpc` |

`--domain` with a plain site name such as `jov.arvojournals.org` is turned into a regex
that matches that site and its subdomains, so you don't have to write one. Anything with
regex characters is used as written.

To find an app's bundle id:

```bash
osascript -e 'id of app "Skim"'
```

## Editing by hand

`rules.toml` is plain TOML. A category is a table and a rule is a `[[rule]]` entry:

```toml
[categories.grant_writing]
label = "Grant writing"
color = "#e4572e"
focus = true

[[rule]]
category = "grant_writing"
domain = "(^|\\.)erc\\.europa\\.eu$"
```

Inside TOML strings a regex backslash is written twice (`\\.`). Run
`uv run scitime categories` afterwards: it fails loudly if the file is broken or a rule
names a category that doesn't exist. Change the copy in `~/.config/scitime/`, not
`src/scitime/default_rules.toml`. That file is only the starting point for new users.

## Asking an AI assistant

You can paste something like this into Claude Code, Codex or a similar tool opened in
the SciTime folder:

> Read `docs/custom_categories.md`. Add a category "Grant writing" (focus time) for the
> ERC and Horizon Europe portals and for Word windows whose title contains "proposal".
> Then show me `scitime which` for each one.

### Rules for the AI

1. **Never read the activity data.** Do not open, query, copy or summarise
   `~/Library/Application Support/scitime/`, `~/Library/Logs/scitime/`, the iCloud
   `scitime/` folder, or the output of `scitime report`, `digest`, `now` or `dashboard`.
   It is the user's browsing history. The commands on this page never need it. If the
   task seems to need it, ask the user to look themselves.
2. Use the four commands above rather than editing the file by hand. They validate,
   escape and back up for you, and put the rule where it wins.
3. Run `scitime categories` first to see the existing keys. Reuse a category when one
   fits rather than making a near-duplicate.
4. After each change, check it with `scitime which` using a made-up URL or app name, and
   show the user the result.
5. Prefer `--domain` for websites and `--bundle` (or `--app`) for apps. Use `--title`
   only when nothing else can tell the activity apart, because titles need Screen
   Recording permission and can contain private text.
6. To undo a change, the previous file is `~/.config/scitime/rules.toml.bak`. Ask the
   user before restoring it.

# 自定义网站、类别和规则

[English](custom_categories.md) · **中文**

SciTime 会把每个 app 和网站归入一个类别。你可以用三种方式改变它的分类方法，
从最简单到最灵活：

1. **`sites.yaml`**：在已有的类别下面列出网站。大多数情况用它就够了。
2. **命令**：`add-site`、`add-category` 和 `add-rule` 会帮你修改文件并做检查。
3. **`rules.toml`**：对 app 名称、bundle id、网址、窗口标题和终端标签页写正则规则。

每一种都可以自己做，也可以让 AI 助手来做。这份说明写给你，也写给你的 AI。

修改在生成报告时才生效，而不是在记录时间时，所以过去的日子也会重新归类。
菜单栏会在一分钟内用上新的设置。

## 网站：`~/.config/scitime/sites.yaml`

键是你的类别名（用 `uv run scitime categories` 查看），每个键下面是一个网站列表：

```yaml
paper_reading:
  - jov.arvojournals.org      # 这个网站和它所有的子域名；开头的 www. 会被忽略
  - journals.plos.org
  - pubs.myjournal.org
vibe_coding:
  - github.com/my-lab         # 只算以这个路径开头的页面
communication:
  - teams.microsoft.com
```

- **这里不能新建类别。** 键必须是已有的类别，这样大分类保持不变。要新建类别，
  先用 `scitime add-category`（见下文）。
- **这里优先。** `sites.yaml` 会在 `rules.toml` 的所有规则之前检查，所以把网站写在这里，
  就能把它从原来的内置类别里挪过来。
- **一个网站只属于一个类别。** 同一个网站写在两个类别下会报错。
- **只写网站名。** 可以带 `https://`、`www.` 或结尾的 `/`，都会自动去掉。需要正则的话，
  用 `add-rule`。

在终端里添加（会自动建文件、保留你的注释，并保存一份 `sites.yaml.bak`）：

```bash
uv run scitime add-site paper_reading jov.arvojournals.org journals.plos.org
uv run scitime sites                                              # 列出来
uv run scitime which --url https://jov.arvojournals.org/article  # → Paper reading, from sites.yaml
```

如果手动编辑时写错了（比如类别名拼错、缩进不对），记录程序和菜单栏会跳过这个文件
继续运行，并在日志里留下警告。运行 `uv run scitime sites` 能看到具体错在哪里。

## 类别和正则规则：命令

```bash
uv run scitime categories                      # 列出类别：名称、显示名、颜色、规则数、是否算专注
uv run scitime add-site KEY site.org [more.org ...]   # 网站 -> 类别（写入 sites.yaml）
uv run scitime add-category KEY [--label "显示名"] [--color "#rrggbb"] [--focus | --no-focus]
uv run scitime add-rule KEY --domain site.org  # 或 --app / --bundle / --url / --title / --detail
uv run scitime which --url https://site.org/x  # 测试：这个会归到哪里？不记录任何东西
```

在 SciTime 文件夹里运行（或者在 `uv run` 后面加 `--project /path/to/scitime`）。

- **`KEY`** 是一个短名字：小写字母、数字和 `_`，比如 `grant_writing`。
- **`--focus`** 让这个类别在仪表盘上计入「科研专注」时间，`--no-focus` 则不计入。
  不写的话，只有内置的科研类别会计入。
- 不写 `--color` 的话，会自动挑一个还没用过的颜色。
- 每次修改在保存前都会检查：文件必须仍然有效，每个正则都必须能编译。
  旧版本保存为 `rules.toml.bak`。
- 你的规则放在内置规则**上面**的「my rules」区块里。第一条匹配上的规则生效，
  所以你的规则总是优先于默认规则。只有 `sites.yaml` 排在它们前面。

## 例子

```bash
# 新建一个「写基金」类别，计入专注时间
uv run scitime add-category grant_writing --label "Grant writing" --focus
uv run scitime add-rule grant_writing --domain erc.europa.eu
uv run scitime add-rule grant_writing --title "proposal|grant"   # 按窗口标题（需要录屏权限）

# 把你读的期刊算作读文献
uv run scitime add-rule paper_reading --domain journals.plos.org

# 一个 app：按名称，或者按 bundle id
uv run scitime add-rule paper_reading --app "Skim|PDF Expert"
uv run scitime add-rule data_analysis --bundle 'org\.julialang\.'

# 教学单独算一类，但只算学校网站上的课程页面
uv run scitime add-category teaching --label "Teaching" --no-focus
uv run scitime add-rule teaching --domain moodle.example.edu

# 检查一下
uv run scitime which --url https://erc.europa.eu/apply
uv run scitime which --app Skim
```

## 规则能匹配什么

每个字段都是不区分大小写的正则表达式。一条规则有好几个字段时，**全部**都要匹配。

| 字段 | 是什么 | 例子 |
|---|---|---|
| `domain` | 网站主机名，不含 `www.` | `sciencedirect.com` |
| `url` | 前台浏览器标签页的完整网址 | `localhost:8501/` |
| `app` | macOS 显示的 app 名称 | `Skim\|PDF Expert` |
| `bundle` | app 的 bundle id（精确对应某个 app，与系统语言无关） | `net\.sourceforge\.skim-app` |
| `title` | 窗口标题（需要录屏权限） | `\[SSH: ` |
| `detail` | 前台终端标签页：`ssh:<主机>` 或 `cli:<程序>` | `^ssh:hpc` |

`--domain` 后面写 `jov.arvojournals.org` 这样的普通网站名时，会自动变成匹配这个网站
及其子域名的正则，不用自己写。带正则符号的写法会原样使用。

查一个 app 的 bundle id：

```bash
osascript -e 'id of app "Skim"'
```

## 手动编辑

`rules.toml` 是普通的 TOML 文件。类别是一个表，规则是一个 `[[rule]]` 条目：

```toml
[categories.grant_writing]
label = "Grant writing"
color = "#e4572e"
focus = true

[[rule]]
category = "grant_writing"
domain = "(^|\\.)erc\\.europa\\.eu$"
```

TOML 字符串里正则的反斜杠要写两次（`\\.`）。改完运行 `uv run scitime categories`：
文件坏了或者规则用了不存在的类别，它会直接报错。改的是 `~/.config/scitime/` 里那份，
不是 `src/scitime/default_rules.toml`，后者只是新用户的初始模板。

## 让 AI 助手来做

可以在 SciTime 文件夹里打开 Claude Code、Codex 等工具，然后粘贴类似这样的话：

> 读一下 `docs/custom_categories.zh-CN.md`。把 jov.arvojournals.org、journals.plos.org
> 和我实验室的 GitHub（github.com/my-lab）放到合适的类别里，然后给我看每个网站的
> `scitime which` 结果。

或者

> 读一下 `docs/custom_categories.zh-CN.md`。新建一个「Grant writing」类别（算专注时间），
> 包括 ERC 和 Horizon Europe 的网站，以及标题里有「proposal」的 Word 窗口。

### 给 AI 的规则

1. **绝不读取使用记录。** 不要打开、查询、复制或总结
   `~/Library/Application Support/scitime/`、`~/Library/Logs/scitime/`、iCloud 里的
   `scitime/` 文件夹，也不要看 `scitime report`、`digest`、`now` 或 `dashboard` 的输出。
   那是用户的浏览记录。这份说明里的命令都用不到它。如果任务看起来需要它，请用户自己去看。
2. **网站写进 `sites.yaml`，用 `scitime add-site`。** 只有 app、窗口标题、终端标签页，
   或者需要正则的网址才用 `add-rule`。这些命令会帮你检查、保留注释和备份。
3. **沿用用户已有的类别。** 先运行 `scitime categories`，把东西放进已有的类别。
   只有用户要求新类别时，才用 `add-category` 新建。
4. 每次修改后，用一个虚构的网址或 app 名运行 `scitime which` 检查，并把结果给用户看。
5. 网站优先用 `--domain`，app 优先用 `--bundle`（或 `--app`）。只有别的方法都分不出来时
   才用 `--title`，因为窗口标题需要录屏权限，而且可能包含隐私内容。
6. 要撤销修改，旧文件是 `~/.config/scitime/sites.yaml.bak` 和 `rules.toml.bak`。
   恢复之前先问用户。
7. 不要为了用户自己的网站去改 `src/scitime/default_rules.toml`，它是所有新安装的模板。

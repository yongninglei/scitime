# iPhone 设置（快捷指令）

[English](iphone_setup.md) · **中文**

iPhone 不允许普通 app 读取其他 app 的使用时间，所以用「快捷指令 → 自动化」记录：
每次打开/关闭某个 app，就往 iCloud 里的一个文本文件追加一行。Mac 上的 scitime 读取这个
文件，把手机时间和电脑时间加在一起，再把合并后的仪表盘写回同一个 iCloud 文件夹，手机
在「文件」app 里就能看。两边只要联网，iCloud 会自动同步，不经过任何第三方服务器。

```
iPhone 快捷指令 ──追加一行──▶ iCloud 云盘/快捷指令/scitime/phone_events.txt ──▶ Mac scitime
iPhone「文件」app ◀──────── iCloud 云盘/快捷指令/scitime/scitime.html ◀──每 10 分钟── Mac scitime
```

一共要做：1 个快捷指令 + 每个 app 1 个「打开」自动化 + 1 个「关闭」自动化。大约 10 分钟。

---

## 第 1 步：建一个快捷指令「scitime」（只做一次）

1. 打开「快捷指令」app →「快捷指令」标签 → 右上角 **＋**。
2. 顶部名字改成 **scitime**。（如果第 3 步找不到变量「快捷指令输入」：点名字旁的 ⌄ →
   「详细信息」，让它接收「文本」输入。）
3. 添加操作 **文本**，在文本框里：
   - 插入变量 **当前日期**，然后点一下这个变量 → 日期格式选 **ISO 8601**，打开 **包括 ISO 8601 时间**；
   - 紧接着输入一个英文逗号 `,`；
   - 再插入变量 **快捷指令输入**。
   
   结果看起来是：`[当前日期],[快捷指令输入]`
4. 添加操作 **追加到文本文件**（Append to Text File）：
   - 追加内容：上一步的 **文本**
   - 文件夹：**快捷指令**（Shortcuts）
   - 文件路径：`scitime/phone_events.txt`
   - 打开 **新建一行**（Make New Line）
5. 完成。

## 第 2 步：每个要统计的 app 建一个「打开」自动化

以抖音为例：

1. 「自动化」标签 → **＋** → **App**。
2. 「App」选 **抖音**；只勾 **已打开**；选 **立即运行**（不要选「运行前询问」）；关掉「运行时通知」。→ 下一步。
3. **新建空白自动化** → 添加操作 **文本**，内容填 `open,Douyin`。
4. 添加操作 **运行快捷指令** → 选 **scitime**，输入选上一步的 **文本**。
5. 完成。

其他 app 重复，只换第 3 步的名字。名字要和下表一致（大小写无所谓，中文名也行），
这样 Mac 才能分对类别：

| App | 第 3 步填 | 类别 |
|---|---|---|
| 抖音 | `open,Douyin` | 社交/视频 |
| Instagram | `open,Instagram` | 社交/视频 |
| 小红书 | `open,Xiaohongshu` | 社交/视频 |
| 哔哩哔哩 | `open,Bilibili` | 社交/视频 |
| YouTube | `open,YouTube` | 社交/视频 |
| X / 微博 / 知乎 | `open,X` / `open,Weibo` / `open,Zhihu` | 社交/视频 |
| 微信 | `open,WeChat` | 邮件/聊天 |
| 邮件 / Gmail / Outlook | `open,Mail` / `open,Gmail` / `open,Outlook` | 邮件/聊天 |
| Safari / Chrome | `open,Safari` / `open,Chrome` | 浏览 |
| ChatGPT / Claude / Google 文档 | `open,ChatGPT` / `open,Claude` / `open,Docs` | 论文+AI 写作 |

别的 app 也可以加，名字随便起；不在规则里的会算到「Other」。想改分类就编辑
Mac 上的 `~/.config/scitime/rules.toml` 里 `bundle = "^iphone$"` 那几条规则。

## 第 3 步：一个「关闭」自动化（覆盖所有 app）

1. 「自动化」→ **＋** → **App**。
2. 「App」里把第 2 步的 **所有 app 都选上**；只勾 **已关闭**；**立即运行**。→ 下一步。
3. 新建空白自动化 → 操作 **文本** 内容 `close` → 操作 **运行快捷指令** 选 **scitime**，输入选 **文本**。

> 手机同一时间只有一个 app 在前台，所以「打开下一个 app」也会结束上一个。锁屏时如果
> 没触发「已关闭」，单次最多算 120 分钟（`rules.toml` 里 `max_session_minutes` 可改）。

## 第 4 步：在手机上看合并后的时间

- 「文件」app → **iCloud 云盘 → 快捷指令 → scitime → scitime.html**，点开即可。
- 想放到主屏幕：新建快捷指令「看时间」→ 操作 **获取文件**（快捷指令文件夹，路径
  `scitime/scitime.html`，关掉「显示文档选择器」）→ 操作 **快速查看** → 分享 →
  **添加到主屏幕**。

Mac 上 scitime 在运行时每 10 分钟更新一次这个页面；Mac 上运行 `uv run scitime dashboard`
会立即更新。

## 第 5 步：检查

1. 在手机上打开抖音，过一会儿退出。
2. Mac 上：
   ```bash
   cat ~/Library/Mobile\ Documents/iCloud~is~workflow~my~workflows/Documents/scitime/phone_events.txt
   uv run scitime report
   ```
   应该看到两行（`open,Douyin` 和 `close`），报告里「Social / video」的 📱 一列有时间。

如果文件里的日期不是 `2026-11-01T21:03:05+01:00` 这种格式，回到第 1 步检查日期格式。

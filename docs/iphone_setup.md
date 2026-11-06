# iPhone setup (Shortcuts)

**English** · [中文](iphone_setup.zh-CN.md)

iOS does not let ordinary apps read how long other apps are used, so SciTime uses
**Shortcuts → Automation** instead. Each time you open or close an app, a line is appended
to a text file in iCloud. SciTime on the Mac reads that file, adds the phone time to the
computer time, and writes the combined dashboard back to the same iCloud folder, so you can
open it on the phone in the Files app. iCloud syncs both ways on its own; no third-party
server is involved.

```
iPhone Shortcuts ──append a line──▶ iCloud Drive/Shortcuts/scitime/phone_events.txt ──▶ SciTime on the Mac
iPhone Files app ◀───────────────── iCloud Drive/Shortcuts/scitime/scitime.html ◀──every 10 min── SciTime on the Mac
```

You need one shortcut, one "Is Opened" automation per app, and one "Is Closed" automation.
It takes about 10 minutes.

---

## Step 1: make a shortcut called "scitime" (once)

1. Open the **Shortcuts** app → **Shortcuts** tab → **＋** at the top right.
2. Rename it **scitime**. (If you can't find the **Shortcut Input** variable in step 3,
   tap ⌄ next to the name → **Details**, and let it receive **Text** input.)
3. Add a **Text** action. In its text box:
   - insert the **Current Date** variable, tap it, set the date format to **ISO 8601** and
     turn on **Include ISO 8601 Time**;
   - type a comma `,` right after it;
   - insert the **Shortcut Input** variable.

   It should look like: `[Current Date],[Shortcut Input]`
4. Add an **Append to Text File** action:
   - Append: the **Text** from the previous step
   - Folder: **Shortcuts**
   - File path: `scitime/phone_events.txt`
   - Turn on **Make New Line**
5. Done.

## Step 2: an "Is Opened" automation for each app you want to count

Instagram as an example:

1. **Automation** tab → **＋** → **App**.
2. Choose **Instagram** as the app. Tick only **Is Opened**, choose **Run Immediately**
   (not "Run After Confirmation"), and turn off **Notify When Run**. → **Next**.
3. **New Blank Automation** → add a **Text** action with `open,Instagram`.
4. Add a **Run Shortcut** action → choose **scitime**, with the **Text** from the previous
   step as its input.
5. Done.

Repeat for the other apps, changing only the name in step 3. Use the names in this table
(capitals don't matter) so the Mac sorts them into the right category:

| App | Text in step 3 | Category |
|---|---|---|
| Instagram | `open,Instagram` | Social / video |
| TikTok / Douyin | `open,TikTok` / `open,Douyin` | Social / video |
| YouTube | `open,YouTube` | Social / video |
| X / Reddit / Facebook | `open,X` / `open,Reddit` / `open,Facebook` | Social / video |
| Xiaohongshu / Bilibili / Weibo | `open,Xiaohongshu` / `open,Bilibili` / `open,Weibo` | Social / video |
| WhatsApp / Telegram / WeChat | `open,WhatsApp` / `open,Telegram` / `open,WeChat` | Mail / chat |
| Mail / Gmail / Outlook | `open,Mail` / `open,Gmail` / `open,Outlook` | Mail / chat |
| Safari / Chrome | `open,Safari` / `open,Chrome` | Browsing |
| ChatGPT / Claude / Google Docs | `open,ChatGPT` / `open,Claude` / `open,Docs` | Paper + AI writing |
| Paperpile / Zotero | `open,Paperpile` / `open,Zotero` | Paper reading |

You can add other apps with any name. Apps that no rule knows count as "Other". To change
how they are sorted, edit the `bundle = "^iphone$"` rules in `~/.config/scitime/rules.toml`
on the Mac.

## Step 3: one "Is Closed" automation (for all apps)

1. **Automation** → **＋** → **App**.
2. Choose **all the apps from step 2**. Tick only **Is Closed**, **Run Immediately**. → **Next**.
3. New Blank Automation → a **Text** action with `close` → a **Run Shortcut** action with
   **scitime**, input **Text**.

> Only one app is in front at a time, so opening the next app also ends the previous one.
> If "Is Closed" doesn't fire when the phone locks, one session counts for at most 120
> minutes (change `max_session_minutes` in `rules.toml`).

## Step 4: see the combined time on the phone

- **Files** app → **iCloud Drive → Shortcuts → scitime → scitime.html**, and tap it.
- To put it on the Home Screen: make a shortcut "My time" → **Get File** (Shortcuts folder,
  path `scitime/scitime.html`, turn off **Show Document Picker**) → **Quick Look** →
  Share → **Add to Home Screen**.

While SciTime runs on the Mac, this page is updated every 10 minutes. Running
`uv run scitime dashboard` on the Mac updates it straight away.

## Step 5: check it

1. Open Instagram on the phone, then leave it after a moment.
2. On the Mac:
   ```bash
   cat ~/Library/Mobile\ Documents/iCloud~is~workflow~my~workflows/Documents/scitime/phone_events.txt
   uv run scitime report
   ```
   You should see two lines (`open,Instagram` and `close`), and time in the 📱 column for
   "Social / video" in the report.

If the dates in the file don't look like `2026-11-01T21:03:05+01:00`, go back to step 1 and
check the date format.

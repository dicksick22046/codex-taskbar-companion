# Codex Taskbar Companion

**English** · [简体中文](docs/i18n/README.zh-CN.md) · [日本語](docs/i18n/README.ja.md) · [Español](docs/i18n/README.es.md)

Shows Codex quota, token usage, and task status in the Windows 11 taskbar or a floating capsule.

[Download](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest) · [Report an issue](https://github.com/dicksick22046/codex-taskbar-companion/issues) · [Changelog](CHANGELOG.md)

![Taskbar and task panel](docs/images/preview.png)

*Preview with sample tasks and usage data.*

## Install

Requires **Windows 11 x64** and the **Codex desktop app**, installed and signed in.

1. Download `CodexTaskbarCompanion-<version>-Setup-x64.exe` from [Releases](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest).
2. Run the installer, then start the app. Python, Qt, and fonts are included. Administrator access is not required.
3. Right-click the strip to open Settings. Choose which items to show and whether to start at sign-in.

New installations use **Auto** placement: prefer the primary taskbar and float when there is not enough room. Existing placement preferences are preserved. Right-click either strip or the tray for **Find task…**, **Task status**, Settings and Quit. Updates are checked on GitHub; installation starts only when you choose it.

Choose **Status bar placement → Floating** to move the quota/status strip. The optional **Running task strip** is independent: drag it to a convenient position and that position is remembered. **Keep floating windows on top** applies to enabled floating windows; colors and transparency apply to both strips.

**Auto** prefers the primary taskbar and uses a floating capsule when there is not enough room. It waits for stable availability before switching back and avoids automatic overlays over fullscreen foreground apps. **Floating display** can follow primary or pin a display; disconnecting it temporarily uses primary, and reconnecting restores the saved relative position. This does not add secondary-taskbar embedding or claim validation on other Windows versions.

![Floating capsule](docs/images/floating.png)

*Floating mode with sample data; the panel and capsule use the same controls as taskbar mode.*

## Use

| Click | Opens |
| --- | --- |
| Weekly quota | Daily token usage for the current quota cycle |
| Daily quota usage | Today's token usage by task and status |
| 5h quota, when available | Remaining quota, reset time, and recorded balance history |
| Reset countdown | Reset history and available reset credits |
| Status dot and count | Tasks in that state, with the current or latest turn's duration |
| Task title | That task in Codex |

Enable **Running task strip** in Indicators to see a separate 420-DIP title carousel. It is off by default for new users; existing display choices are preserved on upgrade. **Task status counts** remains an independent control on the original strip. Hovering pauses task rotation and reveals long titles; empty Running lists hide the title strip. Main/Side markers appear only in live task surfaces; Side entries return to the parent task and do not add duplicate statistics/search rows. Running markers are static; motion is reserved for interactions and deliberate long-title reading.

Settings include English, Simplified Chinese, Japanese, and Spanish UI selection, optional hover-to-open panels, and optional quota rotation. With rotation enabled, all enabled left-side indicators, including the reset countdown, share one fixed-width position.

Capsule colors and background transparency are set manually in Settings. Choose Dark or Light; 0% transparency gives a solid background. Text and ring opacity are unaffected.

The status strip fits the actual enabled labels and counts within the available screen/taskbar space. It does not silently hide selected indicators or change quota-rotation preferences. If complete content cannot fit, task categories remain available in the tray/context menu. The separate task strip keeps a stable width during rotation.

Right-click and choose **Find task…** to search recorded tasks by title or project. Filter to one project, then click a result or use the arrow keys and Enter to return to it in Codex. This filter affects the search window only; quota and strip counts keep their existing scope.

Task search defaults to project, title, status and recent activity. Enable **History statistics** to reveal local lifetime **run time, tokens and execution turns**, plus the unit selector. Sorting, filtering, selection and existing caches are preserved. The history scan runs only while this view is visible and statistics are expanded; collapsing it pauses indexing. Run time includes waits within a turn and excludes gaps. Turns are execution rounds. `≥` marks a known lower bound when records are incomplete.

Settings use a sidebar for **Appearance**, **Indicators** and **General**. Placement, theme and display changes apply immediately, including the capsule's width.

General includes optional input-needed notifications (off by default) and **Copy diagnostics** for bug reports. Notifications group new waiting tasks and do not repeat unchanged work. Diagnostics exclude task names, account details, paths and log contents.

![Grouped settings](docs/images/settings.png)

An unresolved synchronous `request_user_input` record appears as **Needs input**, with an amber question mark in the strip. Open that task in Codex to answer. Asynchronous app questions, unsaved side chats and human approval prompts are not all observable; automatic review is not labeled as a request for your approval.

![Needs input indicator with sample data](docs/images/attention.png)

![Task search](docs/images/task-search.png)

*Search window with sample tasks. Search runs locally and does not save your query.*

## About the numbers

- Quota percentages come from the account; Token statistics come from this computer. Local cycle/today panels label both scopes explicitly. A quiet **Cached** marker identifies retained readings after a quota failure, with the last successful update in tooltips/details. Expired balances and reset times become unknown across all quota surfaces.
- **Week left / 5h left** show remaining account quota; **Today used** is observed consumption, not necessarily a complete day. The detail shows the observation start time. Restarting preserves the baseline, earlier usage is not reconstructed, and resets are accumulated as separate intervals.
- The daily task list includes today's turns. Status panels show the current or latest turn's duration, including time waiting for tools.
- Historical token totals cover locally recorded tasks. Other devices and temporary side chats without saved usage are excluded.
- The task catalog includes recorded CLI, VS Code, app-server and CLI execution sources. Newly included records can increase local token totals. Persisted synchronous input requests are observable; live approval routing and unrecorded questions are not fully exposed.

Reset history uses **Scheduled** for an observed natural rollover, **Manual** for a reset confirmed through this tool, and **Other recovery** for other observed recoveries. The latter has an unconfirmed source; its stored historical classification is unchanged. Using a reset credit requires confirmation and consumes a real credit.

## Data and limitations

Settings, task names, and usage records are stored in `%USERPROFILE%/.codex-taskbar-companion`. Updates and uninstalling retain this directory. The app does not store conversation text or account credentials and has no telemetry. Remove private information from screenshots and logs before posting them.

This is an early Windows 11 release. Windows 10, macOS, separate widgets on multiple monitors, and third-party taskbars have not been validated. The installer is not code-signed. Side-chat detection depends on Codex desktop logs, so changes to those logs may require an update. Temporary read failures retain valid data; not every transient Codex error can be detected.

## Development

Use Python 3.12. Packaging also requires Inno Setup.

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
./start.ps1
.venv/Scripts/python.exe -m unittest discover
./scripts/package.ps1 -Compiler 'C:/Path/To/Inno Setup/ISCC.exe'
```

Exit the installed app before running from source; a second launch opens the existing instance's settings. Build outputs go to `dist/` and `release/`. Version information is in `codex_taskbar/build_info.py`.

To preview the 5h panel without an eligible account, run `./scripts/preview-session.ps1`. It uses sample data in a separate window and does not change your account or settings.

Implementation notes: [architecture](docs/architecture.md), [interaction specification](docs/specs/interaction.md), [performance checks](docs/performance.md), and [roadmap](docs/roadmap.md). Some technical documents are in Chinese.

## License

[MIT](LICENSE). Fonts and dependencies retain their own licenses; see [Third-party components](THIRD_PARTY.md). This is an independent community project, not affiliated with OpenAI.

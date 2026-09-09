# Codex Taskbar Companion

**English** · [简体中文](docs/i18n/README.zh-CN.md) · [日本語](docs/i18n/README.ja.md) · [Español](docs/i18n/README.es.md)

Shows Codex quota, token usage, and task status in the Windows 11 taskbar.

[Download](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest) · [Report an issue](https://github.com/dicksick22046/codex-taskbar-companion/issues) · [Changelog](CHANGELOG.md)

![Taskbar and task panel](docs/images/preview.png)

*Preview with sample tasks and usage data.*

## Install

Requires **Windows 11 x64** and the **Codex desktop app**, installed and signed in.

1. Download `CodexTaskbarCompanion-<version>-Setup-x64.exe` from [Releases](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest).
2. Run the installer, then start the app. Python, Qt, and fonts are included. Administrator access is not required.
3. Right-click the strip to open Settings. Choose which items to show and whether to start at sign-in.

The strip sits on the left of the primary taskbar. If there is not enough space, open Settings from the system tray. Updates are checked on GitHub; installation starts only when you choose it.

## Use

| Click | Opens |
| --- | --- |
| Weekly quota | Daily token usage for the current quota cycle |
| Daily quota usage | Today's token usage by task and status |
| 5h quota, when available | Remaining quota, reset time, and recorded balance history |
| Reset countdown | Reset history and available reset credits |
| Status dot and count | Tasks in that state, with the current or latest turn's duration |
| Task title | That task in Codex |

Running tasks rotate in the strip. Hovering pauses rotation and scrolls long titles. Unread results, stopped tasks, and failed tasks have separate indicators. An active side chat marks its parent task as running; the parent is counted once.

Settings include English, Simplified Chinese, Japanese, and Spanish UI selection, optional hover-to-open panels, and optional quota rotation. With rotation enabled, weekly, daily, and 5h metrics share one position; the countdown stays visible.

## About the numbers

- Quota percentages come from the account. Tokens come from task logs on this computer. Token totals cannot be converted into an exact quota percentage or subscription cost.
- Daily quota usage starts at the day's first available reading. Restarting preserves it. Earlier usage is not reconstructed; a reset during the day is handled as a separate interval.
- The daily task list includes today's turns. Status panels show the current or latest turn's duration, including time waiting for tools.
- Historical token totals cover locally recorded tasks. Other devices and temporary side chats without saved usage are excluded.

Reset history uses **Scheduled** for an observed natural rollover, **Manual** for a reset confirmed through this tool, and **Official** for other observed recoveries. Official is an inferred category, not a verified statement from OpenAI. Using a reset credit requires confirmation and consumes a real credit.

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

Implementation notes: [architecture](docs/architecture.md) and [interaction specification](docs/specs/interaction.md), currently in Chinese.

## License

[MIT](LICENSE). Fonts and dependencies retain their own licenses; see [Third-party components](THIRD_PARTY.md). This is an independent community project, not affiliated with OpenAI.

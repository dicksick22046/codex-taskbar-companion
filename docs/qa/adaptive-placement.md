# Adaptive placement verification — 0.8.0

- 246 Windows tests pass; the offscreen-only class is run separately with four passing window-level journeys. Main and version-tag Windows/Linux CI pass.
- Controlled cases cover stable fallback/recovery, availability chatter, press/panel locks, fullscreen suppression, legacy preferences, primary following, pinned negative-origin displays, disconnect/reconnect and screen-bound menus/settings/search.
- Native settings renders were inspected in four languages at full and compact widths. The Japanese display caption and display-option text were shortened after captures exposed clipping.
- The installed executable matches the build. On this machine, Auto attached to the available primary taskbar and Floating detached its native owner. The tool remained visible, original settings were restored, foreground did not change, and live quota/task data resumed without errors.
- Published installer and checksum assets were checked, including old-client update detection and public download verification. No real reset, system taskbar alignment change, display reconfiguration or mouse control was used.

Actual mixed-DPI multi-monitor hardware, Windows 10/ARM64 and other operating systems have not been validated. Simulated topology is not a substitute for those checks. Secondary-taskbar embedding is outside this release.

# Automatic placement and floating display selection

## Behavior

Add Auto beside Taskbar and Floating. Preserve existing saved placement and keep Taskbar as the default. Auto prefers the existing primary-taskbar location, falls back to the existing floating capsule when usable space is unavailable, and returns when space recovers. A changed availability result must persist for one second to avoid layout chatter; explicit settings changes and the initial decision resolve immediately. Defer background mode switches during a press, drag, menu or reset confirmation. Never rewrite the user's chosen mode or floating position as a consequence of fallback.

An intentionally hidden taskbar/fullscreen result must not cause a new overlay. Auto's floating fallback is hidden while the foreground application covers its monitor; manual Floating retains the existing keep-on-top behavior. Reuse the current 150 ms UI check and existing data Provider; add no collection thread or network request.

Settings expose Floating display for Auto and Floating. Primary display follows the current primary; named displays are pinned by Qt screen name. Retain legacy saved screen choices. Selecting a display preserves a saved relative position or uses the existing default floating placement. A disconnected pinned display temporarily uses primary without overwriting the saved choice, and returns when reconnected. Dragging to another display updates the choice and normalized position. Keep every panel within the resolved screen's available bounds.

Refresh the display selector only when screen topology, selected display or language changes; do not repopulate it on every status tick. Show an unavailable saved display explicitly rather than silently claiming a different selection.

## Verification

Cover availability recovery/chatter, manual mode preservation, fullscreen suppression, interaction locks, multiple/negative-origin screens, disconnect/reconnect, legacy settings, display selection/drag, and complete settings flows. Use synthetic topologies and offscreen input; do not change the user's real taskbar alignment or display configuration. Verify the primary display on this machine. Report mixed-DPI hardware and other Windows versions as untested until actual device checks exist.

References: [TrafficMonitor options](https://github.com/zhongyang219/TrafficMonitor/wiki/Option-Settings), [Qt QScreen](https://doc.qt.io/qt-6/qscreen.html), [MonitorFromWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-monitorfromwindow). Reuse the project's existing floating host, not a second window implementation.

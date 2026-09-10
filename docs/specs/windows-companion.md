# Windows companion milestone

## Scope

Extend the existing Windows presentation with an optional floating capsule and reduce unnecessary background work. Keep one Provider, one strip, existing quota/task semantics and existing data directory. Default placement remains Taskbar; upgrading preserves existing preferences. This milestone does not claim macOS, Linux or untested Windows support.

## Performance

Keep the existing 150 ms interaction/visibility checks and 30 s quota / 5 s catalog sampling. Repaint static content only when its visible state changes. Animate only visible animated content. Refresh an open panel when data, displayed time or geometry changes, not at every UI tick. Refresh settings connection status separately from rebuilding controls and reading startup registration.

The diagnostic snapshot is not the persistent quota or reset ledger. Write it at most once per 30 s, with the latest snapshot flushed on graceful shutdown; memory snapshots remain current. Ledger persistence and reset request durability are unchanged.

Validate with repeatable idle/active render counts and CPU samples using controlled data. Report the test conditions; no universal performance guarantees.

## Floating placement

Settings offer Taskbar / Floating, plus Keep on top for Floating. Switch immediately without restarting collection. Reuse manual theme/transparency, indicators, tasks and panels. Right-click retains Settings and Quit. The tray remains available if all indicators are disabled.

The floating capsule is 30 DIP high, with a maximum width of 540 DIP constrained by the screen. Content sizing is specified below. It is independent of taskbar availability and alignment. Drag anywhere inside the capsule; movement must exceed the system drag threshold before being a drag. A completed drag never opens a panel or task. Preserve normal click targets and outside dismissal. Transparent rounded corners stay outside the target.

### Adaptive capsule width

Both placements fit the enabled metrics, nonempty status counts and task content, with balanced end padding. Keep the existing taskbar space limit and floating 540 DIP limit. Measure every current rotating task and use the longest required width, so switching tasks does not resize the capsule. Retain the quota rotation slot's existing stable width. Long content still elides and scrolls on hover. No extra setting is needed.

Keep the left edge and ring positions fixed when content changes. Defer shrinking while hovering, pressing, dragging, or a panel/menu/settings window is open. Opening a task panel continues to use its own readable minimum width even when the capsule is short.

Floating position records may include a reference width, so resizing content does not change the restored left anchor. Older position records assume the previous 540 DIP reference. Screen changes still constrain the whole capsule. Invalid reference widths are discarded. Dragging saves the actual current width as the reference.

Persist position only after a completed drag, as screen name and normalized coordinates within its available area. Restore on that screen when present; use the primary screen if removed. Clamp the whole capsule after display/DPI/work-area changes. Do not follow the taskbar owner in Floating mode. Keep-on-top changes must not activate the window. Defaults: Keep on top enabled, lower-left inset position.

Panels prefer above the capsule, open below when above lacks space, and remain within that screen's available area. Tall lists scroll within the available space. Preserve the 8 DIP gap. Mode changes close the current panel; data, task selection and quota baselines remain intact.

## Verification and delivery

Use isolated preferences and mocked Provider/reset APIs. No global pointer input, focus stealing or real reset consumption in tests. Cover drag threshold/cancellation, target freezing, mode persistence, screen removal/negative origins, popup edges, topmost/owner changes and existing native visibility recovery.

Small commits: contract; performance; floating presentation; verified documentation/package as warranted. Release decisions are delegated to the maintainer. Publish only after tests, source rendering and installed-build checks; distinguish simulated monitor tests from actual multi-monitor/DPI hardware testing.

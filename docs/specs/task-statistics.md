# Lifetime task statistics and settings refinement

## Task statistics

The task finder adds sortable Run time, Tokens and Turns columns alongside project, task, known status and activity. Default remains latest activity first. Header clicks reverse order; missing values sort last in either direction. Sorting uses numeric values, never formatted strings, and preserves selection by task ID. Search and project filtering remain local. Token units reuse the existing M / 100M preference and appear in each value.

Totals mean all available local records for that task, not account-wide or cross-device totals. Tokens sum nonnegative cumulative-counter deltas, including cache inputs already in total_tokens; counter resets start another segment. Forked tasks exclude inherited events before creation while retaining a pre-creation token baseline. When that baseline is missing, omit the ambiguous first counter and show a lower bound; round displayed lower bounds down, with the exact known count in the tooltip. Turns counts distinct execution turns with a start record, not tool calls or individual assistant messages. Run time sums paired start/end intervals plus the currently verified running interval, excluding gaps between rounds. Incomplete lifecycle records show a lower bound, not invented hours. Unsaved side chats cannot contribute lifetime totals.

The existing daily and reset-period statistics keep their scope. They must not be repurposed as lifetime totals. Reuse the event parser and Provider worker; add a bounded, incremental history index only while the finder is visible. Process chunks within a small per-loop time budget. Persist offsets, counter baseline, aggregate duration, turn identifiers and file identity in the app data directory, without conversation content. Cache survives restarts; appends are incremental, truncation/replacement/fork-boundary changes invalidate the affected record. Persist periodically and on shutdown, not every UI frame. Missing/unreadable files remain unknown; new indexes show progress until ready. Canonical logs are never modified.

## Settings

Replace the long ungrouped form with a compact settings window organized into Appearance, Indicators, and General. Reuse Qt and existing fonts/colors, with aligned rows, subtle group surfaces and clear switch states. Position/theme options remain immediate; show topmost only for floating mode. Keep language, startup and update controls together in General. Preserve every existing preference and callback; no new account actions or telemetry. Layout must fit shorter screens through scrolling, and all four languages must remain readable.

## References and boundaries

- [Microsoft settings guidelines](https://learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings): grouped related options, right-aligned controls and immediate feedback. Apply the layout principles in Qt without migrating frameworks.
- [ccusage Codex](https://ccusage.com/guide/codex/): local session usage as a useful report surface; retain explicit token semantics rather than estimating subscription dollars.
- [CodexBar provider architecture](https://github.com/steipete/CodexBar/blob/main/docs/provider.md): separate source-specific collection from shared presentation. Future sources need real adapters and fixtures, not just extra branded controls.
- [TrafficMonitor taskbar integration](https://github.com/zhongyang219/TrafficMonitor/wiki/Taskbar-Window): study native taskbar behavior and its limitations; do not copy a Windows embedding technique into macOS/Linux.

## Verification

Test full-history deltas, duplicate starts, counter resets, inherited forks, partial lines, missing interval endpoints, live duration, restart cache reuse, file truncation/replacement and processing limits. Test numeric sorting both directions with unknown values, filtering/selection and units. Verify settings preservation and keyboard controls in four languages, render current controls before/after and review compact layouts. No real reset consumption, global mouse input or focus-stealing tests.

# Product clarity and attention

## Objective and scope

Help Windows Codex users understand capacity, notice tasks requiring action and return to the right task. Retain Qt, the existing Provider, account/token calculations, native reset confirmation and the opaque visual surfaces. This coherent batch follows the 2026-09-12 product review. It changes presentation, validity handling and preferences; it does not add signal inference, telemetry or a new provider.

Apple Design principles govern this batch: immediate pressed feedback, direct dragging, interruptible transitions, restrained motion, progressive disclosure and reduced-motion support. Keep the established font and readable opaque panels. Do not add decorative glass, momentum throws, sounds or continuous shimmer.

## 1. Quota validity and meaning

- All quota surfaces use one read-only validity projection. A window with a known reset time at or before now is expired and cannot supply a current balance, countdown or next-reset value, regardless of whether an error has already arrived. Unknown reset times are retained as unknown, not invented. Do not mutate the raw snapshot or historical chart boundary when deriving current values.
- The status strip, 5h details and reset panel must agree. A previously opened 5h panel refreshes to unknown when its window expires; it must not continue showing the old remaining percentage or imply a new cycle. Retain a 5h entry as unknown if the raw snapshot proves that capability, until a new successful snapshot removes that window kind.
- Preserve valid cached readings on quota-read failure, but show a quiet, non-blinking `Cached` indicator near the metrics. Quota tooltips and relevant panels state `Account quota` and the last successful local update time; when no successful time is available, say so. Other task-metadata errors do not falsely label successful quota data as failed.
- Strip labels visibly distinguish remaining (`Week left`, `5h left`) from observed consumption (`Today used`). Rotation keeps a stable measured label/value slot in every language; multiword labels must not be split using the first space. Unknown remains `—`.
- Week and Today retain their existing local Token destinations, explicitly titled `Local cycle · Tokens` and `Local today · Tokens`. Each includes a compact account-quota context line, so the entry percentage is distinguished from the local Token breakdown. The Today context says when quota observation began today; absent/partial coverage is not described as a complete day. Do not estimate missing usage or change reset-delta arithmetic.
- Publish `daily_observed_at` from the first valid quota sample in the current local day, excluding future samples and following the existing baseline requirements. This is display metadata, not a new sampling source or ledger.
- The inferred `official` reset classification remains unchanged in stored data for compatibility, but its visible name becomes `Other recovery` rather than `Official`. Its explanation states that the source is unconfirmed. Scheduled and confirmed in-app Manual remain distinct.

## 2. Independent windows and defaults

- `show_tasks` now controls the original strip's task status counts. Add independently persisted `show_task_strip` for the Running task strip. Turning either off must not change the other or the Provider state.
- Fresh settings default to status counts enabled and the Running task strip disabled. For an existing settings file with a valid old `show_tasks` value and no new key, initialize `show_task_strip` from that old value, preserving the previously experienced presentation. Respect an explicitly stored new boolean thereafter. No destructive migration or position reset.
- Settings name these controls `Task status counts` and `Running task strip`. Label the original strip's placement `Status bar placement`, and the shared topmost setting `Keep floating windows on top`. Its scope covers whichever floating windows are enabled. Color/transparency continue to apply to both.
- Fit the status strip to its actual labelled content, not the old arbitrary 540 DIP maximum. Request that complete minimum width from the taskbar; the taskbar helper still respects real system-button boundaries. Floating status width is constrained by the screen's available area. If the complete content cannot fit, keep its tray/menu route available instead of clipping off status controls. Do not silently enable quota rotation or hide selected indicators. Fresh settings use Auto placement; preserve existing valid Taskbar/Floating/Auto choices. Stored reference widths remain positive integers and are clamped to the current screen when restored. The independent task strip remains 420 DIP.
- Preserve the independent position, 420×30 DIP dimensions, drag threshold and guarded navigation implemented for the task strip. No Running tasks means it hides; Needs input and other categories remain in the original status view and finder. Do not change the observation coverage of task states.
- Give Needs input a visible text label with its count instead of relying on a question mark alone. Other status counts retain compact markers and complete tooltips. Add a standard `Task status` submenu to the existing tray/context menu, after Find task, exposing available category names and counts through normal QAction controls. It opens the same existing category panels and supports native keyboard navigation. No global shortcut or activation on background refresh.
- Give the self-painted strips descriptive accessible names containing their visible purpose/state. Full screen-reader compliance and hardware accessibility claims remain unverified until actually tested.

## 3. Find tasks first, disclose statistics

- The finder defaults to Project, Task, Status and Last active. Keep the existing search, project filtering, stable task identity, keyboard navigation, unknown-state handling and exclusion of ephemeral Side rows.
- Add a checkable `History statistics` control with accessible name, tooltip and keyboard focus. When expanded, reveal Run time, Tokens, Turns and the existing unit control in the same table. Preserve every calculation and cache. A `show_task_statistics` preference saves this explicit choice; default false, including upgrades because there was no prior visibility preference.
- The history index runs only while the finder is visible and statistics are expanded. Hiding the finder or collapsing statistics pauses the existing worker's index budget. No scan, progress wording or metric-related visual updates in the simple view.
- Preserve query, filter, selection and scroll while revealing/collapsing columns. If a metric column was the sort key when statistics are hidden, return to Last active descending so a hidden metric does not control the simple results. Reopening the expanded view retains the user's visible-mode choice.
- Disclosure is immediate; do not animate table row positions, scale text or block keyboard input. Keep existing responsive screen bounds and short-window scrolling.

## 4. Purposeful motion

- Remove the continuously sweeping title highlight and breathing Running markers from the two strips and task lists. Running remains legible through static semantic color and labels.
- Retain existing interruptible panel/selection springs, pressed feedback, stable task carousel transitions and direct 1:1 dragging. Long titles move only during deliberate hover. Task changes and marquee must not compete; reduced motion remains static/readable.
- Stop the shared 33ms animation timer when no visible marquee needs it. Existing Qt property animations may run for a bounded transition. Static Running data alone is not a reason to repaint continuously. No new timer, polling, thread or input hook.

## 5. Verification and delivery

Focused tests cover validity before/after expiry with/without quota errors, preserved raw snapshots, optional 5h capability, midnight/future observation samples, context labels, cache freshness, inferred reset wording, all four languages and long labels. Test fresh/legacy/explicit window preferences, independent toggles and position preservation; standard menu category actions; finder disclosure, sorting/selection and index pause/resume; idle timer behavior, hover, interrupted transitions and reduced motion.

Run the full desktop suite and the separate offscreen widget journeys. Render normal/unknown/stale/expired panels, settings and basic/expanded finder using current code and synthetic data; inspect actual source and installed windows without real pointer control. Real reset consumption is forbidden. Build via scripts/package.ps1; verify upgrade settings, actual system Run/uninstall registration and bootstrap cleanup. Record genuine hardware/real-pointer/user-testing gaps explicitly.

Deliver in small reviewable commits: this spec; quota data projection; quota presentation; independent controls/motion; finder disclosure; integrated verification/docs; one cohesive release. Prior completed floating-strip work is committed separately. Version, installer and tag are prepared together after integrated acceptance. Publish only to GitHub dicksick22046/codex-taskbar-companion, never replace an existing release asset.

## 6. User validation

Prepare a ready-to-run, consent-based usability protocol for five unfamiliar Codex users: interpret quota and freshness, find a task needing input, recover an older task, and hide Running titles while retaining status. Record comprehension, task success/time, missed state changes and obstruction/disable feedback. No telemetry is added. Recruiting and actual observations require willing participants and cannot be replaced by simulated agents or automated tests. Engineering delivery may be completed while this study remains explicitly pending; do not claim validated productivity or default-preference outcomes.

## Execution status

- [x] Quota validity and observation metadata
- [x] Quota meaning, freshness and reset-source presentation
- [x] Independent controls, accessible state entry and quiet motion
- [x] Basic finder with optional historical statistics
- [x] Integrated tests and visual verification
- [ ] Upgrade/install verification, documentation and release
- [x] Usability protocol ready; real participant study reported separately

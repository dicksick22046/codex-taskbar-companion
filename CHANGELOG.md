# Changelog

**English** · [简体中文](docs/i18n/CHANGELOG.zh-CN.md)

## Unreleased

- Replace the oversized hand-drawn pin with a standard compact Lucide icon; align it with panel headings, retain the hit area, and fix light-capsule/dark-panel contrast and focus feedback.

## 0.10.0

- Pin any task status from its list into one connected multi-row panel; each row rotates independently and supports hover feedback and direct unpinning.
- Migrate the former Running strip preference and remove its separate display switch and drag position.
- Place usage sums beside their periods; simplify reset history, distinguish Official in purple, and show recorded pre-reset quota percentages when available.
- Show an on-demand, attributed community reset forecast with a time window and approximate probability; hide unavailable or stale forecasts.
- Clarify daily-consumption labels and multilingual quota terminology.

## 0.9.0

- Show consistent unknown values for expired quota across the strip and open panels, with cached-reading and update-time context.
- Distinguish remaining account quota, observed daily consumption and local Token statistics; show the observation start and label unconfirmed reset sources as Other recovery.
- Control task status counts and the optional Running task strip independently. New installations use Auto placement; upgrades preserve previous display choices.
- Add named task-status actions to the tray/context menu, including when the status strip cannot fit on screen.
- Default task search to a simple four-column view. Reveal lifetime statistics on demand and pause history indexing when they are hidden.
- Remove continuous Running shimmer and breathing; retain direct dragging, interruptible feedback and deliberate long-title scrolling.
- Fit complete labels within actual taskbar/screen bounds and improve long settings labels in all four languages.

- Move the running task carousel into its own draggable floating strip with a saved position; keep quota indicators, status counts and their menus on the original strip.
- Keep temporary Main/Side distinctions in the strip and status lists; show ordinary tasks once without role labels in daily Token statistics and task search.

## 0.8.1

- Show Main tasks and Side chats independently, with separate status counts and durations; Side entries return to their parent task.
- Read current Codex unread records for the signed-in identity and local host, while retaining support for the legacy format.

- Clear stale running side chats when Codex reports session inactivity, including when no completion notification appears. Preserve explicit interruption and native unread state.
- Compare task activity timestamps by instant so side chats with different timezone offsets cannot displace newer main-task activity.

- Show partial task totals and indexing progress while local history is being processed; retain cached work across restarts.
- Skip unrelated log payloads when indexing lifetime statistics, reducing processing time for large task histories without increasing the polling frequency.

## 0.8.0

- Add Auto placement: prefer the primary taskbar, fall back to floating when space is unavailable, and return after availability stabilizes.
- Add floating-display selection, primary-display following and disconnected-display recovery without losing the saved relative position.
- Keep panels, menus and new utility windows on the resolved display; avoid automatic overlays over fullscreen foreground apps.

- Balance strip selection padding around rings and text, keep feedback inside clickable targets, and emphasize status pills without a second enclosing box.

## 0.7.0

- Rebuild settings with a persistent sidebar, clearer typography, balanced rows and direct placement/theme choices.
- Refresh task search, panel surfaces, unit selection and project labels while retaining the existing ring interpolation and rotation behavior.
- Apply settings to capsule geometry immediately; synchronize units, reset user-filter scrolling and preserve background selection.
- Keep interrupted selections continuous, settle hidden controls and honor keyboard/reduced-motion behavior.
- Add optional, grouped input-needed notices and visible recovery feedback for failed task navigation, startup and settings saves.
- Add Copy diagnostics with an explicit allowlist that excludes task content, accounts, paths and logs.

## 0.6.1

- Restrict setting changes to the switch itself; labels and row whitespace no longer toggle preferences.
- Commit unit, task and menu actions on release, cancel when dragged away, and keep the held task stable during rotation.
- Prevent passive scrolling from changing settings or task filters; support precision scrolling in popovers.
- Add keyboard navigation to task popovers, compact focus feedback, and native-window checks for covered strip clicks.
- Make switches and popovers reverse smoothly from their current motion; respect Windows animation settings and stop hidden animation loops.
- Refine tabs, pressed states and empty panels while retaining opaque backgrounds and the bundled font.

## 0.6.0

- Add sortable local lifetime run time, tokens and execution turns to task search, with M / 100M units.
- Index history incrementally while the search window is open, reuse cached offsets, and mark incomplete history as lower bounds.
- Group settings into Appearance, Indicators and General, with aligned controls and keyboard-accessible switches.
- Show an exclusive Needs input category for explicit unresolved synchronous input requests; stop the waiting task's generation animation and return to Codex to answer.
- Retain existing approval routing; automatic-review hooks are not treated as human approval prompts.

## 0.5.0

- Add Find task to the context menu, with local title/project search, project filtering and keyboard navigation.
- Include recorded Codex CLI execution and app-server sources in the existing catalog, deduplicated by task ID.
- Keep the full search catalog in memory and localize untitled task labels.
- Reuse font configuration during rendering while keeping returned font objects independent.

- Fit the capsule to its content in both placements, retaining the existing maximum width and a stable width across rotating tasks.
- Preserve the floating left anchor when content shrinks; keep task panels readable independently of capsule width.

## 0.4.0

- Add an optional floating capsule with drag positioning, screen-relative position restore and a keep-on-top setting.
- Keep floating panels within the available screen, opening above or below the capsule; scroll long reset histories without moving the action button.
- Allow settings to scroll on shorter screens.

- Avoid unchanged strip repaints and repeated settings updates; limit running animations to the task area.
- Write diagnostic snapshots every 30 seconds and on shutdown, while keeping live data and quota/reset persistence unchanged.

## 0.3.3

- Increase left padding inside the capsule so the first ring is clear of its edge.

- Add a fixed capsule background with manual dark/light colors and background transparency controls.
- Recover native visibility and Qt surface state after an unexpected hide; keep context menus above the strip and taskbar.
- Hide the taskbar divider when the left-side indicators rotate.
- Align reset-history labels, numeric values, and units in separate columns.
- Use 100M consistently for reset-history totals; retain the unit on every row.
- Left-align rotating values in a compact column after their labels, retaining the ring position.
- Shorten the cycle-usage heading to “Cycle · Tokens” and update the translations.
- Tighten the rotating slot to the current countdown format, retaining the ring position and stable width between rotations.

## 0.3.2

- Align rotating values to the right edge so the divider has equal spacing on both sides.
- Include the reset countdown in rotation. All enabled left-side indicators share one fixed-width slot.
- Include completed side chats in their parent task's unread status, using Codex's child-session unread IDs.
- Show each reset event's quota window even when the current account has only one window.
- Put the usage label and unit on each reset-history row, separate it from the category, and use blue category text.

## 0.3.1

- Correct reset history to chronological order: older events first (September 7 above September 8).

## 0.3.0

- Sort reset history by event time, newest first, including records added out of order.
- Add English, Simplified Chinese, Japanese, and Spanish UI selection, applied immediately and saved between launches.
- Add optional quota rotation in a fixed slot. Keep the countdown separate, pause while reading or clicking, and use continuous text and ring transitions.
- Restyle the language selector and use consistent short labels in parallel and rotating layouts.
- Add optional hover-to-open panels with entry and exit delays.
- Use a separate Side badge and retain confirmed side-chat links when the strip restarts.
- Restore the strip if Windows places the taskbar above it, without activating the window.
- Select the reset credit with the earliest expiry. Use 100M for historical token totals and a more compact reset panel.
- Unify missing-value styles. Rewrite public documentation in English with translated READMEs and a Chinese changelog.

## 0.2.4

- Classify resets as Scheduled, confirmed Manual, or inferred Official; recalculate older records when supporting data exists.
- Keep the pointer cursor over daily unit controls during refresh. Hovering does not change the selected unit.
- Handle input across each full taskbar control, including transparent gaps. Preserve rotation progress after hover and panel closure.
- Count an active side chat as activity in its parent task, with a Side chat label and no duplicate count.
- Add locally recorded token totals to reset-history intervals and simplify their colors.
- Move application code into a package and tests into tests/, remove outdated notes, and document architecture and review results.

## 0.2.3

- Use opaque dark panels instead of translucent backgrounds.
- Restore daily and cycle usage headings, with dates, totals, and unit controls on a separate row.
- Reorganize the reset panel with English labels, aligned dates, and a separate reset button. Show only the date when the source cannot be established.

## 0.2.2

- Avoid treating small reset-time adjustments as reset events; show when the source is not established.
- List every available credit's expiry, with one default reset action and confirmation.
- Add the daily period, token total, and unit controls. Remove the idle Tasks placeholder.
- Keep task rotation running when a panel is open; hovering a task still pauses it.
- Darken the shared translucent panel background for readability.

## 0.2.1

- Stop the time areas in the 5h and reset panels from activating weekly chart unit controls.

## 0.2.0

- Open separate panels from weekly quota, daily usage, status counts, and the countdown. Task titles open the corresponding Codex task.
- Group the daily list by status and show today's tokens; status lists show current or latest turn duration.
- Add a 5h balance history using existing samples.
- Store reset history per account. This version selects the newest valid credit and requires confirmation before use.
- Prevent duplicate reset submissions, reuse the same request after uncertain results, and retain observed daily usage before a reset.

## 0.1.5

- Complete installation outside an isolated host when required, so startup registration works from Windows sign-in.
- Add a consistent gap above the taskbar for both panels.
- Add regression coverage for token increments across midnight and restarts; keep the existing measurement rules.

## 0.1.4

- First public release, with installation instructions, a preview, and an issue-reporting link.
- Move updates to dicksick22046/codex-taskbar-companion.

## 0.1.3

- Stop dimming metrics after a temporary quota read failure.

## 0.1.2

- Avoid clearing all quotas after temporary read failures.
- Handle quota and task reads separately. Retain valid records, but do not reuse a balance from an expired window.
- Record which read failed without increasing polling frequency.

## 0.1.1

- Fix different data directories being used when launched from Codex and from Windows sign-in.
- Merge existing quota history into one persistent location and preserve the day's baseline after restarts.
- Write quota history atomically.

## 0.1.0 — Release candidate

- Add the single-row Codex taskbar strip and separate usage and task panels.
- Detect weekly and 5-hour windows, with five display switches and access through the system tray.
- Show daily task duration and tokens, unread results, and explicit stopped or failed states.
- Add per-user installation, startup, data migration, and settings retention across updates.
- Check GitHub releases, verify downloads, and install updates on request.

Full real-time error capture, macOS, and independent widgets on multiple monitors are outside the initial support scope.

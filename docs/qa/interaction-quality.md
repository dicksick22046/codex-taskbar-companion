# Interaction audit — September 2026

The reported full-row settings toggle exposed a mismatch between the visible control and its actual target. This audit covers settings, the strip, quota/reset/status popovers, task search, and the context menu. The governing contract is [interaction quality](../specs/interaction-quality.md).

## Findings and corrections

| Step | Severity | Observed problem | Corrected behavior / verification |
| --- | --- | --- | --- |
| 1. Change a setting | High | Clicking a caption toggled its checkbox and drew a full-row focus outline. | Separate noninteractive label and switch; pointer release inside commits, dragging out cancels. Tab/Space operate the switch with a compact focus cue. |
| 2. Scroll through settings or search | High | Collapsed choices and sliders could interpret scrolling as a value change. | Passive wheels leave preferences, filters and selected tab unchanged. Native popup lists still scroll. |
| 3. Change a quota unit | Medium | The parent panel executed the unit action on press. | Native exclusive buttons provide press feedback, release/cancel semantics and keyboard access. Their header targets cannot also open a task. |
| 4. Open a task or menu | High | Task metadata/motion could change under a held press; global interception did not verify native occlusion. | Freeze the held task and transition, retain its ID, cancel outside release, and check the actual window at the pointer. Right-click menus commit on release. |
| 5. Browse task popovers | Medium | No row keyboard navigation; discrete wheel steps lost precision input. | Up/Down/Home/End and Enter/Escape work; selection stays visible, Home restores the heading, pixel scrolling is preserved. Scrolling cancels pending navigation. |
| 6. Reverse or disable motion | Medium | Popover transitions restarted motion; switches had no continuous state movement. | Critically damped switches/popovers retain current value and velocity on reversal. Windows reduced-animation settings snap to readable static states; hidden loops stop. |
| 7. Read empty and focused states | Medium | Empty cycle data could display an invented date range; empty 5h charts lacked explanation. Some controls lacked clear focus feedback. | Localized empty/loading messages, unknown period shown as a dash, control-sized focus/press states, and a consistent tab surface. |

## Evidence

- 216 Windows tests pass, including targeted synthetic press/release/cancel, wheel, keyboard, occlusion, motion-reversal and reduced-motion cases. Settings callbacks and navigation are mocked where they have side effects.
- Native Qt screenshots reviewed before/after at matching sizes: all settings tabs, English/Chinese/Japanese/Spanish compact layouts, light/dark and parallel/rotating strips, cycle/daily/5h/reset/status panels, finder and menu. Switch motion and keyboard focus were also rendered separately. [Current settings example](../images/settings.png) uses controlled data.
- Existing tests continue to cover floating drag offset, screen bounds, adaptive width, long reset-history scrolling, search sorting/filtering, and reset confirmation with a fake provider.
- No real pointer control, foreground activation for test interactions, real task navigation or reset redemption was used.

## Remaining validation limits

Synthetic events and native renders do not establish real-device end-to-end accessibility. Screen-reader exposure of custom-painted strip/popover content, real touchpad hardware, mixed-DPI multi-monitor behavior, and other operating systems require separate device testing. This audit does not claim those are complete.

# Interaction audit — September 2026

The reported full-row settings toggle exposed a mismatch between the visible control and its actual target. This audit covers settings, the strip, quota/reset/status popovers, task search, and the context menu. The governing contract is [interaction quality](../specs/interaction-quality.md).

The 0.6.1 pass was insufficient: subsequent user feedback exposed unbalanced control clearance and geometry frozen while settings were open. Acceptance was reopened around complete flows, followed by the [visual rebuild](../specs/visual-refresh.md). Test counts alone did not establish design quality.

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
| 8. Adjust settings continuously | High | Geometry stayed wide while settings were open; first-row spacing and inherited fonts were inconsistent. | Real setting callbacks resize immediately, with balanced control rows, explicit typography and sidebar navigation. |
| 9. Filter, change units and retry | Medium | User filters retained old scroll positions; units lagged between views; failures could appear successful. | User filtering returns to the top; units synchronize immediately; independent errors persist until their operation recovers. |
| 10. Interrupt new navigation controls | Medium | Same-index refresh cancelled motion, hidden segments could stay halfway, and rapid navigation restarted fades. | Real callback/hide/retarget tests protect current presentation; keyboard and reduced-motion actions settle without animation. |
| 11. Notice waiting work and report problems | Medium | A glance-only signal was easy to miss; raw troubleshooting data was difficult to share safely. | Optional deduplicated notices and explicit allowlisted diagnostics, tested with a fake tray and clipboard. |

## Evidence

- 234 Windows tests pass; the separate offscreen journey class is skipped in that run and its three visible-widget journeys pass in a dedicated run. Qt window-level test events cover hit routing and wheel propagation; real setting/layout callbacks execute while OS and persistence side effects are isolated.
- Native Qt screenshots reviewed: all sidebar pages in English/Chinese/Japanese/Spanish, compact layouts, light/dark strips, cycle/daily/5h/reset/status panels, finder and menu. [Current settings example](../images/settings.png) uses controlled data. Screenshots establish specific rendered states, not complete device-level behavior.
- A separate read-only motion audit found five caller-level issues in new controls. Those were corrected; ring interpolation, quota transition/dwell and the existing data/statistics/reset modules remain unchanged from 0.6.1.
- Existing tests continue to cover floating drag offset, screen bounds, adaptive width, long reset-history scrolling, search sorting/filtering, and reset confirmation with a fake provider.
- No real pointer control, foreground activation for test interactions, real task navigation or reset redemption was used.

## Remaining validation limits

0.7.0 is published. Main and version-tag Windows/Linux CI passed, including the dedicated offscreen journeys. The installed executable matches the build; preferences, startup registration, native visibility/hit window and relaunch checks passed. Public installer checksum and download checks passed.

The final desktop capture returned an entirely black screen and no foreground window after an idle period. This is not evidence of a successful installed pixel render. A quiet follow-up is scheduled to inspect only the companion after the desktop is available; it must not wake/unlock the computer or control the user's input.

Follow-up: desktop capture is now available. The installed 0.7.0 strip rendered correctly in a private, strip-only capture; its native hit window and unchanged foreground were confirmed. The periodic follow-up is paused. User feedback separately exposed selection padding: a ring had less than 1 DIP clearance on its left while text had much more on its right. The correction gives metrics approximately 5 DIP optical padding, preserves ring/layout coordinates, aligns targets with their feedback, and emphasizes status pills directly. It is tracked as an unreleased local fix; the original release is not rewritten.

The local correction also reserves end clearance for elided task titles. Commit b12ecd1 is installed as an unreleased 0.7.0 build, with preferences and relaunch preserved; the executable matches the local build. 237 tests, offscreen journeys and Windows/Linux CI pass. Selected/pressed/cancelled states were rendered at 100%, 125%, native 150% and 200% scaling; short and capped task titles were inspected separately. This fix does not create or replace a public release.

Synthetic events and native renders do not establish real-device end-to-end accessibility. Screen-reader exposure of custom-painted strip/popover content, real touchpad hardware, mixed-DPI multi-monitor behavior, and other operating systems require separate device testing. This audit does not claim those are complete.

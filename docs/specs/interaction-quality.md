# Whole-product interaction quality

## Predictable controls

Captions and blank settings rows never change preferences. Switches are separate right-aligned controls with their own compact keyboard-focus cue; mouse clicks do not produce a selected-row outline. Press feedback is immediate, while state changes commit on release inside the same control. Dragging out cancels. Collapsed choices, sliders and tab bars ignore passive wheel changes; keyboard actions remain available. No unrelated default action runs when Enter is pressed elsewhere.

Verify complete flows with the real layout/update callbacks, isolating only OS side effects and persistence. Every settings control has balanced vertical space to its row boundaries; card padding must not make the first row asymmetric. Display changes resize the capsule while settings stay open. Search query/project changes return results to the top; background refresh preserves selection and scroll. Unit changes update all open views immediately. A failed setting write or startup action must not leave the UI claiming success.

Quota unit tabs follow the same press/release/cancel contract. Unit targets cannot also be task-row targets, including while scrolling. Task navigation retains a stable ID across a press, and cancels if the release targets a different row. Overlay input must respect the native window actually under the pointer, so covered taskbar widgets cannot steal clicks.

## Feedback and motion

Use the existing typography and manual colors, with subtle filled press/open states, rounded control groups and consistent spacing. Keep the established opaque popovers. Apple-style refinement means predictable, brief, interruptible feedback, not decorative bounce or renewed background blur.

Switch and popover transitions start from the current presented value and retain velocity when reversed; use critically damped motion without oscillation. Rotation must not change the visible task beneath a held pointer. Floating drag remains one-to-one and retains its grab offset. Closed/hidden content does not run continuous paint timers. Respect the Windows client-area animation preference: retain static status indicators and readable labels while disabling nonessential movement.

## Content and scrolling

Support precision-wheel pixel deltas as well as discrete wheel steps. Scroll only content and keep interactive headers separate. Empty quota data must not invent a cycle date range. Empty task messages are localized. All popovers, menus and dialogs stay within their supported screen bounds. Reset still requires the existing explicit confirmation; no validation uses real reset credits.

## Audit coverage

Inspect settings (all tabs and controls), parallel/rotating strip in both placements, cycle/daily/5h/reset/status popovers, task search/sort/filter/navigation, context menu, empty/loading states, and active/interrupted motion. Use fresh native-control screenshots plus targeted event tests; no real pointer control or foreground takeover. Record findings, fixes, test evidence and remaining hardware/assistive-technology limits. Source guidance: [Apple Motion](https://developer.apple.com/design/human-interface-guidelines/motion), [Apple Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility).

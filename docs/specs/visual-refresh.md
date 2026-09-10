# Desktop visual and interaction refresh

## Direction

Rebuild the presentation rather than retain the 0.6 tabbed-form appearance. Reference Apple's [System Settings hierarchy](https://support.apple.com/guide/mac-help/change-system-settings-mh15217/mac) and [motion guidance](https://developer.apple.com/design/human-interface-guidelines/motion): persistent navigation, clear content hierarchy, quiet grouped surfaces, immediate control feedback and interruptible motion. Keep native Windows window management and the existing Qt runtime.

## Surfaces

- Settings: a persistent left navigation rail and a distinct content area, page heading, concise section labels, consistent grouped rows, right-aligned controls with equal vertical clearance. Preserve all options. Short windows scroll content, not navigation. Show errors in context. Selection must work with mouse and keyboard.
- Search: a clear heading and scope, a unified search/filter toolbar, restrained numeric table with readable selection, sorting and empty states. Keep all lifetime metrics and selection/refresh behavior.
- Popovers: shared opaque elevated surface, consistent corner radius, keyline, heading/secondary text and a filled segmented unit selector. Keep compact single-row task content and reset confirmation.
- Strip: refine typography contrast, project/Side labels and status chips together, keeping existing indicator meanings, adaptive dimensions and manual light/dark/transparency settings.
- Motion: a short reversible selection/page transition, existing switch/popover springs and stable held targets. No text scaling or decorative perpetual motion. Reduced motion remains fully usable.

## Acceptance

Compare before/after screenshots from the real implementation at matching viewport, language and data. Review all four languages, compact/full layouts, populated/empty/loading/error states, dark/light strip and both placements. Exercise real callbacks through multi-step settings, filtering, units, navigation, close/reopen and failed actions. Tests must isolate only external side effects, not the layout/update functions under test. No real mouse or reset credit use.

Existing UI flow corrections in interaction-quality.md remain mandatory. Data collection, histories, reset policy and previously delivered statistics/attention features remain part of the regression run. Publish only after the redesigned installed build and complete flows are checked.

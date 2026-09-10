# Product review after the desktop rebuild

The tool should answer three questions quickly: how much quota remains, what needs attention, and how to return to the right task. Every extra control, collector and notification must justify its ongoing cost against those decisions.

| Decision | Evidence and disposition |
| --- | --- |
| Keep continuous rings and stable rotation | Existing interpolation/dwell behavior was explicitly valued. The six related method bodies remain unchanged from 0.6.1; data/statistics/reset modules also remain unchanged. |
| Rebuild settings instead of applying another skin patch | User feedback exposed both visual hierarchy problems and a missing continuous settings-to-strip flow. Sidebar navigation, direct choices, consistent fonts and live geometry are implemented. |
| Treat tests as evidence, not a taste score | Earlier static captures and isolated callbacks missed real friction. New tests exercise actual update/layout callbacks and visible offscreen widget journeys; native images are separately inspected. |
| Make attention useful without becoming noisy | Optional input notices default off, establish a baseline, group new waits and suppress resolved/unchanged work. They use the existing verified synchronous request state. |
| Make failures recoverable | Search remains open on navigation failure; settings show independent save/startup failures. Update notices open the relevant settings page. |
| Improve support without collecting more private data | Copy diagnostics is explicit and local. An allowlist replaces requests for raw logs; the issue template supports the report. |
| Clarify quota semantics without adding width | Tooltips distinguish weekly/5h remaining quota from today's consumption. Do not turn subscription use into speculative dollar costs. |
| Preserve background cost | No new collector or polling interval. Existing render-budget tests remain; hidden animation and notification-deduplication checks cover the additions. |
| Avoid duplicate controls and speculative presets | Existing display switches plus rotation already cover compact layouts. More presets would create settings that can conflict without solving a demonstrated problem. |
| Keep platform/mobile/provider expansion conditional | Mature references and architecture direction are recorded. Other desktop systems need actual device validation; mobile needs a reachable authenticated service and deployment context. No desktop support or deployed mobile service is claimed. |
| Keep accessibility work explicit | Native settings/search controls and popover keyboard navigation are improved. Full screen-reader acceptance for custom-painted content and mixed-DPI hardware still needs device-level validation. |

Execution and remaining boundaries are tracked in [the two-level plan](plans/product-quality.md). The target is a dependable small companion, with coherent releases and recoverable failures, rather than an expanding control panel for every possible AI workflow.

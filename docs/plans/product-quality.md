# Product quality execution

## 1. Desktop visual and interaction rebuild

| Item | Status | Completion evidence |
| --- | --- | --- |
| 1.1 Preserve ring interpolation, quota semantics, stable task/metric rotation and compact width | Required regression | Existing motion/data tests plus before/after frames |
| 1.2 Correct live settings geometry, row spacing, unit/filter synchronization and failure feedback | Implemented before redesign | Commit 3615810; 222 tests at that checkpoint; must pass again in new UI |
| 1.3 Rebuild settings with persistent navigation, explicit choices and shared typography | Implemented; installed acceptance pending | Four-language native renders, real callback tests and visible offscreen journeys |
| 1.4 Redesign search, popovers, menu and strip consistently | Implemented; installed acceptance pending | Native populated renders; existing empty/loading/interaction regression retained |
| 1.5 Independently audit motion and verify interruption/reduced motion/hidden timers | Implemented; final regression pending | Five vetted caller-level findings corrected; ring and quota motion retained |
| 1.6 Verify all multi-step flows, install, restart, data/preferences, CI and release | Pending | Real callbacks, isolated side effects; no real mouse/reset use |

## 2. Actionable attention and failures

| Item | Status | Boundary |
| --- | --- | --- |
| 2.1 Audit task-navigation, startup, saving and update failure feedback | Implemented; final regression pending | Independent failures persist until their own recovery; search remains open on navigation failure |
| 2.2 Optional input-needed notification, grouped and deduplicated | Implemented; final regression pending | Default off, no startup backlog; one-second grouping; fake-tray click tests |
| 2.3 Recheck input/approval evidence boundaries and documentation | Queued | Asynchronous/ephemeral questions and human approval are not fully covered |

## 3. Product review and next decisions

Evaluate whether each addition reduces missed work, prevents mistakes or improves recovery enough to justify its permanent complexity. Record a disposition and evidence for each candidate before implementation.

Current review selects two small additions: clarify remaining/consumed quota in tooltips without widening the strip, and provide user-initiated, allowlisted support diagnostics for recurring visibility/startup reports. Neither needs a new collector or server. Keep the ring animation, stable rotation and shared Provider. Other-platform claims and broad approval detection remain gated on actual evidence; a mobile backend is not a prerequisite for a useful desktop companion.

- Clarity of remaining quota versus today's consumption at a glance.
- Empty/first-run/reconnection behavior and preservation of previous useful data.
- Lightweight support diagnostics for recurring visibility/startup problems, without exposing account or task data.
- Background work when windows are closed, idle or animations are disabled.
- Keyboard and assistive-technology access to custom-painted content.
- Platform adapters and provider extensions: mature references already recorded; desktop compatibility still needs actual target devices.
- Mainland-accessible read-only mobile view / WeChat: analysis only, requires a reachable authenticated service and deployment context.

## Previously delivered work

Floating mode, adaptive sizing, performance throttling, local task search, lifetime tokens/run time/execution turns, sorting, and explicit synchronous Needs input are implemented. UI acceptance has been reopened by user feedback. The old 0.6.0 candidate was superseded by public 0.6.1; it is not an outstanding publication task. Other-platform support, broad approval detection and mobile deployment have not been delivered.

# Product quality execution

## 1. Desktop visual and interaction rebuild

| Item | Status | Completion evidence |
| --- | --- | --- |
| 1.1 Preserve ring interpolation, quota semantics, stable task/metric rotation and compact width | Required regression | Existing motion/data tests plus before/after frames |
| 1.2 Correct live settings geometry, row spacing, unit/filter synchronization and failure feedback | Implemented before redesign | Commit 3615810; 222 tests at that checkpoint; must pass again in new UI |
| 1.3 Rebuild settings with persistent navigation, explicit choices and shared typography | In progress | Four languages, compact/full screenshots and full control journeys |
| 1.4 Redesign search, popovers, menu and strip consistently | Pending | Matching before/after states; populated/empty/loading/error paths |
| 1.5 Independently audit motion and verify interruption/reduced motion/hidden timers | In progress | Vetted motion findings; frame review; retain good existing behavior |
| 1.6 Verify all multi-step flows, install, restart, data/preferences, CI and release | Pending | Real callbacks, isolated side effects; no real mouse/reset use |

## 2. Actionable attention and failures

| Item | Status | Boundary |
| --- | --- | --- |
| 2.1 Audit task-navigation, startup, saving and update failure feedback | In progress | No silent success; contextual recovery without repeated alerts |
| 2.2 Optional input-needed notification, grouped and deduplicated | Queued | Existing verified synchronous request state only; reuse polling; simulated notification tests |
| 2.3 Recheck input/approval evidence boundaries and documentation | Queued | Asynchronous/ephemeral questions and human approval are not fully covered |

## 3. Product review and next decisions

Evaluate whether each addition reduces missed work, prevents mistakes or improves recovery enough to justify its permanent complexity. Record a disposition and evidence for each candidate before implementation.

- Clarity of remaining quota versus today's consumption at a glance.
- Empty/first-run/reconnection behavior and preservation of previous useful data.
- Lightweight support diagnostics for recurring visibility/startup problems, without exposing account or task data.
- Background work when windows are closed, idle or animations are disabled.
- Keyboard and assistive-technology access to custom-painted content.
- Platform adapters and provider extensions: mature references already recorded; desktop compatibility still needs actual target devices.
- Mainland-accessible read-only mobile view / WeChat: analysis only, requires a reachable authenticated service and deployment context.

## Previously delivered work

Floating mode, adaptive sizing, performance throttling, local task search, lifetime tokens/run time/execution turns, sorting, and explicit synchronous Needs input are implemented. UI acceptance has been reopened by user feedback. The old 0.6.0 candidate was superseded by public 0.6.1; it is not an outstanding publication task. Other-platform support, broad approval detection and mobile deployment have not been delivered.

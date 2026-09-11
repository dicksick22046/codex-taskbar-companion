# Product quality execution

## 1. Desktop visual and interaction rebuild

| Item | Status | Completion evidence |
| --- | --- | --- |
| 1.1 Preserve ring interpolation, quota semantics, stable task/metric rotation and compact width | Verified in 0.7.0 | Six motion method bodies and existing data modules unchanged from 0.6.1; regression passes |
| 1.2 Correct live settings geometry, row spacing, unit/filter synchronization and failure feedback | Verified in 0.7.0 | Real callback and geometry assertions pass in the rebuilt UI |
| 1.3 Rebuild settings with persistent navigation, explicit choices and shared typography | Delivered in 0.7.0 | Four-language native renders, real callback tests and visible offscreen journeys |
| 1.4 Redesign search, popovers, menu and strip consistently | Delivered in 0.7.0 | Current populated/compact/error renders and refreshed public examples |
| 1.5 Independently audit motion and verify interruption/reduced motion/hidden timers | Verified in 0.7.0 | Five vetted caller-level findings corrected; ring and quota motion retained |
| 1.6 Verify multi-step flows, install, restart, preferences, CI and release | Automated gates passed; published 0.7.0 | 234 tests, three window-level offscreen journeys, installed hash/relaunch/startup/preferences and main/tag CI |
| 1.7 Inspect installed strip pixels on an available desktop | Completed; follow-up paused | Desktop capture recovered; the installed 0.7.0 strip rendered with quota text, rings, counts and task content. Native hit/foreground checks passed. This confirms rendering, not that every interaction is defect-free; the reported selection issue is tracked below. |
| 1.8 Correct selection clearance across strip entries | Included in 0.8.0 | Approximately 5 DIP optical padding, complete nonoverlapping targets, existing-pill status emphasis and consistent short/elided-title end clearance. Originally delivered as local fix b12ecd1; now included in the coherent 0.8.0 release. Published 0.7.0 remains unchanged. |
| 1.9 Make large task-history indexing useful before completion | Released in 0.8.1 | Progressive lower bounds and byte progress; faster payload skipping with cache continuity. 250 native tests, four offscreen journeys, matching real-history aggregates, completed 115-task local index and installed restart checks. See [verification](../qa/progressive-statistics.md). |

## 2. Actionable attention and failures

| Item | Status | Boundary |
| --- | --- | --- |
| 2.1 Audit task-navigation, startup, saving and update failure feedback | Delivered and tested | Independent failures persist until their own recovery; search remains open on navigation failure |
| 2.2 Optional input-needed notification, grouped and deduplicated | Delivered and tested | Default off, no startup backlog; one-second grouping; fake-tray click tests |
| 2.3 Recheck input/approval evidence boundaries and documentation | Reviewed; boundary retained | Asynchronous/ephemeral questions and human approval remain unclaimed; no hook routing changed |
| 2.4 Reconcile stale Side state and separate Main / Side | Released in 0.8.1 | Native idle replay, current identity-scoped unread, independent counts/durations/navigation; 60 state combinations, 261 native tests, four offscreen journeys and installed state comparison. See [verification](../qa/side-chat-idle.md). Agent children and unobservable Side waiting/failure reasons remain outside coverage. |

## 3. Product review and next decisions

### Windows placement compatibility — current delivery

| Item | Status | Evidence |
| --- | --- | --- |
| Auto taskbar/floating fallback and recovery | Implemented | Stable-availability policy, fullscreen and interaction-lock tests |
| Floating display choice and disconnect/reconnect | Implemented | Legacy preferences, primary following, pinned/negative-origin screen fixtures and retained positions |
| Screen-bound menus, panels and utility windows | Implemented | Resolved-display bounds tests |
| Compact multilingual settings and real control flow | Verified in controlled environment | Four-language renders and offscreen window-level input |
| Primary-display installed build, CI and release | Delivered in 0.8.0 | 246 tests, four offscreen journeys, primary-display Auto/taskbar and floating owner/visibility checks, settings restoration, main/tag CI and public asset checks |
| Mixed-DPI multi-monitor hardware / Windows 10 / ARM64 | Not verified | Requires actual target devices; do not infer support from fixtures |

Evaluate whether each addition reduces missed work, prevents mistakes or improves recovery enough to justify its permanent complexity. Record a disposition and evidence for each candidate before implementation.

Current review selects two small additions: clarify remaining/consumed quota in tooltips without widening the strip, and provide user-initiated, allowlisted support diagnostics for recurring visibility/startup reports. Neither needs a new collector or server. Keep the ring animation, stable rotation and shared Provider. Other-platform claims and broad approval detection remain gated on actual evidence; a mobile backend is not a prerequisite for a useful desktop companion.

Both selected additions are implemented and tested in 0.7.0. The completed decision review is in [product review](../product-review.md). The items below retain their stated boundaries instead of being marked universally complete.

- Clarity of remaining quota versus today's consumption at a glance.
- Empty/first-run/reconnection behavior and preservation of previous useful data.
- Lightweight support diagnostics for recurring visibility/startup problems, without exposing account or task data.
- Background work when windows are closed, idle or animations are disabled.
- Keyboard and assistive-technology access to custom-painted content.
- Platform adapters and provider extensions: mature references already recorded; desktop compatibility still needs actual target devices.
- Mainland-accessible read-only mobile view / WeChat: analysis only, requires a reachable authenticated service and deployment context.

## Previously delivered work

Floating mode, adaptive sizing, performance throttling, local task search, lifetime tokens/run time/execution turns, sorting, and explicit synchronous Needs input are implemented. UI acceptance has been reopened by user feedback. The old 0.6.0 candidate was superseded by public 0.6.1; it is not an outstanding publication task. Other-platform support, broad approval detection and mobile deployment have not been delivered.

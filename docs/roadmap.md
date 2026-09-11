# Product roadmap

Help people notice what their AI tasks need and return to the right task, with quota visibility close at hand.

## Current delivery order

The first-level goals below are governed by the concrete second-level checklist in [product quality execution](plans/product-quality.md). Completing a single item is not the end of the work. Reconcile unfinished items before reporting completion or beginning another milestone.

1. **Desktop experience, attention and product review — delivered.** 0.7.0 and the subsequent local selection fix are recorded in the execution checklist.
2. **Windows placement compatibility — active.** Deliver automatic taskbar/floating placement and explicit floating-display selection, including disconnect/reconnect handling. See [the contract](specs/adaptive-placement.md).
3. **Broader platforms and signals — conditional.** Retain the recorded evidence requirements; do not claim untested operating systems or broad human-approval detection.

## 1. Reliable Windows companion — 0.4.0

- Measure and reduce idle rendering and diagnostic writes without slowing task or quota collection.
- Offer a floating capsule alongside the existing taskbar placement, sharing the same data and panels.
- Keep tray recovery, persistent preferences and reversible updates.
- Validate idle/active behavior, mode changes, dragging, screen constraints and installed startup. Windows 11 x64 remains the tested platform.

See [the milestone contract](specs/windows-companion.md). Ship a cohesive, verified batch; small commits are not separate releases.

## 2. Help users return to work — task finding in 0.5.0

- Task search and project filtering reuse the existing catalog; capsule width fits content without resizing on each rotation.
- Needs input now uses explicit persisted request/result pairs; asynchronous questions and human approval routing still need verified evidence. See [attention signals](specs/attention.md).
- Explicitly include recorded CLI, VS Code, app-server and execution sources, deduplicated by ID. Live input/approval visibility across clients still needs a verified source; see [the evidence boundary](specs/task-finding.md#waitingapproval-evidence-boundary).
- Keep notifications optional and grouped. Measure missed actions and incorrect notifications with users.

## 3. Expand where there is evidence

- macOS: native menu-bar presentation, with a real test partner before a support claim.
- Windows 10 / ARM64 and Linux: validate packaging and window behavior on actual target systems.
- A second provider and optional read-only remote status/notifications, driven by demand and available APIs.

Reference-driven choices and the mobile web / WeChat feasibility direction are recorded in [product references](product-references.md). Task search now includes sortable local lifetime metrics, and settings follow grouped control patterns from Windows guidance.

These platform/provider/mobile items remain staged candidates, not delivered capabilities. Mobile web and WeChat work so far is feasibility analysis only; no service has been deployed. A full chat client, remote approval execution and team administration are outside the current milestones.

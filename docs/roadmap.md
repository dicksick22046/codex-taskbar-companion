# Product roadmap

Help people notice what their AI tasks need and return to the right task, with quota visibility close at hand.

## 1. Reliable Windows companion — 0.4.0

- Measure and reduce idle rendering and diagnostic writes without slowing task or quota collection.
- Offer a floating capsule alongside the existing taskbar placement, sharing the same data and panels.
- Keep tray recovery, persistent preferences and reversible updates.
- Validate idle/active behavior, mode changes, dragging, screen constraints and installed startup. Windows 11 x64 remains the tested platform.

See [the milestone contract](specs/windows-companion.md). Ship a cohesive, verified batch; small commits are not separate releases.

## 2. Help users return to work — task finding in 0.5.0

- Task search and project filtering reuse the existing catalog; capsule width fits content without resizing on each rotation.
- Investigate reliable waiting-for-input and approval evidence before adding an attention inbox or notifications.
- Explicitly include recorded CLI, VS Code, app-server and execution sources, deduplicated by ID. Live input/approval visibility across clients still needs a verified source; see [the evidence boundary](specs/task-finding.md#waitingapproval-evidence-boundary).
- Keep notifications optional and grouped. Measure missed actions and incorrect notifications with users.

## 3. Expand where there is evidence

- macOS: native menu-bar presentation, with a real test partner before a support claim.
- Windows 10 / ARM64 and Linux: validate packaging and window behavior on actual target systems.
- A second provider and optional read-only remote status/notifications, driven by demand and available APIs.

These are staged candidates, not advertised capabilities. A full chat client, remote approval execution and team administration are outside the current milestones.

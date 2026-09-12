# Task finding

Lifetime metric columns and numeric sorting are specified in [task statistics](task-statistics.md); the read-only Needs input category is specified in [attention](attention.md).

## Scope and entry

Add **Find task…** to the strip/tray context menu, above Settings and Quit. Keep tray-left-click and second-launch Settings behavior unchanged. No global shortcut, extra strip icon, or automatic window opening. The task browser is a modeless window with a search field, project filter and single-line results. Opening a result uses the existing Codex task URL.

Search task titles and project names locally, case-insensitively, requiring every whitespace-separated search term to match. Project selection filters only this browser; quota numbers and strip counts remain account-wide. Keep the query/filter while the window is hidden in this session, without storing search history. List tasks by most recent stored activity, with deterministic ID tie-breaking.

Each row has a project tag, task title, known status if available and a compact activity timestamp. Keep titles elided with a full tooltip and use existing colors. Show no inferred status for catalog-only tasks. Keyboard arrows select and Enter opens; a pointer press/release must retain the same task ID when data changes. Preserve selection and scroll position on refresh when possible. No results should be a readable empty state.

## Data contract

Reuse the existing five-second catalog collection and single Provider. Publish a minimal in-memory `catalog` projection: ID, title, project, updated timestamp. No prompts, item bodies, paths or credentials. Exclude this projection from diagnostic snapshot persistence. Merge each ordinary task's existing state evidence in the browser; do not derive running or waiting state from `notLoaded`.

Explicitly query recorded `cli`, `vscode`, `appServer` and `exec` sources, excluding child threads using the existing parent rule. Deduplicate by task ID. These are local persisted Codex sources; no remote aggregation or live client subscription is implied. Additional previously omitted execution tasks can contribute their recorded local usage through the existing cursor logic.

Ephemeral Side chats are excluded from task search and lifetime statistics. Show each ordinary task once with its own state and recorded totals, without Main/Side labels or side-chat navigation metadata. Temporary Main/Side distinctions belong only to the strip and status-category panels; they do not add tasks to the persisted catalog or alter the parent's state or totals.

Render with a virtualized list. Reuse the UI tick while visible and avoid model resets when relevant data is unchanged. Filter without API calls. Browser actions never start/resume/interrupt tasks, approve commands or consume reset credits.

## Waiting/approval evidence boundary

The [official App Server documentation](https://learn.chatgpt.com/docs/app-server) describes runtime status notifications for loaded threads, including `waitingOnApproval`, and the `thread/loaded/list` query. Its stored thread listing defaults to `cli` and `vscode` when source filters are omitted.

A read-only probe on 2026-09-10 found 100 catalog tasks all `notLoaded` and zero loaded tasks in this tool's observer process, while the existing local-log path observed active work. Explicit source selection returned additional `exec` tasks. This verifies a coverage gap, but does not establish access to another client's live approval/input requests. Version 0.6 adds explicit persisted synchronous input request/result pairing as specified in [attention signals](attention.md). Human approval and asynchronous/ephemeral questions remain outside that coverage; never resume a user's task merely to subscribe to it.

## Verification

Test source parameters and pagination, ID deduplication, projection fields/diagnostic exclusion, search terms and Unicode, exact project selection, ordering, stable selection, click-target safety, keyboard navigation and translated empty states. Test with hidden widgets and mock navigation/reset APIs. Review synthetic renders at normal and constrained sizes. Real source probes are read-only and retain aggregate evidence only.

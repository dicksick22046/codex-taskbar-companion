# Read-only attention signals

## Needs input

Reuse the existing local log cursor to recognize a structurally valid `response_item` function call named `request_user_input` (optionally namespace-qualified), with a call ID and a nonempty questions list. Retain only call ID and timestamp, never question or answer text. A matching function-call output resolves it. A new turn, completion or interruption also clears the old request. Unrelated calls, malformed arguments and mere text mentioning the tool do not create a signal.

Only expose Needs input on a currently verified running task with an unresolved request in its own log. It takes priority over Running in category counts, without duplicating the task. The turn remains active for elapsed-time accounting, but its title/badge does not pulse as though the model were generating. Show an amber question mark and count, a dedicated task panel, and the same status in search/daily lists. Clicking still returns to the existing task in Codex. No automatic answers, approval decisions or keyboard injection are added.

This covers persisted synchronous input requests. It does not claim coverage of asynchronous app questions or ephemeral side-chat requests without saved records. Native Codex dialogs remain the place to answer.

## Optional desktop notice

General settings may enable input-needed notifications; default off. Reuse the existing UI snapshot check, with no new thread, polling or conversation storage. The first usable snapshot establishes a baseline without sending old notices. Enabling the option also establishes a fresh baseline. Batch newly waiting task IDs for one second, remove any already resolved IDs, and notify once per waiting interval. Unchanged data never repeats a notice.

Messages contain a count, not task titles or question text. Clicking a notice opens the remaining single task, or the waiting list for several; if none remain, open task search. When the strip is hidden, task search remains the fallback. Update notices open the General settings page. Delivery depends on Windows notification preferences, so the persistent Needs input category remains the primary signal. Tests use a fake tray and never trigger real questions or notifications.

## Approval boundary

The installed Codex schema includes PermissionRequest hooks, but the current input schema lacks a definitive human-routing field and tool-call correlation. Upstream [#28833](https://github.com/openai/codex/issues/28833) documents false notifications when requests go to automatic review; [#34836](https://github.com/openai/codex/issues/34836) requests correlation. Do not register another approval hook or interpret every hook as human action required. Existing user hooks remain unchanged.

The [Clawd on Desk limitations](https://github.com/rullerzhou-afk/clawd-on-desk/blob/main/docs/guides/known-limitations.md) and its public request/response fixture inform the read-only question approach. Implementation uses our cursor and metadata only, without copying its permission interception or remote approval behavior.

## Verification

Cover request/result pairing, unrelated outputs, multiple questions per call, malformed inputs, duplicate records, turn changes, interruption, restart replay, inherited forks and stale pre-boot work. Verify exclusive categories and no real question/approval creation, focus changes or reset consumption during tests.

# Side-chat idle reconciliation

Two ephemeral side chats remained marked running after they ended because the collector only recognized a shown completion notification or a successful interrupt response. This also kept an idle parent in the strip's running count.

Read-only inspection of installed Codex 26.903.9818 confirmed that its browser session registry logs `IAB_LIFECYCLE ended browser use session activity` when the native thread becomes idle. The renderer also requests this cleanup when interruption begins. The collector now consumes that metadata in the existing incremental desktop-log pass. It establishes inactivity, not a successful completion or a failure; later cleanup preserves an explicit terminal reason. Native unread membership remains necessary for an idle side chat to produce an unread badge.

An independent app-server observer returned `interrupted` for main tasks that the desktop still reported active. That observer result is not used to stop main tasks. Main and side activity timestamps are compared as instants, including mixed timezone offsets.

Verification covers missing completion notifications, restart replay, a later side turn, unrelated view activity, old idle events, preserved completion/interruption, native unread clearing and a main task continuing after its side finishes. Provider-level checks assert consistent running counts, panel membership and task-search state without opening tasks or consuming quota resets.

The adapter remains dependent on the observed desktop log format. It does not infer completion from an arbitrary period without tokens.

## Independent Main / Side status and unread migration

The subsequent user request replaces parent aggregation with separate Main and Side state items; Agent children remain outside this change. Sixty combinations cover main running/waiting/completed/stopped/failed and side running/idle/completed/interrupted, with unread present, absent or unavailable. Counts, panels and task search agree; Side durations use their own interval, tokens remain unknown and navigation returns to the parent. Main failures and waiting state do not transfer to Side.

The live desktop had removed its legacy unread field. Its current identity-and-host-keyed records were verified against installed source: hash the native identity fields and select the local execution host. The Provider obtains only the identity hash from an in-memory auth-status response on its existing thirty-second cadence. Tests cover identity changes with unchanged file contents, local/remote separation, unread clearing, unsupported formats, and no fallback to migration snapshots. A live read-only check successfully resolved the current native unread set.

261 native tests and four offscreen journeys passed, followed by 74 focused checks after role-label alignment. Hidden native Qt renders in all four languages were inspected; Main and Side have equal badge widths and aligned titles. No real pointer input, task execution or quota reset was used for these checks.

## Installed verification

Source `e19f701` passed Windows and portable-core GitHub CI. The local installed executable matches the build, retains settings and bundled assets, and relaunches visibly without changing foreground focus. A fresh installed snapshot reported two running main tasks and no running side chats; those two IDs matched the desktop's active tasks. The previously stale side chats were absent from Running. Category panels and task-search classifications matched the snapshot counts, and the strip capture/native hit check passed.

This batch was initially installed locally on the 0.8.0 baseline, then published in [0.8.1](https://github.com/dicksick22046/codex-taskbar-companion/releases/tag/v0.8.1). Side-chat waiting prompts and detailed failures remain limited by available metadata; they are not inherited from the parent or inferred from inactivity.

The 0.8.1 release commit is `0803ec8`. Main and tag CI passed, including the tag installer build. Local 0.8.1 installation, preserved preferences, relaunch visibility and native hit checks passed. The public installer and checksum were verified, and the update resolver recognizes 0.8.1 for clients on 0.8.0 while offering no update to 0.8.1 itself. Earlier release assets remain unchanged.

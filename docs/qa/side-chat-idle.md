# Side-chat idle reconciliation

Two ephemeral side chats remained marked running after they ended because the collector only recognized a shown completion notification or a successful interrupt response. This also kept an idle parent in the strip's running count.

Read-only inspection of installed Codex 26.903.9818 confirmed that its browser session registry logs `IAB_LIFECYCLE ended browser use session activity` when the native thread becomes idle. The renderer also requests this cleanup when interruption begins. The collector now consumes that metadata in the existing incremental desktop-log pass. It establishes inactivity, not a successful completion or a failure; later cleanup preserves an explicit terminal reason. Native unread membership remains necessary for an idle side chat to produce an unread badge.

An independent app-server observer returned `interrupted` for main tasks that the desktop still reported active. That observer result is not used to stop main tasks. Main and side activity timestamps are compared as instants, including mixed timezone offsets.

Verification covers missing completion notifications, restart replay, a later side turn, unrelated view activity, old idle events, preserved completion/interruption, native unread clearing and a main task continuing after its side finishes. Provider-level checks assert consistent running counts, panel membership and task-search state without opening tasks or consuming quota resets.

The adapter remains dependent on the observed desktop log format. It does not infer completion from an arbitrary period without tokens.

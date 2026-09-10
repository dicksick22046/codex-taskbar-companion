# Product references and next choices

## Reuse proven approaches

| Reference | What applies here | Boundary |
| --- | --- | --- |
| [TrafficMonitor](https://github.com/zhongyang219/TrafficMonitor/wiki/Taskbar-Window) | Windows taskbar compatibility checks and independent floating presentation | Native taskbar embedding has OS-specific limits; it is not a cross-platform UI technique. |
| [CodexBar provider guide](https://github.com/steipete/CodexBar/blob/main/docs/provider.md) | Separate provider collection, identity and capabilities from shared display | A quota adapter does not imply task-state or approval support. Add sources with real fixtures and explicit account boundaries. |
| [ccusage Codex reports](https://ccusage.com/guide/codex/) | Useful per-session local usage reports and clear source scope | Keep subscription quota and local tokens distinct; do not invent dollar spending from subscription use. |
| [Microsoft settings guidelines](https://learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings) | Related groups, aligned controls, immediate application of preferences | Apply these principles in Qt; a UI refinement does not require a framework migration. |
| [Clawd on Desk limitations](https://github.com/rullerzhou-afk/clawd-on-desk/blob/main/docs/guides/known-limitations.md) | Read-only request/result pairing for Codex input reminders | No question answering or permission interception. Current approval hooks can include automatic review. |

No third-party source implementation is vendored by this work. The runtime stays Python/Qt with existing dependencies.

## Cross-platform direction

Keep data interpretation portable and test it independently. Use native presentation adapters: tray/floating on Windows, menu bar on macOS, tray/floating according to Linux desktop support. Packaging, binary discovery, startup and updates need OS-specific implementations and target-system validation. Existing Windows behavior remains the supported delivery; Linux data tests are not a desktop support claim.

## Mainland-accessible remote summary

Recommendation: validate a small read-only mobile web view before a mini program or another remote-control client. The Windows app would explicitly opt into sending minimal state to an authenticated HTTPS service reachable from the user's phone. The phone reads that service, not the local Codex process. This can avoid requiring a VPN on the phone, provided the chosen service is actually reachable on the target mobile networks. The computer must remain online and retain its own working Codex connection.

Keep the first scope to task state, attention counts and usage summary. Exclude conversation bodies, account credentials, shell execution and remote approval. If Codex already satisfies the user's access needs, a parallel chat client adds little value.

A WeChat mini program can reuse the same backend after the mobile view proves useful. It still requires platform setup, configured server domains and backend operation; it only avoids maintaining separate native mobile clients. Tencent's [mini program integration guide](https://cloud.tencent.com/document/product/269/68378#) documents the server-domain configuration step. Registration, publishing and any applicable filing requirements must be checked for the actual deployment; no backend or mini program has been deployed by this work.

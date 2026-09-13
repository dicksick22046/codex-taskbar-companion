# Pinned status and reset details — 0.10.0

The [pinned-status contract](../specs/pinned-status.md) and [quota presentation contract](../specs/product-clarity.md) are included in release commit `7b6eff4`.

- Native suite: 322 tests, one offscreen-only skip; four window-level journeys passed separately. Focused checks cover pin migration, empty/reappearing states, per-row rotation, hover/press cancellation, connected geometry, reset percentages and forecast validation/throttling.
- Four-language native renders were inspected for connected surfaces, popup pin controls, concise rows, aligned history amounts, purple Official labels and nearby period sums. Public examples use synthetic data.
- The public forecast endpoint was read successfully without credentials. The comparison service returned null probabilities; its data was not substituted with a fabricated estimate. Unknown, stale, wrong-provider and malformed predictions are rejected.
- Local 0.10.0 installation matches the build, preserves normalized preferences and relaunches. The old enabled Running strip migrates to a pinned Running row. Native rectangles share left/right edges and overlap at the taskbar boundary as intended. A desktop crop was black; direct window-buffer captures succeeded and were inspected. No global pointer input or real reset credit was used.
- GitHub main and tag CI passed. The release's final tag, installer checksum and public download were checked; a 0.9.0 client recognizes 0.10.0 as an update. The temporary draft tag was removed after the release was associated with the verified version tag.

Historical percentages are last recorded account values, not exact closing measurements. Old manual history without a before snapshot remains blank. The community forecast is global and may have low confidence; it cannot promise a reset for an individual account. Physical multi-monitor hardware beyond existing validation remains unverified.

## 0.10.1 follow-up

[0.10.1](https://github.com/dicksick22046/codex-taskbar-companion/releases/tag/v0.10.1) is published from `7224de0`.

- 341 native regression tests passed, with one offscreen-only skip. Main and tag CI passed, including the installer build.
- English, Chinese, Japanese and Spanish settings and caption-on/off strip renders were inspected. Dark/light motion phase captures verify synchronized breathing, readable title highlights and stable targets. Source comparison confirms the pre-removal ring/quota animation methods and spring/control modules are preserved.
- A real offscreen Qt window with deliberately broken native ownership/topmost state recovered through its native event callback exactly once; no idle repair loop or foreground change followed. Combined popup geometry, expansion, menus and relative ownership have focused regression coverage.
- The installed executable matches the verified build. Normalized user preferences, actual startup registration and exit/relaunch are preserved. Read-only buffer captures and hit tests confirm the connected installed bar and pinned row are visible above the taskbar at inspection time.
- Installer SHA-256: `c41aa50a1d4ff5cd4cc8aeaf8f33145b0c5b023953b69d11142941afcd9c5e2c`. Public asset metadata, checksum and download prefix match; the updater detects this version from 0.10.0.

No real pointer input was injected. The user's intermittent taskbar-click occlusion remains a live recurrence check; offscreen recovery and a correct installed snapshot do not prove that every shell activation path is fixed. Old missing percentages now show a dash, while future in-tool manual resets retain their before snapshot.

## Unreleased reset overview and selection

The current design is delivered locally from `d836462`. Review scope: opening the reset panel, comparing periods, inspecting one period, navigating long history, and reaching reset-credit controls. This review used fresh native-widget captures with synthetic data; it is not a real-user usability study or screen-reader certification.

| Step | Finding and resulting behavior | Verification |
| --- | --- | --- |
| 1. Overview | Values share one row and columns share a baseline. Chart and footer spacing is 32 DIP shorter than the prior layout, with unchanged width. | Four-language default renders; complete labels at scrolling edges |
| 2. Inspect a period | Opening selects the latest history. Clicks and keyboard actions change the fixed detail line; hovering and scrolling leave the selection unchanged. Missing readings remain a dash. | Latest default, inert hover, pointer-down feedback, canceled clicks, stable IDs on refresh, interrupted motion and reduced motion |
| 3. Browse and act | Chart dragging cancels click selection; native scrollbar and arrow/Home/End keys remain available. Selected periods scroll fully into view; short screens retain access to credits and the reset button. | Direct widget drag/key/wheel tests, fixed-header pixel comparison and reset-request isolation |

Native regression: 355 tests, one offscreen-only skip; four separate offscreen journeys pass. Windows/portable CI pass. The installed executable matches the tested build, normalized preferences are preserved and native bar/pinned windows remain attached without changing foreground focus. Public 0.10.1 assets were not replaced.

The design uses selection to disclose details, as illustrated in [Apple's chart interaction guidance](https://developer.apple.com/videos/play/wwdc2023/10037/). The earlier intermittent shell-click occlusion remains a recurrence check; controlled rendering and a correct installed snapshot do not prove every shell activation path is fixed.

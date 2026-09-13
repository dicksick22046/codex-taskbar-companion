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

## Unreleased history chart

Commit `63d89fa` replaces the textual history with shared-scale horizontal Token bars and a separate recorded-quota column. Native regression: 345 tests, one skipped; main Windows and portable-core CI passed. Four-language renders cover explicit units and the old manual record's absent quota snapshot. A constrained 280-DIP screen test verifies scrolling in both placement modes, unchanged header pixels and a fixed reset button. Zero values and absent/invalid values produce no bar fill and retain distinct labels.

The local installation includes this development update, matches its build and preserves normalized preferences, startup/relaunch and native attached windows without changing foreground focus. The public version remains 0.10.1; its installer and checksum were not replaced. README examples use current synthetic data. The earlier shell-click recurrence limitation remains open.

The follow-up in `aa9e013` keeps each period on one 28-DIP line with an inline comparison bar, amount, unit, quota percentage and source. Four-language renders and 79 focused checks pass, including aligned baselines, column clearance and fixed-header scrolling. Main Windows/portable CI passed. The local installed build matches and preserves preferences; the Chinese four-row panel is 96 physical pixels shorter at the tested 150% scaling, with the same width. No new public version was issued.

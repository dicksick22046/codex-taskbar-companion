# Pinned status and reset details — 0.10.0

The [pinned-status contract](../specs/pinned-status.md) and [quota presentation contract](../specs/product-clarity.md) are included in release commit `7b6eff4`.

- Native suite: 322 tests, one offscreen-only skip; four window-level journeys passed separately. Focused checks cover pin migration, empty/reappearing states, per-row rotation, hover/press cancellation, connected geometry, reset percentages and forecast validation/throttling.
- Four-language native renders were inspected for connected surfaces, popup pin controls, concise rows, aligned history amounts, purple Official labels and nearby period sums. Public examples use synthetic data.
- The public forecast endpoint was read successfully without credentials. The comparison service returned null probabilities; its data was not substituted with a fabricated estimate. Unknown, stale, wrong-provider and malformed predictions are rejected.
- Local 0.10.0 installation matches the build, preserves normalized preferences and relaunches. The old enabled Running strip migrates to a pinned Running row. Native rectangles share left/right edges and overlap at the taskbar boundary as intended. A desktop crop was black; direct window-buffer captures succeeded and were inspected. No global pointer input or real reset credit was used.
- GitHub main and tag CI passed. The release's final tag, installer checksum and public download were checked; a 0.9.0 client recognizes 0.10.0 as an update. The temporary draft tag was removed after the release was associated with the verified version tag.

Historical percentages are last recorded account values, not exact closing measurements. Old manual history without a before snapshot remains blank. The community forecast is global and may have low confidence; it cannot promise a reset for an individual account. Physical multi-monitor hardware beyond existing validation remains unverified.

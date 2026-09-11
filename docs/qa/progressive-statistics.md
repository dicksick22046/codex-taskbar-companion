# Progressive task statistics

The task finder hid all lifetime metrics until each source file finished indexing. Large histories therefore appeared empty even after useful aggregates had been collected.

The fix exposes observed totals as lower bounds, adds byte progress and skips canonical records that cannot contribute to lifetime totals. Unknown envelope layouts still use the existing parser. Cache version 2 and saved offsets remain compatible; the Provider retains its existing 60 ms processing budget and polling cadence.

Verification on Windows 11 x64:

- 250 tests passed, with the offscreen-only class skipped in the native run; its four window-level journeys passed separately.
- Focused cases cover partial values, completion, historical open intervals, large skipped records across restart, old caches and unfamiliar envelopes.
- A read-only comparison on two large and two small local logs produced identical tokens, recorded run time, execution turns and incompleteness flags. Processing took 7.69 seconds before and 4.28 seconds after. This is processing time, not the full Provider's wall-clock time.
- Across 115 local sources and twelve 60 ms slices, processed bytes increased from 148.6 MB to 155.2 MB. The longest measured slice was 64.21 ms before and 65.66 ms after; chunk boundaries can slightly exceed the target budget.
- Hidden native Qt renders in English and Chinese were inspected for partial values, completed values, initial indexing and missing files. These checks used fixtures and did not control the user's pointer or redeem quota credits.

These measurements describe this machine and these histories, not a universal performance guarantee. Other operating systems and target devices remain outside this verification.

## Local delivery

Implementation `18cda54` follows [task statistics](../specs/task-statistics.md#task-statistics). Its Windows and portable-core GitHub CI jobs passed. A local build was installed and matched the built executable; preferences and bundled assets were retained, and relaunch restored a visible strip without changing foreground focus. The installed strip capture and native hit test passed.

During the companion's stopped update interval, its existing local index was completed in 24.19 seconds: all 115 available tasks had indexed tokens, recorded duration and turns, with no missing files. The index was saved before relaunch; conversation logs were read only. This is a local unreleased fix on the 0.8.0 baseline. Published 0.8.0 assets and tags were not replaced.

The fix is now included in public 0.8.1, together with the status and unread repairs. See [release verification](side-chat-idle.md#installed-verification).

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

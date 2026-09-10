# Local support diagnostics

General settings offers a secondary Copy diagnostics action. It copies a compact JSON report only on an explicit click, with a brief Copied confirmation. It does not upload anything or add a polling task.

Allow only application/version/platform/font, validated presentation preferences, window size/visibility/placement availability/animation preference, and booleans for loading/available quota/data errors. Exclude task titles, IDs, projects, account details, paths, log messages, credentials and conversation contents. Tests must seed such excluded values and verify they never reach a fake clipboard.

Quota tooltips explicitly distinguish weekly/5-hour remaining quota from today's consumption. This improves interpretation without adding width or changing data semantics. Existing ring interpolation and labels remain unchanged.

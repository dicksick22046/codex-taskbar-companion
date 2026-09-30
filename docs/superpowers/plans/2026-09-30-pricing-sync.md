# Event-Driven Pricing Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Trigger validated OpenAI Standard pricing checks after a client-version change or an unknown model observation, cache supplemental rates locally, and remove the daily schedule while preserving conservative USD semantics.

**Architecture:** Add a small pricing catalog/cache boundary used by `UsageCursor` and a background sync coordinator owned by `Provider`. The catalog keeps reviewed built-in rates, validated supplemental rates, and effective timestamps; the coordinator handles version/model triggers and atomic cache writes without blocking the Qt UI.

**Tech Stack:** Python 3.12, existing `urllib.request`, JSONL usage parser, SQLite-free local JSON cache, unittest, GitHub Actions.

**Spec:** `docs/specs/pricing-sync.md`

## Global Constraints

- Remote source is only `https://developers.openai.com/api/docs/pricing.md` Standard pricing.
- Unknown model IDs remain unknown until an exact validated row is available.
- Network work is background-only and never receives account or task contents.
- Existing built-in rates remain the offline fallback.
- Existing token/USD completeness and `None` semantics remain unchanged.
- No daily scheduled price check remains.

## Review Focus

- A version change must trigger one background check without delaying startup; test the marker update and retry behavior.
- A newly observed model must trigger one deduplicated check; test repeated usage events.
- Official table shape or numeric validation failures must preserve the prior catalog; test malformed rows and oversized responses.
- A cached rate must not retroactively reprice events before its effective timestamp; test boundary timestamps.
- Network failure and corrupted cache must leave existing USD totals and built-in rates usable; test atomic-write recovery.

### Task 1: Pricing catalog and validated cache

**Files:**
- Create: `codex_taskbar/pricing_catalog.py`
- Modify: `codex_taskbar/pricing.py`
- Test: `tests/test_pricing_catalog.py`

**Interfaces:**
- `PricingCatalog(runtime_dir: Path, app_version: str)` loads `pricing_cache.json`, exposes `rate_for(model: str, at: datetime | None)`, and records `observe_unknown(model: str)`.
- `PricingCatalog.merge_official(rows, fetched_at, app_version)` validates and atomically persists supplemental rates.
- `pricing.estimate_usd(model, usage, rates=None)` accepts an optional exact-rate tuple while preserving the current default behavior.

- [ ] Write failing tests for cache schema, exact model lookup, effective-time boundaries, atomic writes, and invalid data fallback.
- [ ] Run `python -m unittest tests.test_pricing_catalog tests.test_usage_cost` and confirm the new tests fail before implementation.
- [ ] Implement the catalog and optional rate injection without changing existing built-in-rate results.
- [ ] Run the focused tests and confirm all pass.
- [ ] Run `git diff --check`.

### Task 2: Official pricing fetch and event-driven coordinator

**Files:**
- Modify: `scripts/check_model_prices.py`
- Create: `codex_taskbar/pricing_sync.py`
- Modify: `codex_taskbar/provider.py`
- Test: `tests/test_pricing_sync.py`, `tests/test_provider.py`

**Interfaces:**
- `fetch_official_standard_prices(opener=open_url) -> dict[str, tuple]` reuses the strict Standard-table parser with size and timeout limits.
- `PricingSyncCoordinator(catalog, app_version)` exposes `on_version_start()` and `on_unknown_model(model)`; each returns immediately and schedules at most one background job per trigger key.
- Provider passes one catalog to each `UsageCursor`, records unknown model IDs from parsed `turn_context`, and refreshes the snapshot after a successful merge.

- [ ] Write failing tests for version-change triggering, unknown-model deduplication, fetch failure retention, and provider wiring.
- [ ] Run the focused tests and confirm they fail before implementation.
- [ ] Implement background fetch, version marker persistence, and unknown-model notifications without adding a timer loop.
- [ ] Update `UsageCursor` to resolve rates through the catalog and preserve event-time semantics.
- [ ] Run focused sync/provider/usage tests and confirm all pass.

### Task 3: Remove daily workflow and update contract documentation

**Files:**
- Modify: `.github/workflows/model-prices.yml`
- Modify: `docs/specs/usage-cost.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/i18n/CHANGELOG.zh-CN.md`
- Test: `tests/test_model_price_audit.py`

- [ ] Replace the daily cron with push/manual checks for pricing sources, parser, and catalog code.
- [ ] Document event-driven triggers, cache provenance, and effective-time behavior.
- [ ] Add parser coverage for `gpt-6.1-sol` and verify the official-rate mismatch is reported until the reviewed table is updated.
- [ ] Run the pricing audit and focused unit tests.

### Task 4: Full verification and delivery review

**Files:**
- Review only: all changed files.

- [ ] Run `python -m unittest tests.test_pricing_catalog tests.test_pricing_sync tests.test_usage_cost tests.test_model_price_audit tests.test_provider`.
- [ ] Run `python -m unittest discover -s tests -p 'test_*.py'` with the repository's Windows/offscreen environment.
- [ ] Run `python -m compileall -q codex_taskbar`.
- [ ] Verify no taskbar code launches, closes, proxies, or restarts Codex.
- [ ] Review cache paths, source URL validation, failure fallback, and git diff before committing.

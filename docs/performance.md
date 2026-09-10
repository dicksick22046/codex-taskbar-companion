# Performance checks

Run from the repository with the development environment installed:

```powershell
.venv/Scripts/python.exe scripts/benchmark_ui.py
.venv/Scripts/python.exe -m unittest tests.test_performance
```

The benchmark runs 300 unchanged UI ticks, rasterizes requested updates in a hidden widget, and mocks window placement/recovery. It uses synthetic data, does not start the Provider, and does not move the mouse.

On the development Windows 11 machine, the pre-change run requested 303 repaints and used 0.391 CPU seconds. After the change, it requested 0 repaints and used 0.047 CPU seconds. CPU timing varies across runs and machines; the regression test checks redundant repaint behavior rather than a timing threshold.

This measures one avoidable cost, not total application CPU or battery use. Active tasks still animate. Collection stays at 30 seconds for quota, 5 seconds for task metadata, and 1 second for local incremental logs. Diagnostic `snapshot.json` can lag up to 30 seconds; the in-memory display and persistent quota/reset ledgers are separate.

For a whole-process comparison, hold task count, monitor scaling and popup visibility constant, allow initial log indexing to finish, and record process CPU time over a fixed interval. Include the child app-server process separately. Do not sum shared working sets as unique memory or infer a memory leak from a single sample.

# 0.9.0 verification

Contract: [product clarity and attention](../specs/product-clarity.md).

## Automated and controlled evidence

- Full Windows desktop suite: 323 tests, successful with one offscreen-only suite skipped by design. Its four complete widget journeys passed in a separate `QT_QPA_PLATFORM=offscreen` process.
- Shared UI fixtures use an isolated temporary runtime. A full test run preserved the live preferences file hash.
- Expiry checks cover successful/failed quota reads, raw-snapshot preservation, an already-open 5h panel, unknown reset times, observed-day boundaries and known 5h capability. No real reset credits were consumed.
- Independent window controls preserve existing choices and positions; fresh settings use Auto and leave the Running strip disabled. The optional history view preserves search/selection, resets hidden metric sorting and pauses indexing.
- Four-language renders of quota panels, settings, simple/expanded task search and the independent task strip were inspected. The Spanish placement label wraps at constrained settings widths. Long quota labels are measured without the former 540 DIP ceiling.
- Static Running tasks do not keep the shared paint timer active. Direct dragging, interrupted transitions, hover-only long-title reading and reduced-motion behavior retain focused coverage.
- Public README images use only synthetic tasks and current Qt rendering. No personal screenshots, accounts or history are included in Git.

## Windows installation

- Built the versioned package with `scripts/package.ps1` and the locally available Inno compiler, retaining build PATH isolation and the public bootstrap.
- Upgraded the local installation to 0.9.0. The installed executable matched the build; existing preference values and bundled assets were preserved. Normal exit/relaunch restored visible windows without changing foreground focus.
- Inspected the real installed quota/status and Running windows. Standard system `Win32_StartupCommand` and `StdRegProv` showed the product's actual startup path and uninstall version 0.9.0. The bootstrap left no temporary installation task or extracted setup directory.
- Ran the installed uninstaller silently after normal app exit: return code 0, installed executable removed, and hashes of the existing settings, quota history, reset history, statistics cache and side-chat links preserved. Reinstalled the same 0.9.0 package successfully and returned the app to normal operation.

## Limits

Real pointer manipulation, mixed-DPI multi-monitor hardware, a subsequent Windows sign-in and screen-reader use were not exercised in this batch. Their controlled/native/unit checks are not presented as hardware or accessibility certification. State coverage remains limited to the Codex metadata already supported.

The [five-participant usability protocol](product-clarity-usability.md) is ready. No real participant sessions have occurred, and this release does not claim validated productivity, retention or universally preferred defaults.

## Public release

[0.9.0](https://github.com/dicksick22046/codex-taskbar-companion/releases/tag/v0.9.0) is published from `018acbebfd0922abd5c69be5790b11dd226b5998`. Both [main CI](https://github.com/dicksick22046/codex-taskbar-companion/actions/runs/34684307338) and [tag CI, including installer build](https://github.com/dicksick22046/codex-taskbar-companion/actions/runs/34684312062) passed.

The published 33,042,944-byte installer was downloaded in full and matched the local verified package: SHA-256 `eb20e2f7a3c5a2bd9680cd4b56d35e134d1606682c97dc00f6fd88d83c1537a2`. The public checksum asset matches as well. The update resolver offers 0.9.0 to 0.8.1/0.8.0/0.7.0 clients and offers no update to 0.9.0 itself. Earlier published assets were not replaced.

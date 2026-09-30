# Third-party components

Codex Taskbar Companion is an independent community application, not an OpenAI product.
No Codex executable, account credential, or conversation is distributed in this package.

- **Python 3.12** — Python Software Foundation License. https://www.python.org/psf/license/
- **PySide6 / Shiboken6 / Qt 6.11** — LGPLv3 / GPLv3 / commercial options as stated in the upstream distributions. This project uses the LGPL option for the included modules. https://doc.qt.io/qtforpython-6/licenses.html
  Qt libraries are shipped separately, without modifications. Users may replace compatible library files and debug modifications as permitted by those licenses. Bundled upstream license texts are in `licenses/`. Corresponding upstream source: https://download.qt.io/official_releases/qt/6.11/ and https://download.qt.io/official_releases/QtForPython/pyside6/
- **PyInstaller** — GPL with bootloader exception; build tool only. https://pyinstaller.org/en/stable/license.html
- **Inno Setup** — independent installer tool. https://jrsoftware.org/files/is/license.txt
- **Lucide pin icon** — ISC License, copyright Lucide Icons and Contributors. The upstream SVG is bundled unchanged; color and display size are applied by the renderer. Source: https://github.com/lucide-icons/lucide/blob/main/icons/pin.svg . License: `assets/icons/LUCIDE-LICENSE`.
- **Alibaba PuHuiTi 3.0 Regular** — unchanged font from the official Alibaba font site. Font source, copyright and hash: `assets/fonts/SOURCE.md`. The official site describes the family as globally free for personal and commercial use. The original copyright remains with Alibaba; the font is not covered by this project's MIT license and is not sold separately. The source and usage notice accompany the package.

The published source and build instructions allow rebuilding the application with modified dependencies. Release archives must retain third-party notices.

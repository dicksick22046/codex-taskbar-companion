"""Per-user Windows login startup, shared by source and installed builds."""
from pathlib import Path
import subprocess
import sys
import winreg

KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE = 'CodexTaskbar'


def command():
    if getattr(sys, 'frozen', False):
        return subprocess.list2cmdline([sys.executable])
    python = Path(sys.executable).with_name('pythonw.exe')
    return subprocess.list2cmdline([str(python), str(Path(__file__).with_name('app.py'))])


def enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            return bool(winreg.QueryValueEx(key, VALUE)[0])
    except FileNotFoundError: return False


def set_enabled(value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        if value: winreg.SetValueEx(key, VALUE, 0, winreg.REG_SZ, command())
        else:
            try: winreg.DeleteValue(key, VALUE)
            except FileNotFoundError: pass

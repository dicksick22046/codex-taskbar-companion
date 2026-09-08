"""GitHub stable-release checks and verified per-user installer downloads."""
import hashlib
import json
from pathlib import Path
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

from PySide6.QtCore import QObject, Signal
from .build_info import VERSION, RELEASE_REPOSITORY


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value))
    return tuple(map(int, match.groups())) if match else None


def asset_url(url, repository, tag, name):
    expected = f'https://github.com/{repository}/releases/download/{tag}/{name}'
    if url != expected: raise ValueError('发布文件地址与仓库不匹配')
    return url


def release_candidate(release, repository, current=VERSION):
    if release.get('draft') or release.get('prerelease'): return None
    tag = release.get('tag_name', '')
    version = version_tuple(tag)
    if version is None or version <= version_tuple(current): return None
    name = f'CodexTaskbarCompanion-{tag.removeprefix("v")}-Setup-x64.exe'
    assets = {item.get('name'): item for item in release.get('assets', [])}
    if name not in assets or name + '.sha256' not in assets:
        raise ValueError('新版本的安装包尚未准备完整')
    return {'version': tag.removeprefix('v'), 'name': name,
            'url': asset_url(assets[name].get('browser_download_url'), repository, tag, name),
            'checksum_url': asset_url(assets[name+'.sha256'].get('browser_download_url'), repository, tag, name+'.sha256')}


class ReleaseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or not (host == 'github.com' or host.endswith('.githubusercontent.com')):
            raise ValueError('发布下载跳转地址不受信任')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url):
    request = urllib.request.Request(url, headers={'User-Agent': f'CodexTaskbar/{VERSION}', 'Accept': 'application/vnd.github+json'})
    return urllib.request.build_opener(ReleaseRedirects()).open(request, timeout=15)


def fetch_release(repository):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('尚未配置更新发布仓库')
    with open_url(f'https://api.github.com/repos/{repository}/releases/latest') as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000: raise ValueError('发布信息过大')
    return release_candidate(json.loads(raw), repository)


def download_installer(release, folder):
    folder.mkdir(parents=True, exist_ok=True)
    with open_url(release['checksum_url']) as response:
        expected = response.read(1025).decode('ascii').split()[0].lower()
    if not re.fullmatch('[0-9a-f]{64}', expected): raise ValueError('发布校验文件无效')
    target = folder / release['name']
    temporary = target.with_suffix('.download')
    digest = hashlib.sha256(); size = 0
    try:
        with open_url(release['url']) as response, temporary.open('wb') as stream:
            while chunk := response.read(128*1024):
                size += len(chunk)
                if size > 350*1024*1024: raise ValueError('安装包超过大小限制')
                stream.write(chunk); digest.update(chunk)
        if digest.hexdigest() != expected: raise ValueError('安装包校验未通过，请稍后重试')
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


class UpdateController(QObject):
    changed = Signal()
    ready = Signal(str)
    result = Signal(object)

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = Path(runtime); self.release = None; self.busy = False
        self.message = '检查更新' if RELEASE_REPOSITORY else '发布仓库尚未配置'
        self.result.connect(self.finish)

    def check(self):
        if self.busy: return
        self.busy = True; self.message = '正在检查更新…'; self.changed.emit()
        def work():
            try: self.result.emit({'release': fetch_release(RELEASE_REPOSITORY)})
            except urllib.error.HTTPError as exc:
                self.result.emit({'unpublished':True} if exc.code==404 else {'error':str(exc)})
            except Exception as exc: self.result.emit({'error': str(exc)})
        threading.Thread(target=work, daemon=True).start()

    def install(self):
        if self.busy or not self.release: return
        self.busy = True; self.message = '正在下载安装包…'; self.changed.emit()
        release = dict(self.release)
        def work():
            try: self.result.emit({'installer': str(download_installer(release, self.runtime/'updates'))})
            except Exception as exc: self.result.emit({'error': str(exc)})
        threading.Thread(target=work, daemon=True).start()

    def finish(self, result):
        self.busy = False
        if 'installer' in result:
            self.message = '安装包已就绪'; self.ready.emit(result['installer'])
        elif result.get('unpublished'):
            self.message = '尚未发布可更新版本'
        elif 'error' in result:
            self.message = '暂时无法检查更新' if RELEASE_REPOSITORY else '发布仓库尚未配置'
            print('Update:', result['error'])
        else:
            self.release = result['release']
            self.message = f'更新至 {self.release["version"]}' if self.release else '已是最新版本'
        self.changed.emit()


def install_after_exit(installer, parent_pid, runtime):
    """The short-lived updater waits until application files are released."""
    import ctypes
    from ctypes import wintypes
    import subprocess
    path=Path(installer).resolve()
    if not path.is_relative_to((Path(runtime)/'updates').resolve()) or path.suffix.lower()!='.exe':
        raise ValueError('安装包不在更新目录')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    process=kernel.OpenProcess(0x100000,False,parent_pid)
    if process:
        try:
            if kernel.WaitForSingleObject(process,30000)!=0:raise TimeoutError('程序尚未退出')
        finally:kernel.CloseHandle(process)
    elif ctypes.get_last_error()!=87:raise ctypes.WinError(ctypes.get_last_error())
    from . import startup
    tasks='/TASKS=autostart' if startup.enabled() else '/TASKS='
    subprocess.Popen([str(path),'/SP-','/SILENT','/CLOSEAPPLICATIONS','/UPDATE=1',tasks],creationflags=0x08000000)

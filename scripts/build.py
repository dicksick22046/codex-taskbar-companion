"""Build a directory application with replaceable Qt DLLs and notices."""
import importlib.metadata
import shutil
import os
import subprocess
import sys
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_info import VERSION


def main():
    work = ROOT/'build'; work.mkdir(exist_ok=True)
    (work/'version.txt').write_text(VERSION,encoding='utf-8')
    notices = work/'licenses'; notices.mkdir(exist_ok=True)
    for package in ('PySide6-Essentials', 'shiboken6'):
        distribution = importlib.metadata.distribution(package)
        for entry in distribution.files or []:
            if 'license' in str(entry).lower() or 'copying' in entry.name.lower():
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = notices/package/Path(str(entry))
                    target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPixmap,QPainter,QColor,QPen
    from PySide6.QtCore import Qt,QBuffer,QByteArray,QIODevice
    application=QApplication.instance() or QApplication([])
    images=[]
    for size in (16,24,32,48,64,128,256):
        pixmap=QPixmap(size,size);pixmap.fill(Qt.GlobalColor.transparent)
        painter=QPainter(pixmap);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.scale(size/32,size/32)
        pen=QPen(QColor('#45ba91'),3);pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen);painter.drawArc(5,5,22,22,90*16,-290*16)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#a088d1'));painter.drawEllipse(12,12,8,8);painter.end()
        data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly);pixmap.save(buffer,'PNG')
        images.append((size,bytes(data)))
    offset=6+16*len(images);directory=bytearray(struct.pack('<HHH',0,1,len(images)));content=bytearray()
    for size,data in images:
        directory+=struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset)
        content+=data;offset+=len(data)
    icon=work/'app.ico';icon.write_bytes(directory+content)
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.exists(): shutil.copy2(python_license, notices/'Python-LICENSE.txt')
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo,FixedFileInfo,StringFileInfo,StringTable,StringStruct,VarFileInfo,VarStruct
    version=tuple(map(int,VERSION.split('.')))+(0,)
    info=VSVersionInfo(ffi=FixedFileInfo(filevers=version,prodvers=version,mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[
        StringFileInfo([StringTable('040904B0',[StringStruct(k,v) for k,v in {
            'CompanyName':'Codex Taskbar Companion contributors','FileDescription':'Codex Taskbar Companion',
            'FileVersion':VERSION,'ProductVersion':VERSION,'ProductName':'Codex Taskbar Companion',
            'OriginalFilename':'CodexTaskbarCompanion.exe'}.items()])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])
    version_file=work/'version-info.txt';version_file.write_text(str(info),encoding='utf-8')
    system=Path(os.environ['SystemRoot'])
    build_env=dict(os.environ)
    build_env['PATH']=os.pathsep.join(map(str,[Path(sys.executable).parent,Path(sys.base_prefix),system/'System32',system]))
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--windowed', '--onedir', '--version-file', str(version_file), '--icon', str(icon), '--name', 'CodexTaskbarCompanion',
                    '--distpath', str(ROOT/'dist'), '--workpath', str(work/'pyinstaller'),
                    '--specpath', str(work), '--add-data', f'{ROOT / "assets"};assets',
                    '--add-data', f'{notices};licenses',
                    '--add-data', f'{ROOT / "LICENSE"};.',
                    '--add-data', f'{ROOT / "THIRD_PARTY.md"};.',
                    str(ROOT/'app.py')], check=True, cwd=ROOT, env=build_env)
    subprocess.run([str(ROOT/'dist/CodexTaskbarCompanion/CodexTaskbarCompanion.exe'),'--smoke-test'],check=True,timeout=25)
    print(f'Built and launch-checked Codex Taskbar Companion {VERSION}')


if __name__ == '__main__': main()

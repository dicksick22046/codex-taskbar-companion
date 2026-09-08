import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class InstallerTests(unittest.TestCase):
    def test_bootstrap_preserves_windows_arguments(self):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / 'BootstrapTests.exe'
            subprocess.run([str(compiler), '/nologo', '/target:exe', '/platform:x64',
                            '/r:System.Management.dll', '/r:System.Windows.Forms.dll', '/r:Microsoft.CSharp.dll',
                            '/main:BootstrapTests', '/out:' + str(executable),
                            str(root/'installer/Bootstrap.cs'), str(root/'installer/BootstrapTests.cs')],
                           capture_output=True, check=True)
            result = subprocess.run([str(executable)], capture_output=True, text=True, check=True)
            self.assertIn('passed: 11', result.stdout)

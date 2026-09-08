using System;
using System.Runtime.InteropServices;

internal static class BootstrapTests
{
    [DllImport("shell32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CommandLineToArgvW(string command, out int count);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);

    static int Main()
    {
        string[] cases = { "", "plain", "two words", @"C:\安装目录\", "/DIR=C:\\directory with spaces\\", "say\"hello", "\\\"quoted\\\"", "/TASKS=", "/VERYSILENT", "a\\\\\"b", "a\tb" };
        foreach (string value in cases)
        {
            int count;
            IntPtr argv = CommandLineToArgvW("setup.exe " + Bootstrap.Quote(value), out count);
            try
            {
                if (count != 2 || Marshal.PtrToStringUni(Marshal.ReadIntPtr(argv, IntPtr.Size)) != value)
                    throw new Exception("Argument round-trip failed: " + value);
            }
            finally { LocalFree(argv); }
        }
        Console.WriteLine("Windows command-line round-trip passed: " + cases.Length);
        string absentTask = "CodexTaskbar-Setup-" + Guid.NewGuid().ToString("N");
        Bootstrap.RemoveTask(absentTask);
        Bootstrap.RemoveTask(absentTask);
        Console.WriteLine("Peer cleanup is idempotent");
        return 0;
    }
}

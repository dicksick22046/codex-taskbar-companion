// Installation only. Uses the .NET Framework included with Windows 11.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Management;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Bootstrap
{
    const string Product = "Codex Taskbar Companion";
    const string WorkerArgument = "--host-worker=";
    const string TaskPrefix = "CodexTaskbar-Setup-";
    const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\{F98B6B74-494B-41F8-A164-6BBAE16801A6}_is1";
    static string UserSid { get { return WindowsIdentity.GetCurrent().User.Value; } }
    static string DataDirectory { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".codex-taskbar-companion"); } }

    [STAThread]
    static int Main(string[] args)
    {
        if (args.Length > 0 && args[0].StartsWith(WorkerArgument, StringComparison.Ordinal))
        {
            Guid id;
            if (!Guid.TryParseExact(args[0].Substring(WorkerArgument.Length), "N", out id)) return 1;
            try
            {
                using (var pipe = new NamedPipeClientStream(".", TaskPrefix + id.ToString("N"), PipeDirection.Out))
                {
                    pipe.Connect(30000);
                    int code = RunSafely(args.Skip(1).ToArray(), true);
                    using (var writer = new BinaryWriter(pipe)) writer.Write(code);
                    return code;
                }
            }
            catch (Exception error) { Log("worker: " + error.Message); return 1; }
            finally
            {
                try { RemoveTask(TaskPrefix + id.ToString("N")); }
                catch (Exception error) { Log("worker cleanup: " + error.Message); }
            }
        }
        return RunSafely(args, false);
    }

    static int RunSafely(string[] args, bool worker)
    {
        try
        {
            bool isolated = IsRegistryIsolated();
            Log((worker ? "worker" : "launcher") + ": isolated=" + isolated);
            if (worker && isolated) throw new InvalidOperationException("Windows 未能提供独立的安装环境。请从资源管理器打开安装包。");
            return isolated ? Handoff(args) : RunInstaller(args);
        }
        catch (Exception error)
        {
            Log("error: " + error.Message);
            bool silent = args.Any(a => a.Equals("/SILENT", StringComparison.OrdinalIgnoreCase) || a.Equals("/VERYSILENT", StringComparison.OrdinalIgnoreCase));
            if (!silent) MessageBox.Show("安装未完成。\n" + error.Message, Product, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    internal static string ReadSystemString(string key, string name)
    {
        using (var registry = new ManagementClass(@"\\.\root\default:StdRegProv"))
        using (var input = registry.GetMethodParameters("GetStringValue"))
        {
            input["hDefKey"] = 0x80000003u; // HKEY_USERS, with the caller's explicit SID.
            input["sSubKeyName"] = UserSid + "\\" + key;
            input["sValueName"] = name;
            using (var result = registry.InvokeMethod("GetStringValue", input, null))
            {
                uint code = (uint)result["ReturnValue"];
                if (code == 1 || code == 2) return null; // Provider reports missing value/key.
                if (code != 0) throw new InvalidOperationException("无法读取 Windows 安装登记，错误码 " + code + "。");
                return (string)result["sValue"];
            }
        }
    }

    internal static bool IsRegistryIsolated()
    {
        string nonce = Guid.NewGuid().ToString("N");
        string path = @"Software\CodexTaskbarCompanion\SetupProbe-" + nonce;
        try
        {
            using (var key = Registry.CurrentUser.CreateSubKey(path)) key.SetValue("Value", nonce, RegistryValueKind.String);
            return ReadSystemString(path, "Value") != nonce;
        }
        finally { Registry.CurrentUser.DeleteSubKey(path, false); }
    }

    internal static string Quote(string value)
    {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            result.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
            result.Append(c); slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }

    static string Arguments(string[] args) { return string.Join(" ", args.Select(Quote)); }

    static int Handoff(string[] args)
    {
        string nonce = Guid.NewGuid().ToString("N");
        string name = TaskPrefix + nonce;
        var security = new PipeSecurity();
        security.SetAccessRuleProtection(true, false);
        security.AddAccessRule(new PipeAccessRule(WindowsIdentity.GetCurrent().User, PipeAccessRights.FullControl, AccessControlType.Allow));
        using (var pipe = new NamedPipeServerStream(name, PipeDirection.In, 1, PipeTransmissionMode.Byte, PipeOptions.Asynchronous, 4096, 0, security))
        {
            dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service", true));
            service.Connect();
            dynamic folder = service.GetFolder("\\");
            bool registered = false;
            try
            {
                dynamic task = service.NewTask(0);
                task.RegistrationInfo.Description = "Temporary installer handoff; no startup trigger.";
                task.Principal.UserId = UserSid;
                task.Principal.LogonType = 3; // Existing interactive token, no stored password.
                task.Principal.RunLevel = 0;
                task.Settings.ExecutionTimeLimit = "PT0S";
                task.Settings.DisallowStartIfOnBatteries = false;
                task.Settings.StopIfGoingOnBatteries = false;
                task.Settings.Hidden = true;
                dynamic action = task.Actions.Create(0);
                action.Path = Assembly.GetExecutingAssembly().Location;
                action.Arguments = Arguments(new[] { WorkerArgument + nonce }.Concat(args).ToArray());
                action.WorkingDirectory = Environment.CurrentDirectory;
                dynamic registration = folder.RegisterTaskDefinition(name, task, 2, UserSid, null, 3, null);
                registered = true;
                var connection = pipe.BeginWaitForConnection(null, null);
                registration.Run(null);
                if (!connection.AsyncWaitHandle.WaitOne(30000)) throw new TimeoutException("Windows 未能启动安装进程。");
                pipe.EndWaitForConnection(connection);
                using (var reader = new BinaryReader(pipe)) return reader.ReadInt32();
            }
            finally
            {
                if (registered) RemoveTask(name);
            }
        }
    }

    internal static void RemoveTask(string name)
    {
        dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service", true));
        service.Connect();
        try { service.GetFolder("\\").DeleteTask(name, 0); Log("handoff task removed"); }
        catch (FileNotFoundException) { }
        catch (COMException error)
        {
            // Either peer may have already removed this invocation's task.
            if (error.ErrorCode != unchecked((int)0x80070002)) throw;
        }
    }

    static int RunInstaller(string[] args)
    {
        string directory = Path.Combine(DataDirectory, "setup", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        string installer = Path.Combine(directory, "setup.exe");
        try
        {
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("InnoSetup"))
            using (var output = new FileStream(installer, FileMode.CreateNew, FileAccess.Write)) input.CopyTo(output);
            int code;
            using (var process = Process.Start(new ProcessStartInfo(installer, Arguments(args)) { UseShellExecute = false, WorkingDirectory = Environment.CurrentDirectory }))
            {
                process.WaitForExit(); code = process.ExitCode;
            }
            if (code == 0 && !args.Any(a => a.Equals("/HELP", StringComparison.OrdinalIgnoreCase) || a == "/?")) VerifyRegistration();
            Log("installer exit=" + code);
            return code;
        }
        finally
        {
            // Delete only the file created above and its now-empty unique directory.
            if (File.Exists(installer)) File.Delete(installer);
            Directory.Delete(directory, false);
        }
    }

    static void VerifyRegistration()
    {
        string version = Assembly.GetExecutingAssembly().GetName().Version.ToString(3);
        string location = ReadSystemString(UninstallKey, "InstallLocation");
        if (ReadSystemString(UninstallKey, "DisplayVersion") != version || string.IsNullOrEmpty(location))
            throw new InvalidOperationException("Windows 未读到本版本的安装登记。");
        string selected = ReadSystemString(UninstallKey, "Inno Setup: Selected Tasks") ?? "";
        string command = ReadSystemString(@"Software\Microsoft\Windows\CurrentVersion\Run", "CodexTaskbar");
        bool autostart = selected.Split(',').Any(s => s.Trim() == "autostart");
        string expected = "\"" + Path.Combine(location, "CodexTaskbarCompanion.exe") + "\"";
        if (autostart ? !string.Equals(command, expected, StringComparison.OrdinalIgnoreCase) : command != null)
            throw new InvalidOperationException("Windows 的开机启动登记与安装选择不一致。");
        Log("system registration verified; autostart=" + autostart);
    }

    static void Log(string message)
    {
        try
        {
            Directory.CreateDirectory(DataDirectory);
            using (var file = new FileStream(Path.Combine(DataDirectory, "setup.log"), FileMode.Append, FileAccess.Write, FileShare.ReadWrite))
            using (var writer = new StreamWriter(file)) writer.WriteLine(DateTimeOffset.Now.ToString("o") + " " + message);
        }
        catch (IOException) { }
    }
}

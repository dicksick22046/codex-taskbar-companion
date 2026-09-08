# 项目范围

这是独立的Codex Taskbar Companion，遥控器在另一个仓库，不在这里改动。

- 先读docs/architecture.md、docs/specs/interaction.md和docs/specs/release.md，以当前工作区为准。
- 应用实现放codex_taskbar/，测试放tests/；根app.py仅为启动入口。交互以docs/specs/interaction.md为准。真实重置只能由用户在界面二次确认；自动验证必须使用模拟API，严禁消耗用户真实重置机会。
- 保持Codex、Windows11、左侧单行的首版范围；不重新展开用户取消的完整实时错误检测。
- 右键只保留设置与退出，设置内管理显示、启动和更新；主栏不添加外部大边框或反复提示。
- 程序数据位于USERPROFILE/.codex-taskbar-companion；运行目录与数据分离，不能提交账号、日志、历史记录或个人截图。
- 当前机器运行安装版时，开发前先从托盘退出，再用仓库start.ps1启动源码；重复启动只会打开已有实例设置，不能据此判断新代码已加载。
- 0.1.5起公开安装包自动检测宿主隔离，必要时交给Windows临时任务安装；不要绕过引导程序单独运行build/setup-payload.exe。用Win32_StartupCommand及系统StdRegProv核验实际登记，不能仅以宿主内winreg或NtQueryKey读回判定自启成功。临时任务用完删除，不作为常驻守护。
- 发布构建使用scripts/package.ps1；构建PATH隔离是必要约束，禁止让Poppler等外部工具的同名DLL混入包。
- 透明属性必须在创建原生窗口句柄前设置。既要运行测试，也要检查实际安装版的窗口。
- 单元测试、受控数据、实际窗口、安装升级卸载和其他机器验收分别报告，不互相替代。
- 版本号唯一来源codex_taskbar/build_info.py；发布信息见CHANGELOG和docs/publishing.md。
- 提交、推送、发布遵循用户授权；发布目标仅GitHub dicksick22046/codex-taskbar-companion，禁止改用内网GitLab。

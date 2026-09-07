# 项目范围

这是独立的Codex Taskbar Companion，遥控器在另一个仓库，不在这里改动。

- 先读docs/HANDOFF.md、docs/status-bar.md和docs/release-v0.1.md，以当前工作区为准。
- 保持Codex、Windows11、左侧单行的首版范围；不重新展开用户取消的完整实时错误检测。
- 右键只保留设置与退出，设置内管理显示、启动和更新；主栏不添加外部大边框或反复提示。
- 程序数据位于LOCALAPPDATA/CodexTaskbar；运行目录与数据分离，不能提交账号、日志、历史记录或个人截图。
- 当前机器运行安装版时，开发前先从托盘退出，再用仓库start.ps1启动源码；重复启动只会打开已有实例设置，不能据此判断新代码已加载。
- 发布构建使用scripts/package.ps1；构建PATH隔离是必要约束，禁止让Poppler等外部工具的同名DLL混入包。
- 透明属性必须在创建原生窗口句柄前设置。既要运行测试，也要检查实际安装版的窗口。
- 单元测试、受控数据、实际窗口、安装升级卸载和其他机器验收分别报告，不互相替代。
- 版本号唯一来源build_info.py；首次候选及发布信息见CHANGELOG和docs/publishing.md。
- 提交、推送、发布遵循用户授权；发布目标仅GitHub Guid16/codex-taskbar-companion，禁止改用内网GitLab。

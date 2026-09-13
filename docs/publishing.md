# 发布流程

## 发布节奏

日常开发提交代码并维护CHANGELOG的Unreleased区，不因一次文案、颜色、单位或小交互调整就升级版本、打标签或发布安装包。常规push和PR只运行测试。

完整功能或一批相关修复通过回归、实际窗口和安装验证后，再统一调整版本号、创建标签与发布说明。仅启动失败、数据损坏或关键能力不可用等严重故障单独发热修复版。

安装器构建由正式版本标签或手动workflow_dispatch触发；工作流仍不自动公开Release。本地体验包和CI产物不等于正式更新，不上传到已有正式版本中。发布前核对测试包与正式版本的升级关系，避免已安装的测试版本阻止后续更新。

发布资产准备完整后再发布草稿，保持GitHub的[草稿与正式Release分离](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。不增加按日定时发布或自动凑版本机制。

## 版本来源

唯一版本号为 `codex_taskbar/build_info.py` 的 `VERSION`。正式版本使用 `X.Y.Z`，Git标签为 `vX.Y.Z`。不要修改已发布版本的安装包；修正后递增补丁号。
更新仓库为 `dicksick22046/codex-taskbar-companion`。公开前必须确认该仓库由项目所有者控制。

## 构建与验收

1. 更新CHANGELOG和VERSION。
2. 安装requirements-build.txt，运行unittest discover。
3. 使用scripts/package.ps1生成安装器及SHA-256文件。
   脚本先生成Inno负载，再用Windows自带.NET Framework编译安装引导程序，发布文件仍是单个Setup.exe。原始负载只留在build中，不能单独作为Release安装包。
4. 在Windows 11上验证安装、设置恢复、退出、再次启动、覆盖升级、卸载保留数据。
5. 检查发布目录只包含安装包和校验文件，不包含账号、用户数据、截图或虚拟环境。

0.1.5起分别检查普通与隔离宿主启动，使用系统StdRegProv和Win32_StartupCommand核对真实登记；同时核对取消/失败退出码、命令行参数、临时任务及安装缓存清理。安装引导程序使用Windows 11自带.NET Framework，不要求用户另装运行时。

GitHub Actions的build工作流提供编译产物，不会自动公开发布。
只有正式GitHub Release才会触发已安装客户端的版本提示；单纯push代码没有这个效果。

## 发布资产

正式Release必须包含：

- `CodexTaskbarCompanion-X.Y.Z-Setup-x64.exe`
- `CodexTaskbarCompanion-X.Y.Z-Setup-x64.exe.sha256`

先建立草稿Release、上传两份资产，再发布。客户端跳过预发布和不完整的资产，不把检查失败显示为“已是最新版”。

发布草稿时显式提供正式tag_name及其已验证的target_commitish，发布后重新读取并检查实际标签、提交与资产下载URL；不能只凭Release标题判断版本。草稿临时标签不作为正式版本发布。
安装包尚无签名证书；不要声称已签名或已通过SmartScreen信誉验证。

## 更新与回退

客户端先下载并验证SHA-256，安装辅助进程等待当前组件退出后启动安装器；更新完成重新启动组件。继承当前开机启动选项，用户数据目录不替换。
用户可重新安装历史版本进行回退。不要通过删除用户数据来实现升级或回退。

首次建仓、提交、打标签、推送和公开发布须遵守所有者授权；本地构建完成不等于已发布。

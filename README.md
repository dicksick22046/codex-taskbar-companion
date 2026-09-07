# Codex Taskbar Companion

把 Codex 的额度和任务，放到 Windows 任务栏的一角。

写着代码，瞄一眼：额度还剩多少，什么时候重置，另一个任务跑完了没。需要细看时点一下，平时就让它安静待着。

[下载安装](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest) · [反馈问题](https://github.com/dicksick22046/codex-taskbar-companion/issues) · [更新记录](CHANGELOG.md)

![状态条与任务面板预览](docs/images/preview.png)

*由真实界面代码绘制，图中任务和数值为演示数据。*

## 一眼能看到什么

左边是额度：周剩余额度、今日消耗、距离重置还有多久。账户接口提供 5 小时额度时，会自动多显示一项，各项都能在设置里关闭。

右边是任务：进行中的任务缓慢轮播，绿色圆点呼吸；完成但还没查看的任务，用橙色圆点提醒。长标题平时省略，鼠标移上去后滚动显示，同时暂停任务轮播。

- **点额度**，看本周期每天的 Token 用量和合计，支持百万与亿切换。
- **点任务**，看正在运行和今天其他有活动的任务，以及各自今天的运行时长、Token 用量；点某一项就能回到 Codex。
- **右键**，打开设置或退出。开机启动、显示开关和检查更新都在设置里。

## 装上就能用

目前面向 **Windows 11 x64 + 已安装并登录的 Codex 桌面版**，显示在底部主任务栏左侧。建议先打开一次 Codex，再启动本工具。

1. 到 [Releases](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest) 下载 `CodexTaskbarCompanion-版本号-Setup-x64.exe`。
2. 安装后启动。安装包带有 Python、Qt 和字体，不用自己配环境，也不需要管理员权限。
3. 在设置里留下你想看的几项。开机启动也可以在这里关闭。

如果左侧空间不足，或你把所有显示都关了，组件会收起到系统托盘。从托盘，或从开始菜单再次打开，都能找到设置。

这是早期版本，目前在 Windows 11 上做过本机安装、升级和交互验证。Windows 10、macOS、多屏独立状态条、第三方任务栏暂未验证。安装包尚未代码签名，Windows 可能显示发布者未知。

## 数字怎么算

**额度来自账户，Token 来自本机日志。** 两者口径不同，不能拿 Token 换算订阅额度，更不是美元账单。

今日额度以当天第一条可用额度记录为起点。如果你下午才第一次打开，它从那一刻开始算，之前用掉的不会补猜。重启保留已有记录，跨日重新取当天基线；周额度在当天重置时，分段累计。

每个任务显示的是**今天累计**的用量和运行时长，包含今天的多轮运行。时长包含工具等待，轮次之间的空档不计。任务列表覆盖今天有活动记录的任务，单纯打开看过的任务不一定在里面。

短暂读取失败时，保留尚未过期的数据和原有显示，后台继续重试。停止、失败只按能读到的明确记录显示，无法捕获 Codex 的所有瞬时网络错误。Codex 的接口和本地日志格式变化，也可能需要本工具跟着更新。

## 数据留在哪里

设置、额度历史和本机状态记录保存在 `%USERPROFILE%/.codex-taskbar-companion`。升级和卸载默认保留，重新安装可以继续用。

工具读取本机 Codex 接口与日志，不发送对话、不创建任务，不保存对话正文或账号凭据，也没有遥测。任务标题、项目名称、用量等状态会保存在本机；反馈问题时，请先检查日志或截图是否包含你不想公开的信息。

更新检查访问本项目的 GitHub Releases。发现新版本会提醒，由你选择安装，更新前校验下载文件的 SHA-256。

## 想自己改

准备 Python 3.12 和 Inno Setup。下面用 `uv` 创建开发环境：

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
./start.ps1
.venv/Scripts/python.exe -m unittest discover
./scripts/package.ps1 -Compiler 'C:/Path/To/Inno Setup/ISCC.exe'
```

如果安装版已经在运行，先退出再启动源码版；重复启动会打开已有实例的设置。构建产物在 `dist/` 和 `release/`，版本号统一在 `build_info.py` 维护。

发现问题，欢迎提 [Issue](https://github.com/dicksick22046/codex-taskbar-companion/issues)。带上工具版本、Windows 版本、复现步骤；界面问题附一张处理过隐私信息的截图，会更容易定位。

源代码采用 [MIT 许可](LICENSE)，字体与第三方库保留各自许可，见 [第三方说明](THIRD_PARTY.md)。这是独立社区工具，与 OpenAI 没有隶属关系。

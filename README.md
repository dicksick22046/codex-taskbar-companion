# Codex Taskbar Companion

Windows 11 上的 Codex 极简额度与任务状态条。

左侧看额度，右侧看正在进行的任务。没有多服务商切换、美元账单或复杂仪表盘。

## 功能

- 周额度；账户提供时自动展示5小时额度。
- 重置倒计时、今日额度消耗、周期Token图表。
- 多任务轮播、完成待读、停止和明确失败标识。
- 任务当天运行时长与Token，点击直达Codex。
- 右键设置、系统托盘恢复、开机启动和版本检查。

## 安装与使用

首版安装包准备中，发布地址为 [GitHub Releases](https://github.com/Guid16/codex-taskbar-companion/releases)。
需要Windows 11 x64，以及已安装并登录的Codex桌面程序。安装包自带Python与Qt，无需单独配置开发环境，不要求管理员权限。

1. 安装后，状态条出现在底部主任务栏左侧。
2. 点击额度打开图表，点击任务打开任务列表。
3. 右键状态条或托盘图标，打开设置或退出；在设置中管理启动和更新。
4. 关闭全部显示或左侧空间不足时，组件收起到托盘；从托盘或再次从开始菜单启动，可打开设置。

显示设置即时保存。任务栏右侧空白不触发面板。首版不承诺Windows 10、macOS、第三方任务栏或多屏独立组件。

## 数据与隐私

记录位于 `%USERPROFILE%/.codex-taskbar-companion`，与安装目录分离；升级及卸载默认保留设置和历史。程序只在本机读取Codex数据，不保存对话正文或账号凭据，不采集遥测。

- 账户额度与本机Token是不同口径，Token不用来估算订阅额度。
- 今日额度从当日首个可用样本起算，缺失期间不补算。
- 任务时长包含工具等待，轮次之间的空档不计。
- “失败”仅取明确失败记录；不是完整的网络故障检测器。
- 更新读取本项目公开GitHub Release，每日检查、手动安装，不强制打断工作。

这是独立社区工具，不是OpenAI官方产品。

## 开发

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
./start.ps1
.venv/Scripts/python.exe -m unittest discover
./scripts/package.ps1 -Compiler 'C:/Path/To/Inno Setup/ISCC.exe'
```

版本由 `build_info.py` 统一维护。构建输出位于 `dist/` 和 `release/`，不进入Git。
日志位于用户数据目录的 `app.log`。开发版旧 `.runtime` 中的设置与额度记录会首次迁移，原文件保留。

行为定义见 [产品规范](docs/status-bar.md)，首版验收见 [发行规范](docs/release-v0.1.md)，发布流程见 [发布说明](docs/publishing.md)。

源代码采用MIT；字体和第三方组件保留各自许可，见 [THIRD_PARTY.md](THIRD_PARTY.md)。

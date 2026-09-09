"""Application copy only; project names and task titles remain user content."""

LANGUAGES = ('en', 'zh-CN')
COPY = {
    'Settings': '设置', 'Settings…': '设置…', 'Quit': '退出',
    'Language': '语言', 'Display': '显示',
    'Weekly quota': '周额度', '5-hour quota': '5 小时额度',
    'Reset countdown': '重置倒计时', 'Daily quota usage': '今日额度消耗',
    'Task rotation and counts': '任务轮播与计数',
    'Rotate quota display': '轮换显示额度', 'Week': '周', 'Today': '今日',
    'Open panels on hover': '悬停打开面板', 'Start at Windows sign-in': '登录 Windows 后启动',
    'Showing the last available quota.': '当前显示上次有效额度。',
    'Quota unavailable. Try again later.': '暂时无法读取额度，请稍后再试。',
    'Some data is unavailable. Showing the last available records.': '部分数据暂未更新，保留上次记录。',
    'Connecting to Codex…': '正在连接 Codex…',
    'Not enough taskbar space. Settings are available in the system tray.': '任务栏空间不足，可从系统托盘打开设置。',
    'Settings remain available in the system tray when all displays are off.': '所有显示关闭后，仍可从系统托盘打开设置。',
    'No project': '无项目', 'Side': '侧聊',
    'Running': '进行中', 'Unread': '未读', 'Failed': '失败', 'Stopped': '已停止', 'Recent': '今日其他',
    'Usage': '用量', 'Tasks': '任务列表',
    'Today · Tokens': '今日 · Token', 'This cycle · Tokens': '本周期 · Token',
    '{value}% remaining': '剩余 {value}%', 'Reset {time}': '重置 {time}',
    'Reset quota': '重置额度', 'Resetting…': '正在重置…', 'Retry reset': '重试重置',
    'Nothing to reset': '无需重置', 'Scheduled': '自然', 'Manual': '手动', 'Official': '官方',
    'Next reset': '下次重置', 'History · 100M': '历史 · 100M', 'No records yet': '暂无记录',
    'Expires': '到期时间', '{count} available': '{count} 次可用', 'Default': '默认', 'No credits': '暂无机会',
    'Continue the reset request with an unconfirmed result?': '继续上次未确认结果的重置请求？',
    'Use one quota reset credit?': '使用一次额度重置机会？',
    'Not provided': '未提供', 'Credit expires: {time}': '机会到期时间：{time}',
    'Cancel': '取消', 'Confirm reset': '确认重置',
    'Check for updates': '检查更新', 'Release repository not configured': '发布仓库尚未配置',
    'Checking for updates…': '正在检查更新…', 'Downloading update…': '正在下载更新…',
    'Update ready': '安装包已就绪', 'No release available yet': '尚未发布可更新版本',
    'Unable to check for updates': '暂时无法检查更新', 'Up to date': '已是最新版本',
    'Update to {version}': '更新至 {version}',
    'Version {version} is available. Update from Settings.': '新版本 {version} 可用，可从设置更新。',
}


def translate(language, key, **values):
    return (COPY[key] if language == 'zh-CN' else key).format(**values)


def project_label(value, language):
    return value or translate(language, 'No project')

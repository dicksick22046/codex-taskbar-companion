"""Small Win32 helpers for an unactivated taskbar-adjacent tool window."""
import ctypes
from ctypes import wintypes as w

OPEN_SETTINGS_MESSAGE = 0x8000 + 42
user32 = ctypes.windll.user32
user32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.FindWindowW.argtypes = [w.LPCWSTR, w.LPCWSTR]
user32.FindWindowW.restype = w.HWND
user32.FindWindowExW.argtypes = [w.HWND, w.HWND, w.LPCWSTR, w.LPCWSTR]
user32.FindWindowExW.restype = w.HWND
user32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = w.HWND
user32.GetShellWindow.restype = w.HWND
user32.GetDesktopWindow.restype = w.HWND
user32.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
user32.GetDpiForWindow.argtypes = [w.HWND]
user32.GetDpiForWindow.restype = w.UINT
user32.IsWindow.argtypes = [w.HWND]
user32.IsWindow.restype = w.BOOL
user32.IsWindowVisible.argtypes = [w.HWND]
user32.IsWindowVisible.restype = w.BOOL
user32.IsIconic.argtypes = [w.HWND]
user32.IsIconic.restype = w.BOOL
user32.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindow.argtypes = [w.HWND, ctypes.c_uint]
user32.GetWindow.restype = w.HWND
user32.SetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.WindowFromPoint.argtypes=[w.POINT]
user32.WindowFromPoint.restype=w.HWND
user32.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int]


class MonitorInfo(ctypes.Structure):
    _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD)]


user32.MonitorFromWindow.argtypes=[w.HWND,w.DWORD];user32.MonitorFromWindow.restype=w.HANDLE
user32.GetMonitorInfoW.argtypes=[w.HANDLE,ctypes.POINTER(MonitorInfo)]


def pointer_over(hwnd,x,y):
    return user32.WindowFromPoint(w.POINT(round(x),round(y)))==hwnd


class ClickHook:
    """Route clicks on our transparent strip and observe outside dismissal."""
    def __init__(self, callback):
        class MouseInfo(ctypes.Structure):
            _fields_=[('point',w.POINT),('data',w.DWORD),('flags',w.DWORD),('time',w.DWORD),('extra',ctypes.c_size_t)]
        signature=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,w.WPARAM,w.LPARAM)
        user32.CallNextHookEx.argtypes=[w.HHOOK,ctypes.c_int,w.WPARAM,w.LPARAM]
        user32.CallNextHookEx.restype=ctypes.c_ssize_t
        def dispatch(code,message,pointer):
            if code>=0 and message in (0x0201,0x0202,0x0204,0x0205):
                point=ctypes.cast(pointer,ctypes.POINTER(MouseInfo)).contents.point
                try:
                    button={0x0201:'left',0x0202:'left_up',0x0204:'right',0x0205:'right_up'}[message]
                    if callback(point.x,point.y,button):return 1
                except Exception:
                    pass
            return user32.CallNextHookEx(None,code,message,pointer)
        self.proc=signature(dispatch)
        user32.SetWindowsHookExW.argtypes=[ctypes.c_int,signature,w.HINSTANCE,w.DWORD]
        user32.SetWindowsHookExW.restype=w.HHOOK
        ctypes.windll.kernel32.GetModuleHandleW.restype=w.HINSTANCE
        self.handle=user32.SetWindowsHookExW(14,self.proc,ctypes.windll.kernel32.GetModuleHandleW(None),0)
        if not self.handle:raise OSError('无法建立状态条点击监听')

    def close(self):
        if self.handle:
            user32.UnhookWindowsHookEx.argtypes=[w.HHOOK]
            user32.UnhookWindowsHookEx(self.handle);self.handle=None


def dpi_aware():
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))


def animations_enabled():
    value=w.BOOL(True)
    user32.SystemParametersInfoW.argtypes=[w.UINT,w.UINT,ctypes.c_void_p,w.UINT]
    return bool(value.value) if user32.SystemParametersInfoW(0x1042,0,ctypes.byref(value),0) else True


def rect(hwnd):
    box = w.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(box)):
        return None
    return box.left, box.top, box.right, box.bottom


def foreground_fullscreen():
    hwnd=user32.GetForegroundWindow()
    if not hwnd or hwnd in (user32.GetShellWindow(),user32.GetDesktopWindow()):return False
    class_name=ctypes.create_unicode_buffer(128);user32.GetClassNameW(hwnd,class_name,128)
    if class_name.value in ('Shell_TrayWnd','Shell_SecondaryTrayWnd'):return False
    bounds=rect(hwnd)
    if not bounds:return False
    info=MonitorInfo();info.size=ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd,2),ctypes.byref(info)):return False
    screen=info.monitor
    return bounds[0]<=screen.left and bounds[1]<=screen.top and bounds[2]>=screen.right and bounds[3]>=screen.bottom


def placement(minimum_width=240):
    tray = user32.FindWindowW("Shell_TrayWnd", None)
    box = rect(tray) if tray else None
    if not box:
        return None
    left, top, right, bottom = box
    scale = max(1, user32.GetDpiForWindow(tray) / 96)
    inset = round(8 * scale)
    height = round(30 * scale)
    rebar = user32.FindWindowExW(tray, None, "ReBarWindow32", None)
    icons = rect(rebar) if rebar else None
    start = user32.FindWindowExW(tray, None, "Start", None)
    start_box = rect(start) if start else None
    edges = [r[0] for r in (start_box, icons) if r]
    if not edges or bottom-top > right-left:return None
    available = min(edges)-left-inset*2
    width = round(min(540*scale,available))
    if width < minimum_width*scale:return None
    x = left+inset
    y = top+max(0,(bottom-top-height)//2)
    screen_bottom = user32.GetSystemMetrics(1)
    hidden = top >= screen_bottom - 2 or bottom - top < 3
    foreground = user32.GetForegroundWindow()
    fg = rect(foreground) if foreground else None
    if fg and foreground not in (tray, user32.GetShellWindow(), user32.GetDesktopWindow()):
        hidden = hidden or (fg[0] <= left and fg[1] <= 0 and fg[2] >= right and fg[3] >= bottom)
    return x, y, width, height, scale, hidden


def topmost(hwnd):
    user32.SetWindowPos(hwnd, w.HWND(-1), 0, 0, 0, 0, 0x0010 | 0x0001 | 0x0002)


def floating_window(hwnd,keep_on_top):
    """Detach from Explorer; change Z band only on presentation/recovery changes."""
    if user32.GetWindowLongPtrW(hwnd,-8):user32.SetWindowLongPtrW(hwnd,-8,0)
    user32.SetWindowPos(hwnd,w.HWND(-1 if keep_on_top else -2),0,0,0,0,0x0010|0x0001|0x0002)


def follow_taskbar(hwnd):
    """Keep the strip above its taskbar owner when Windows raises shell surfaces."""
    tray = user32.FindWindowW("Shell_TrayWnd", None)
    if tray and user32.GetWindowLongPtrW(hwnd, -8) != tray:
        user32.SetWindowLongPtrW(hwnd, -8, tray)  # GWLP_HWNDPARENT: owner, not child parenting.
        insert_after=user32.GetWindow(tray,3)
        if insert_after!=hwnd:user32.SetWindowPos(hwnd,insert_after or 0,0,0,0,0,0x0213)
        return
    if not tray:return
    previous=user32.GetWindow(hwnd,3)  # GW_HWNDPREV walks toward the top of the Z order.
    seen={hwnd}
    while previous and previous not in seen:
        if previous==tray:
            insert_after=user32.GetWindow(tray,3)
            if insert_after!=hwnd:
                # Restore only our position above the taskbar; preserve focus and owner order.
                user32.SetWindowPos(hwnd,insert_after or 0,0,0,0,0,0x0010|0x0001|0x0002|0x0200)
            return
        seen.add(previous)
        previous=user32.GetWindow(previous,3)


def hide_border(hwnd):
    dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
    dwm.argtypes = [w.HWND, w.DWORD, ctypes.c_void_p, w.DWORD]
    color = w.DWORD(0xFFFFFFFE)  # DWMWA_COLOR_NONE
    dwm(hwnd, 34, ctypes.byref(color), ctypes.sizeof(color))
    policy = w.DWORD(1)  # DWMNCRP_DISABLED: no non-client frame on tool windows.
    dwm(hwnd, 2, ctypes.byref(policy), ctypes.sizeof(policy))
    backdrop = w.DWORD(1)  # DWMSBT_NONE: the strip itself stays transparent.
    dwm(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    corners = w.DWORD(1)  # DWMWCP_DONOTROUND; popup corners are drawn by Qt.
    dwm(hwnd, 33, ctypes.byref(corners), ctypes.sizeof(corners))
    class Margins(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int) for name in ("left", "right", "top", "bottom")]
    class Blur(ctypes.Structure):
        _fields_ = [("flags", w.DWORD), ("enable", w.BOOL), ("region", w.HRGN), ("transition", w.BOOL)]
    api = ctypes.windll.dwmapi
    api.DwmExtendFrameIntoClientArea.argtypes = [w.HWND, ctypes.POINTER(Margins)]
    api.DwmEnableBlurBehindWindow.argtypes = [w.HWND, ctypes.POINTER(Blur)]
    api.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(Margins(0, 0, 0, 0)))
    api.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(Blur(1, False, None, False)))
    _set_accent(hwnd,0,0)


def _set_accent(hwnd,state,color):
    class Accent(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int) for name in ("state", "flags", "color", "animation")]
    class Composition(ctypes.Structure):
        _fields_ = [("attribute", ctypes.c_int), ("data", ctypes.c_void_p), ("size", ctypes.c_size_t)]
    accent = Accent(state, 0, ctypes.c_int(color).value, 0)
    value = Composition(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
    user32.SetWindowCompositionAttribute.argtypes = [w.HWND, ctypes.POINTER(Composition)]
    user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(value))


def popup_glass(hwnd):
    """Borderless rounded panels, with native backdrop effects disabled."""
    hide_border(hwnd)
    corners=w.DWORD(2)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,33,ctypes.byref(corners),ctypes.sizeof(corners))

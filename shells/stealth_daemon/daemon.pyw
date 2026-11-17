# -*- coding: utf-8 -*-
"""
Background Desktop Helper (daemon.pyw).
Hoạt động trực tiếp trên MỌI trình soạn thảo (Antigravity, VS Code, IDLE, Notepad++, Web LMS):
- Chỉ cần gõ hoặc dán đề bài vào file (không cần bôi đen hay bấm Ctrl+C trước!) rồi bấm:
  + Ctrl + Alt + 1 : Giải tức thì (Tầng 3 Offline RAG < 0.08s) -> Tự động dán đè code ra màn hình!
  + Ctrl + Alt + 2 : Giải bằng AI 3 Tầng + Chạy thử ngầm kiểm lỗi -> Tự động dán đè code ra màn hình!
  + Ctrl + Alt + 3 : Giải + Kiểm lỗi ngầm -> Tự động xóa comment và gõ từng ký tự ra màn hình (Bấm Esc để dừng)!
  + Ctrl + Alt + 4 : Tự động bắt Traceback sửa đoạn code đang bị lỗi trên màn hình -> Dán đè bản đã sửa!
  + Ctrl + Alt + 0 : Gỡ cài đặt và tắt tiến trình ngầm.
  + Alt + Shift + Delete : Tự hủy dấu vết & tắt tiến trình ngầm.
"""

import ctypes
from ctypes import wintypes
import os
import random
import sys
import threading
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core_engine.engine_pipeline import process_request  # noqa: E402

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Win32 Constants
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

VK_0 = 0x30
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34
VK_A = 0x41
VK_C = 0x43
VK_V = 0x56
VK_DELETE = 0x2E
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_HOME = 0x24
VK_END = 0x23
VK_BACK = 0x08
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_SCROLL = 0x91

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

HOTKEY_ALT_1 = 101
HOTKEY_ALT_2 = 102
HOTKEY_ALT_3 = 103
HOTKEY_ALT_4 = 104
HOTKEY_ALT_0_CLEAN = 197
HOTKEY_BACK_CLEAN = 198
HOTKEY_CLEANUP = 199

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]


def get_clipboard_text() -> str:
    for _ in range(8):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.015)
    else:
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr) or ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text: str) -> bool:
    if text is None:
        return False
    encoded = (text + "\0").encode("utf-16-le")
    for _ in range(8):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.015)
    else:
        return False
    try:
        user32.EmptyClipboard()
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h_mem:
            return False
        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            return False
        ctypes.memmove(ptr, encoded, len(encoded))
        kernel32.GlobalUnlock(h_mem)
        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        return True
    finally:
        user32.CloseClipboard()


def send_vk(vk: int, down: bool = True, up: bool = True) -> None:
    scan = user32.MapVirtualKeyW(vk, 0)
    inputs = []
    if down:
        ki_d = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=0, time=0, dwExtraInfo=0)
        inputs.append(INPUT(type=INPUT_KEYBOARD, u=_INPUTunion(ki=ki_d)))
    if up:
        ki_u = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)
        inputs.append(INPUT(type=INPUT_KEYBOARD, u=_INPUTunion(ki=ki_u)))
    if inputs:
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), ctypes.byref(arr), ctypes.sizeof(INPUT))


def wait_for_modifiers_release(timeout_sec: float = 1.2) -> None:
    """
    Đợi người dùng nhả phím Alt và phím số 1..4 trước khi gửi tổ hợp Ctrl+C / Ctrl+V
    để trình soạn thảo không bị nhận nhầm thành Ctrl+Alt+C hay Ctrl+Alt+V.
    """
    t0 = time.perf_counter()
    vks_to_check = (VK_MENU, VK_LMENU, VK_RMENU, VK_1, VK_2, VK_3, VK_4)
    while time.perf_counter() - t0 < timeout_sec:
        if not any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in vks_to_check):
            break
        time.sleep(0.015)

    # Dam bao nha hoàn toàn trạng thái phím Alt/Shift
    for vk_mod in (VK_MENU, VK_LMENU, VK_RMENU, VK_SHIFT):
        if user32.GetAsyncKeyState(vk_mod) & 0x8000:
            send_vk(vk_mod, down=False, up=True)
    time.sleep(0.02)


def send_ctrl_combo(vk_key: int) -> None:
    """Gửi tổ hợp Ctrl + <Phím> (Ctrl+C, Ctrl+A, Ctrl+V) chuẩn xác cho VS Code / Antigravity / IDLE."""
    send_vk(VK_CONTROL, down=True, up=False)
    time.sleep(0.015)
    send_vk(vk_key, down=True, up=False)
    time.sleep(0.015)
    send_vk(vk_key, down=False, up=True)
    time.sleep(0.015)
    send_vk(VK_CONTROL, down=False, up=True)


def auto_grab_editor_text() -> str:
    """
    Tự động lấy văn bản đề bài từ trình soạn thảo đang mở:
    1. Thử Ctrl+C để lấy vùng đang bôi đen.
    2. Nếu chưa bôi đen (Clipboard trống hoặc chỉ 1 dòng ngắn), tự động Ctrl+A -> Ctrl+C
       để lấy toàn bộ nội dung file và giữ vùng chọn để lát nữa Ctrl+V ghi đè sạch sẽ!
    """
    old_clip = get_clipboard_text()
    set_clipboard_text("")
    time.sleep(0.02)

    send_ctrl_combo(VK_C)
    time.sleep(0.09)
    grabbed = get_clipboard_text()

    non_empty_lines = [ln for ln in grabbed.splitlines() if ln.strip()]
    if len(non_empty_lines) <= 1:
        # Nguoi dung chua boi den khoi de bai -> Tu dong boi den toan bo file (Ctrl+A -> Ctrl+C)
        send_ctrl_combo(VK_A)
        time.sleep(0.06)
        send_ctrl_combo(VK_C)
        time.sleep(0.09)
        grabbed_all = get_clipboard_text()
        if grabbed_all.strip():
            grabbed = grabbed_all

    if not grabbed.strip():
        return old_clip
    return grabbed


def send_unicode_char(ch: str) -> None:
    if ch == "\r":
        return
    if ch == "\n":
        send_vk(VK_RETURN)
        time.sleep(0.01)
        # Xóa khoảng trắng auto-indent của VS Code / IDLE ở dòng mới: Home -> Shift+End -> Backspace
        send_vk(VK_HOME)
        send_vk(VK_SHIFT, down=True, up=False)
        send_vk(VK_END)
        send_vk(VK_SHIFT, down=False, up=True)
        send_vk(VK_BACK)
        return

    code_unit = ord(ch)
    ki_d = KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0)
    ki_u = KEYBDINPUT(
        wVk=0,
        wScan=code_unit,
        dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
        time=0,
        dwExtraInfo=0,
    )
    arr = (INPUT * 2)(
        INPUT(type=INPUT_KEYBOARD, u=_INPUTunion(ki=ki_d)),
        INPUT(type=INPUT_KEYBOARD, u=_INPUTunion(ki=ki_u)),
    )
    user32.SendInput(2, ctypes.byref(arr), ctypes.sizeof(INPUT))


def pulse_scroll_lock_led(duration_sec: float = 0.05) -> None:
    try:
        send_vk(VK_SCROLL)
        time.sleep(duration_sec)
        send_vk(VK_SCROLL)
    except Exception:
        pass


def stream_typewriter_output(code: str, cancelled=lambda: False) -> None:
    """
    Xóa vùng comment đang chọn và gõ tự động từng ký tự mượt mà (chuẩn thụt lề Python).
    Nhấn phím ESC bất kỳ lúc nào để dừng ngay lập tức.
    """
    send_vk(VK_BACK)
    time.sleep(0.08)
    for ch in code.replace("\r\n", "\n"):
        if cancelled() or user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
            break
        send_unicode_char(ch)
        time.sleep(random.uniform(0.004, 0.010))


class StealthDaemonApp:
    def __init__(self) -> None:
        self._busy = False
        self._stopping = False

    def handle_action(self, mode: str) -> None:
        if self._busy or self._stopping:
            return
        self._busy = True

        def _worker() -> None:
            try:
                wait_for_modifiers_release()
                if self._stopping:
                    return
                raw_input = auto_grab_editor_text()
                if not raw_input.strip():
                    return

                res = process_request(
                    raw_text=raw_input,
                    action_mode="full" if mode == "ghost" else mode,
                    verify_shadow=True,
                )
                if not res.code or self._stopping:
                    return

                set_clipboard_text(res.code)
                pulse_scroll_lock_led(0.05)

                if mode == "ghost":
                    stream_typewriter_output(res.code, cancelled=lambda: self._stopping)
                else:
                    # Tu dong dan (Ctrl+V) de code hien ngay lap tuc tren man hinh!
                    wait_for_modifiers_release(timeout_sec=0.3)
                    if not self._stopping:
                        send_ctrl_combo(VK_V)
            finally:
                self._busy = False

        threading.Thread(target=_worker, daemon=True).start()

    def self_cleanup_and_exit(self) -> None:
        self._stopping = True
        success = False
        try:
            wait_for_modifiers_release(timeout_sec=0.4)
            from go_cai_dat import uninstall_everything
            success = uninstall_everything(kill_self_process=True)
            banner = "# [Ctrl+Alt+0: " + (
                "DA GO CAI DAT. Reload Window trong cac IDE dang mo.]\n"
                if success else
                "GO CAI DAT CHUA HOAN TAT. Chay go_cai_dat.bat de xem loi.]\n"
            )
            set_clipboard_text(banner)
            send_ctrl_combo(VK_V)
            time.sleep(0.15)
            set_clipboard_text("")
            pulse_scroll_lock_led(0.05)
        except Exception as exc:
            # pythonw không có console: hiển thị lỗi thay vì im lặng báo thành công.
            user32.MessageBoxW(None, f"Go cai dat chua hoan tat: {exc}", "Pylance Helper", 0x10)
        os._exit(0 if success else 1)

    def run(self) -> None:
        all_hks = (
            HOTKEY_ALT_1,
            HOTKEY_ALT_2,
            HOTKEY_ALT_3,
            HOTKEY_ALT_4,
            HOTKEY_ALT_0_CLEAN,
            HOTKEY_BACK_CLEAN,
            HOTKEY_CLEANUP,
        )
        for hk in all_hks:
            user32.UnregisterHotKey(None, hk)

        # Dung Ctrl+Alt+1..4,0 cho IDLE/Notepad++ de KHONG tranh chap phim Alt+1..4,0 cua VS Code / Antigravity Extension!
        mod_combo = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
        user32.RegisterHotKey(None, HOTKEY_ALT_1, mod_combo, VK_1)
        user32.RegisterHotKey(None, HOTKEY_ALT_2, mod_combo, VK_2)
        user32.RegisterHotKey(None, HOTKEY_ALT_3, mod_combo, VK_3)
        user32.RegisterHotKey(None, HOTKEY_ALT_4, mod_combo, VK_4)
        user32.RegisterHotKey(None, HOTKEY_ALT_0_CLEAN, mod_combo, VK_0)
        user32.RegisterHotKey(
            None, HOTKEY_BACK_CLEAN, MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_BACK
        )
        user32.RegisterHotKey(
            None, HOTKEY_CLEANUP, MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_DELETE
        )

        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    hk_id = msg.wParam
                    if hk_id == HOTKEY_ALT_1:
                        self.handle_action("instant")
                    elif hk_id == HOTKEY_ALT_2:
                        self.handle_action("full")
                    elif hk_id == HOTKEY_ALT_3:
                        self.handle_action("ghost")
                    elif hk_id == HOTKEY_ALT_4:
                        self.handle_action("self_fix")
                    elif hk_id in (HOTKEY_ALT_0_CLEAN, HOTKEY_BACK_CLEAN, HOTKEY_CLEANUP):
                        self.self_cleanup_and_exit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            for hk in all_hks:
                user32.UnregisterHotKey(None, hk)


if __name__ == "__main__":
    StealthDaemonApp().run()

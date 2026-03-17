import time
import ctypes
from ctypes import wintypes, Structure, Union


# Structures
class KEYBDINPUT(Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    )


class MOUSEINPUT(Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    )


class HARDWAREINPUT(Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUT_UNION(Union):
    _fields_ = (("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT))


class INPUT(Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", INPUT_UNION))


# Literals

INPUT_KEYBOARD = 1

KEYEVENTF_KEYDOWN = 0x0
KEYEVENTF_KEYUP = 0x02
KEYEVENTF_UNICODE = 0x04

VK_BACKSPACE = 0x08
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_DELETE = 0x2E
VK_END = 0x23
VK_HOME = 0x24
VK_SHIFT = 0x10
VK_CTRL = 0x11


class InputMethod:
    def __init__(self, tracing_keys: set[int] = None, rate_limit: int = 512):
        self._tracing_keys = tracing_keys or {VK_ESCAPE}
        self._trace_flags: dict[int, bool] = {}
        for key in self._tracing_keys:
            self._trace_flags[key] = False

        self._SendInput = ctypes.windll.user32.SendInput
        self._SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self._SendInput.restype = wintypes.UINT

        self._rate_limit = rate_limit
        self._cancel_check = False

    def cancel_input(self) -> None:
        """
        取消输入。
        """
        self._cancel_check = True

    def is_canceled(self) -> bool:
        """
        判断是否已取消输入。
        """
        return self._cancel_check

    def is_sending(self, key: int) -> bool:
        """
        判断是否正在发送指定键。
        此方法仅对已追踪的键有效，对于未进行追踪的键始终返回 `False`。

        :param key: 键值
        :return: 是否正在发送

        """
        return self._trace_flags.get(key, False)

    def send_string(
        self,
        text: str,
        char_delay_ms: int = 20,
        *,
        esc_before_enter=False,
        clear_line_after_enter=False,
        skip_leading_whitespace=False,
    ) -> None:
        """
        逐字符发送文本，每个字符后暂停 char_delay_ms 毫秒。
        支持取消检查（_cancel_check 为 True 时终止）。
        优化了特殊键的发送方式，减少卡顿，提高兼容性。
        """

        if not text:
            return

        self._cancel_check = False
        delay = char_delay_ms / 1000.0
        counter = 0

        if skip_leading_whitespace:
            text = "\n".join([x.lstrip() for x in text.split("\n")])
        for ch in text:
            if self._cancel_check:
                return

            if ch == "\n":
                # 可选：Esc 键关闭补全（单独发送，加短延迟）
                if esc_before_enter:
                    self.send_key(VK_ESCAPE, delay_after=delay)

                # 发送 Enter 键
                self.send_key(VK_RETURN, delay_after=delay)

                # 可选：清空当前行 (Shift+Home + Backspace)
                if clear_line_after_enter:
                    self.try_clear_line(delay_before=delay, delay_after=delay)
            else:
                # 普通 Unicode 字符
                self.send_char(ch, delay)

            counter += 1
            # 避免输入过快，挤爆缓冲区
            if delay == 0 and counter % self._rate_limit == 0:
                time.sleep(0.01)

    def send_char(self, char: str, delay=0.0):
        encoded_char = char[:1].encode("utf-16-le")
        events = []
        for i in range(0, len(encoded_char), 2):
            code_unit = int.from_bytes(encoded_char[i : i + 2], "little")
            events.append(
                self._create_key_event(scan=code_unit, flags=KEYEVENTF_UNICODE)
            )
            events.append(
                self._create_key_event(
                    scan=code_unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                )
            )
        self._send_events(events)
        time.sleep(delay)

    def send_key(self, key: int, *, delay_before=0.0, delay_after=0.0):
        self._update_flags({key: True})
        time.sleep(delay_before)
        self._send_events(
            [
                self._create_key_event(vk=key, flags=KEYEVENTF_KEYDOWN),
                self._create_key_event(vk=key, flags=KEYEVENTF_KEYUP),
            ]
        )
        time.sleep(delay_after)
        self._update_flags({key: False})

    def try_clear_line(self, count: int = 1, *, delay_before=0.0, delay_after=0.0):
        self._update_flags({VK_CTRL: True, VK_HOME: True, VK_DELETE: True})
        time.sleep(delay_before)
        for _ in range(count):
            self.send_key(VK_HOME)
            self._send_events(
                [
                    self._create_key_event(vk=VK_CTRL, flags=KEYEVENTF_KEYDOWN),
                    self._create_key_event(vk=VK_DELETE, flags=KEYEVENTF_KEYDOWN),
                    self._create_key_event(vk=VK_DELETE, flags=KEYEVENTF_KEYUP),
                    self._create_key_event(vk=VK_CTRL, flags=KEYEVENTF_KEYUP),
                ]
            )
        time.sleep(delay_after)
        self._update_flags({VK_CTRL: False, VK_HOME: False, VK_DELETE: False})

    def _update_flags(self, states: dict[int, bool]):
        for code, state in states.items():
            if code in self._tracing_keys:
                self._trace_flags[code] = state

    # 按键事件创建
    def _create_key_event(self, vk=0, scan=0, flags=0):
        ki = KEYBDINPUT()
        ki.wVk = vk
        ki.wScan = scan
        ki.dwFlags = flags
        ki.time = 0
        ki.dwExtraInfo = 0
        input_struct = INPUT()
        input_struct.type = INPUT_KEYBOARD
        input_struct.union.ki = ki
        return input_struct

    # 发送按键事件
    def _send_events(self, events):
        if not events:
            return

        array_type = INPUT * len(events)
        input_array = array_type(*events)
        sent = self._SendInput(len(events), input_array, ctypes.sizeof(INPUT))
        if sent != len(events):
            print(f"警告：只发送了 {sent}/{len(events)} 个事件")

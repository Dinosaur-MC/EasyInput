from typing import Callable, Set
import tkinter as tk
from tkinter import ttk


# ==================== 热键设置对话框 ====================
class HotkeyDialog:
    def __init__(self, parent: tk.Tk, callback: Callable[[Set[str], str], None]):
        self.parent = parent
        self.callback = callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置热键")
        self.dialog.geometry("300x150")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        ttk.Label(self.dialog, text="请按下您希望使用的热键组合...").pack(pady=10)
        self.key_label = ttk.Label(self.dialog, text="", font=("Arial", 12))
        self.key_label.pack(pady=5)

        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=10)
        self.ok_btn = ttk.Button(
            btn_frame, text="确定", command=self.ok, state=tk.DISABLED
        )
        self.ok_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.cancel).pack(
            side=tk.LEFT, padx=5
        )

        # 绑定键盘事件
        self.dialog.bind("<KeyPress>", self.on_key_press)
        self.dialog.bind("<KeyRelease>", self.on_key_release)

        self.pressed_keys: Set[str] = set()
        self.modifiers_recorded: Set[str] = set()
        self.main_key: str | None = None
        self.dialog.focus_set()
        self.ok_btn.focus_set()

        # 将窗口居中于父窗口
        self.dialog.update_idletasks()  # 确保窗口大小已计算
        x = (
            parent.winfo_rootx()
            + (parent.winfo_width() // 2)
            - (self.dialog.winfo_width() // 2)
        )
        y = (
            parent.winfo_rooty()
            + (parent.winfo_height() // 2)
            - (self.dialog.winfo_height() // 2)
        )
        self.dialog.geometry(f"+{x}+{y}")

    def on_key_press(self, event: tk.Event):
        keysym = event.keysym
        if keysym.lower() == "escape":
            self.cancel()
            return
        elif keysym.lower() == "return" and self.main_key is not None:
            self.ok()
            return

        if keysym in self.pressed_keys:
            return
        self.pressed_keys.add(keysym)

        mod = self.get_modifier(keysym)
        if mod:
            self.modifiers_recorded.add(mod)
        else:
            # 如果是非修饰键，则记录
            self.main_key = self.normalize_key(keysym)
        self.update_display()

    def on_key_release(self, event: tk.Event):
        keysym = event.keysym
        if keysym in self.pressed_keys:
            self.pressed_keys.remove(keysym)

        # 当所有键都释放时，如果有主键，则启用确定按钮
        if not self.pressed_keys:
            if self.main_key is not None:
                self.ok_btn.config(state=tk.NORMAL)
            else:
                for modifier in self.modifiers_recorded:
                    if modifier in self.pressed_keys:
                        self.pressed_keys.remove(modifier)
                self.modifiers_recorded.clear()
        self.update_display()  # 更新显示（但记录不会改变）

    def get_modifier(self, keysym: str):
        if keysym in ("Control_L", "Control_R", "Control"):
            return "ctrl"
        elif keysym in ("Shift_L", "Shift_R", "Shift"):
            return "shift"
        elif keysym in ("Alt_L", "Alt_R", "Alt"):
            return "alt"
        elif keysym in ("Super_L", "Super_R", "Super", "Win_L", "Win_R"):
            return "cmd"
        else:
            return None

    def normalize_key(self, keysym: str):
        if len(keysym) == 1 and keysym.isalpha():
            return keysym.lower()
        else:
            return keysym.lower()

    def update_display(self):
        parts = list(self.modifiers_recorded)
        if self.main_key:
            parts.append(self.main_key)
        self.key_label.config(text=" + ".join(parts) if parts else "（无）")

    def ok(self):
        if self.main_key:
            self.callback(self.modifiers_recorded.copy(), self.main_key)
            self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()

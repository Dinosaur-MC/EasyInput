# EasyInput - 万能文本输入器

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/Dinosaur-MC/EasyInput/total.svg)](https://github.com/Dinosaur-MC/EasyInput/releases/latest)
[![GitHub Stars](https://img.shields.io/github/stars/Dinosaur-MC/EasyInput?style=social)](https://github.com/Dinosaur-MC/easyinput)

## EasyInput - Universal Text Input

A lightweight, customizable text input tool for Windows that simulates keyboard input directly via `SendInput`, bypassing the clipboard to support any Unicode character. Perfect for inserting special symbols, code snippets, or frequently used text with customizable hotkeys.

### Features

- **Direct Keyboard Simulation**: Uses Windows API `SendInput` to simulate keystrokes, avoiding clipboard limitations.
- **Unicode Support**: Input any Unicode character, including emojis and special symbols.
- **Customizable Hotkeys**: Set your preferred key combinations (e.g., Ctrl+Alt+F8) to trigger text insertion.
- **Text Presets**: Save and manage reusable text snippets (e.g., signatures, code templates).
- **Flexible Configuration**: Adjust input delay, confirmation prompts, and whitespace handling via `config.json`.
- **Escape Key Handling**: Option to send Escape before Enter to prevent accidental actions in some applications.

### Installation & Usage

1. **Prerequisites**:
   - Python 3.12+
   - Install dependencies using [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended):
     ```bash
     uv sync
     ```
   - This command will create a virtual environment and install all dependencies specified in `pyproject.toml`
   - Required packages: `pynput`

2. **Run the Application**:
   ```bash
   uv run main.py
   ```

3. **Configure Hotkeys**:
   - Click "设置热键" (Set Hotkey) to define your preferred key combination.
   - The hotkey will trigger the selected preset text input after a countdown.

4. **Manage Presets**:
   - Use the interface to add, edit, or delete text presets.
   - Presets are saved in `config.json`.

### Configuration (`config.json`)

The configuration file allows fine-tuning of input behavior:

```json
{
  "presets": {
    "name": "text content"
  },
  "hotkey_modifiers": ["ctrl", "alt"],
  "hotkey_key": "f8",
  "delay": 3,
  "confirm": false,
  "char_delay": 20,
  "esc_before_enter": false,
  "clear_line_after_enter": false,
  "skip_leading_whitespace": false
}
```

- `presets`: Dictionary of saved text snippets.
- `hotkey_modifiers`: List of modifier keys (ctrl, alt, shift, win).
- `hotkey_key`: The main key (e.g., f8, space).
- `delay`: Countdown seconds before input (0-10).
- `confirm`: Show confirmation dialog before input.
- `char_delay`: Delay between keystrokes in milliseconds.
- `esc_before_enter`: Send Escape key before Enter.
- `clear_line_after_enter`: Clear input line after sending Enter.
- `skip_leading_whitespace`: Skip leading whitespace characters in input.

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### GitHub

Source code available at: [https://github.com/Dinosaur-MC/EasyInput.git](https://github.com/Dinosaur-MC/EasyInput.git)

---

## EasyInput - 万能文本输入器

一个轻量级、可定制的Windows文本输入工具，通过`SendInput`直接模拟键盘输入，绕过剪贴板限制，支持任意Unicode字符。适用于插入特殊符号、代码片段或常用文本，并支持自定义热键。

### 功能特性

- **直接键盘模拟**: 使用Windows API `SendInput`模拟按键，避免剪贴板限制。
- **Unicode支持**: 输入任何Unicode字符，包括表情符号和特殊符号。
- **自定义热键**: 设置您喜欢的组合键（如Ctrl+Alt+F8）来触发文本输入。
- **文本预设**: 保存和管理可重用的文本片段（如签名、代码模板）。
- **灵活配置**: 通过`config.json`调整输入延迟、确认提示和空白处理。
- **Esc键处理**: 可选择在Enter前发送Esc键，防止在某些应用中误操作。

### 安装与使用

1. **前置条件**:
   - Python 3.12+
   - 安装依赖包（推荐使用 [uv](https://docs.astral.sh/uv/getting-started/installation/)）:
     ```bash
     uv sync
     ```
   - 该命令将创建虚拟环境并安装`pyproject.toml`中指定的所有依赖
   - 所需包: `pynput`

2. **运行程序**:
   ```bash
   uv run main.py
   ```

3. **配置热键**:
   - 点击"设置热键"按钮定义您喜欢的组合键。
   - 热键将触发选中的预设文本输入，带有倒计时。

4. **管理预设**:
   - 使用界面添加、编辑或删除文本预设。
   - 预设保存在`config.json`中。

### 配置文件 (`config.json`)

配置文件允许微调输入行为:

```json
{
  "presets": {
    "name": "text content"
  },
  "hotkey_modifiers": ["ctrl", "alt"],
  "hotkey_key": "f8",
  "delay": 3,
  "confirm": false,
  "char_delay": 20,
  "esc_before_enter": false,
  "clear_line_after_enter": false,
  "skip_leading_whitespace": false
}
```

- `presets`: 保存的文本片段字典。
- `hotkey_modifiers`: 修饰键列表（ctrl, alt, shift, win）。
- `hotkey_key`: 主键（如f8, space）。
- `delay`: 输入前的倒计时秒数（0-10）。
- `confirm`: 输入前显示确认对话框。
- `char_delay`: 按键之间的延迟（毫秒）。
- `esc_before_enter`: 在Enter前发送Esc键。
- `clear_line_after_enter`: 在发送Enter后清除输入行。
- `skip_leading_whitespace`: 跳过输入中的前导空白字符。

### 许可证

本项目采用MIT许可证，详见[LICENSE](LICENSE)文件。

### GitHub

源代码地址: [https://github.com/Dinosaur-MC/EasyInput.git](https://github.com/Dinosaur-MC/EasyInput.git)

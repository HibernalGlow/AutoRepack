from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Container, Horizontal, Grid, VerticalScroll
from textual.widgets import (
    Header, 
    Footer, 
    Button, 
    Input, 
    Label, 
    SelectionList,
    RadioSet
)
from textual.screen import ModalScreen
from textual.binding import Binding
from typing import Dict, List, Union, Optional, Any, Callable, Tuple
import subprocess
import argparse
import sys
import os
import pyperclip
import yaml
from datetime import datetime
import shutil
import json
import multiprocessing
from multiprocessing import Process, Pipe
from typing import Tuple, Dict, List, Any, Callable, Union
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class ConfigOption:
    """配置选项基类"""
    def __init__(self, label: str, id: str, arg: str):
        self.label = label
        self.id = id
        self.arg = arg

class CheckboxOption(ConfigOption):
    """复选框选项"""
    def __init__(self, label: str, id: str, arg: str, default: bool = False):
        super().__init__(label, id, arg)
        self.default = default

class InputOption(ConfigOption):
    """输入框选项"""
    def __init__(self, label: str, id: str, arg: str, default: str = "", placeholder: str = ""):
        super().__init__(label, id, arg)
        self.default = default
        self.placeholder = placeholder

class PresetConfig:
    """预设配置类"""
    def __init__(
        self,
        name: str,
        description: str,
        checkbox_options: List[str],  # 选中的checkbox id列表
        input_values: Dict[str, str]  # parameter id和值的字典 (包括 input 和 select)
    ):
        self.name = name
        self.description = description
        self.checkbox_options = checkbox_options
        self.input_values = input_values

class ConfigTemplate(App[None]):
    """通用配置界面模板"""
    
    # 类级变量作为CSS缓存
    _css_cache = None
    
    # 使用属性装饰器实现CSS懒加载和缓存
    @property
    def CSS(self) -> str:
        if ConfigTemplate._css_cache is None:
            try:
                css_path = os.path.join(os.path.dirname(__file__), "textual_preset.css")
                with open(css_path, "r", encoding="utf-8") as f:
                    ConfigTemplate._css_cache = f.read()
            except Exception as e:
                import logging
                logging.error(f"无法读取CSS文件: {e}")
                # 提供基础CSS作为回退选项
        return ConfigTemplate._css_cache
        
    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("r", "run", "运行"),
        Binding("d", "toggle_dark", "切换主题"),
    ]

    def __init__(
        self,
        program: str,
        title: str = "配置界面",
        checkbox_options: List[CheckboxOption] = None,
        parameter_options: List[InputOption] = None, # <-- Only InputOption now
        extra_args: List[str] = None,
        demo_mode: bool = False,
        presets: List[PresetConfig] = None,
        on_run: Callable[[dict], None] = None  # 新增回调函数参数
    ):
        super().__init__()
        self.program = program
        self.title = title
        self.checkbox_options = checkbox_options or []
        self.parameter_options = parameter_options or [] # <-- Use the new name, only InputOption
        self.extra_args = extra_args or []
        self.demo_mode = demo_mode
        self.presets = {preset.name: preset for preset in (presets or [])}  # 转换为字典
        self._checkbox_states = {}
        self._input_values = {}
        self.on_run_callback = on_run  # 保存回调函数

    def _load_presets(self) -> dict:
        """加载预设配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f).get('presets', {})
        except Exception as e:
            self.notify(f"加载预设配置失败: {e}", severity="error")
            return {}

    def _save_preset(self, name: str, description: str = "") -> None:
        """保存当前配置为预设"""
        try:
            # 收集当前配置
            selection_list = self.query_one(SelectionList)
            selected_checkboxes = selection_list.selected

            # 收集参数值 (Input only)
            current_input_values = {}
            for opt in self.parameter_options:
                widget = self.query_one(f"#{opt.id}")
                if isinstance(widget, Input):
                    current_input_values[opt.id] = widget.value

            # 创建新预设
            new_preset = PresetConfig(
                name=name,
                description=description,
                checkbox_options=[opt.id for opt in self.checkbox_options
                                if opt.id in selected_checkboxes],
                input_values=current_input_values # <-- Save collected input values
            )

            # 更新预设列表
            self.presets[name] = new_preset
            
            # 刷新预设列表
            preset_list = self.query_one("#preset-list")
            preset_list.remove_children()
            if self.presets:
                preset_list.mount(RadioSet(
                    *[f"{name}\n{preset.description}" 
                      for name, preset in self.presets.items()],
                    id="preset-radio"
                ))
            
            self.notify("预设配置已保存")
            
        except Exception as e:
            self.notify(f"保存预设配置失败: {e}", severity="error")

    def _apply_preset(self, preset_name: str) -> None:
        """应用预设配置"""
        if preset_name not in self.presets:
            return

        preset = self.presets[preset_name]

        # 清空并设置参数值 (Input only)
        for opt in self.parameter_options:
            widget = self.query_one(f"#{opt.id}")
            preset_value = preset.input_values.get(opt.id)

            if isinstance(widget, Input):
                widget.value = preset_value if preset_value is not None else ""

        # 清空所有复选框选择
        selection_list = self.query_one(SelectionList)
        selection_list.deselect_all()
        
        # 只选择预设中指定的选项
        for option_id in preset.checkbox_options:
            selection_list.select(option_id)

        self._update_command_preview()
        self.notify(f"已应用预设配置: {preset_name}")

    def action_toggle_dark(self) -> None:
        """切换暗色/亮色主题"""
        self.theme = "textual-light" if self.theme == "nord" else "nord"

    def compose(self) -> ComposeResult:
        """生成界面"""
        yield Header(show_clock=True)

        with ScrollableContainer(id="main-container"):
            # 按钮组 - 水平排列在顶部
            with Container(id="buttons-container"):
                yield Button("运行", classes="primary", id="run-btn")
                yield Button("复制命令", classes="copy", id="copy-btn")
                yield Button("退出", classes="error", id="quit-btn")

            # 顶部容器：预设配置和按钮
            with Container(id="top-container"):
                # 预设配置区域
                with Container(id="presets-container"):
                    with Container(id="preset-list"):
                        # 如果有预设配置，显示RadioSet
                        if self.presets:
                            yield RadioSet(
                                *[f"{name}\n{preset.description}" 
                                  for name, preset in self.presets.items()],
                                id="preset-radio"
                            )

            # 命令预览区域
            with Container(id="command-preview"):
                yield Label("", id="command")

            # 功能开关组
            if self.checkbox_options:
                with Container(classes="config-group"):
                    yield Label("功能开关", classes="group-title")
                    yield SelectionList[str](
                        *[(opt.label, opt.id, opt.default) for opt in self.checkbox_options]
                    )

            # 参数设置组 (Only Input)
            if self.parameter_options:
                with Container(classes="config-group"):
                    yield Label("参数设置", classes="group-title")
                    with Container(classes="params-container"):
                        for opt in self.parameter_options: # Now only InputOption
                            with Container(classes="param-item"):
                                yield Label(f"{opt.label}:")
                                # Always use Input
                                yield Input(
                                    value=opt.default,
                                    placeholder=opt.placeholder,
                                    id=opt.id
                                )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮事件处理"""
        if event.button.id == "quit-btn":
            self.exit()
        elif event.button.id == "run-btn":
            self.action_run()
        elif event.button.id == "copy-btn":
            self.action_copy_command()
        elif event.button.id == "save-preset":
            # 弹出对话框获取预设名称和描述
            class SavePresetDialog(ModalScreen[tuple[str, str]]):
                BINDINGS = [("escape", "cancel", "取消")]
                
                def compose(self) -> ComposeResult:
                    with Grid(id="dialog-grid"):
                        yield Label("预设名称:")
                        yield Input(id="preset-name")
                        yield Label("描述:")
                        yield Input(id="preset-desc")
                        yield Button("保存", variant="primary")
                        yield Button("取消", variant="error")

                def on_button_pressed(self, event: Button.Pressed) -> None:
                    if event.button.label == "保存":
                        name = self.query_one("#preset-name").value
                        desc = self.query_one("#preset-desc").value
                        self.dismiss((name, desc))
                    else:
                        self.dismiss(None)

                def action_cancel(self) -> None:
                    self.dismiss(None)

            async def show_save_dialog() -> None:
                result = await self.push_screen(SavePresetDialog())
                if result:
                    name, desc = result
                    if name:
                        self._save_preset(name, desc)

            self.app.run_worker(show_save_dialog())

        elif event.button.id == "delete-preset":
            # 删除当前选中的预设
            radio_set = self.query_one("#preset-radio", RadioSet)
            if radio_set and radio_set.pressed_index is not None:
                preset_name = list(self.presets.keys())[radio_set.pressed_index]
                try:
                    del self.presets[preset_name]
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        yaml.dump({'presets': self.presets}, f, allow_unicode=True)
                    
                    # 刷新预设列表
                    preset_list = self.query_one("#preset-list")
                    preset_list.remove_children()
                    if self.presets:
                        preset_list.mount(RadioSet(
                            *[f"{name}\n{preset.description}" 
                              for name, preset in self.presets.items()],
                            id="preset-radio"
                        ))
                    self.notify("预设配置已删除")
                except Exception as e:
                    self.notify(f"删除预设配置失败: {e}", severity="error")
        elif event.button.id.startswith("preset-"):
            # 应用预设配置
            preset_name = event.button.id[7:]  # 去掉"preset-"前缀
            self._apply_preset(preset_name)

    def _update_command_preview(self) -> None:
        """更新命令预览"""
        # 使用简化的python命令前缀
        cmd = ["python"]
        
        # 添加程序路径（去掉多余的引号）
        program_path = self.program.strip('"')
        cmd.append(program_path)

        # 添加选中的功能选项
        selection_list = self.query_one(SelectionList)
        if selection_list:
            selected_options = selection_list.selected
            for opt in self.checkbox_options:
                if opt.id in selected_options:
                    cmd.append(opt.arg)

        # 添加参数选项 (Input only)
        for opt in self.parameter_options:
            widget = self.query_one(f"#{opt.id}")
            value = None
            if isinstance(widget, Input):
                value = widget.value

            if value: # Append if value is not empty or None
                cmd.extend([opt.arg, str(value)]) # Ensure value is string

        # 添加额外参数
        if self.extra_args:
            cmd.extend(self.extra_args)

        # 更新预览
        command_label = self.query_one("#command")
        command_label.update(" ".join(cmd))

    def on_mount(self) -> None:
        """初始化"""
        # self.title = "配置界面"  # <-- 移除或注释掉这一行
        self.theme = "textual-light"  # 使用Textual自带的亮色主题
        self._adjust_layout()
        self._update_command_preview()
        # 设置定时器，每0.1秒更新一次命令预览 (Select变化也会触发Input变化事件，无需单独监听)
        self.set_interval(0.1, self._update_command_preview)
    def on_resize(self) -> None:
        """窗口大小改变时调整布局"""
        self._adjust_layout()

    def _adjust_layout(self) -> None:
        """根据容器宽度调整布局类名"""
        container = self.query_one("#main-container")
        if container:
            width = container.size.width
            # 移除所有布局类
            container.remove_class("-narrow")
            container.remove_class("-wide")
            
            # 根据宽度添加相应的类
            if width < 60:
                container.add_class("-narrow")
            elif width > 100:
                container.add_class("-wide")

    # --- Event handlers for updating command preview ---
    # Input changes trigger this
    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_command_preview()

    # SelectionList changes trigger these
    def on_selection_list_highlighted_changed(self) -> None:
        """当选择列表高亮变化时更新预览"""
        self._update_command_preview()

    def on_selection_list_selection_changed(self) -> None:
        """当选择列表选择变化时更新预览"""
        self._update_command_preview()

    def on_selection_list_selected(self) -> None:
        """当选择列表选择确认时更新预览"""
        self._update_command_preview()

    def on_selection_list_option_selected(self) -> None:
        """当选择列表选项被选中时更新预览"""
        self._update_command_preview()

    def on_selection_list_option_deselected(self) -> None:
        """当选择列表选项被取消选中时更新预览"""
        self._update_command_preview()

    def on_selection_list_option_highlighted(self) -> None:
        """当选择列表选项被高亮时更新预览"""
        self._update_command_preview()

    # 也可以尝试直接监听空格键的按下
    def on_key(self, event) -> None:
        """监听键盘事件"""
        if event.key == "space":
            self._update_command_preview()

    def action_copy_command(self) -> None:
        """复制命令到剪贴板"""
        try:
            command = self.query_one("#command").renderable
            pyperclip.copy(command)
            # 可以添加一个临时提示，表示复制成功
            self.notify("命令已复制到剪贴板", timeout=1)
        except Exception as e:
            self.notify(f"复制失败: {e}", severity="error")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """当选择预设配置时"""
        if event.radio_set.id == "preset-radio":
            preset_name = list(self.presets.keys())[event.index]
            self._apply_preset(preset_name)

    def on_radio_set_clicked(self, event: RadioSet.Clicked) -> None:
        """处理点击事件"""
        if event.radio_set.id == "preset-radio":
            if event.click_count == 2:  # 检查是否是双击
                preset_name = list(self.presets.keys())[event.radio_set.pressed_index]
                self._apply_preset(preset_name)
                self.action_run()

    def action_run(self) -> None:
        """收集配置并执行回调函数"""
        params = self._collect_parameters()
        if self.on_run_callback:
            # 先退出界面再执行回调
            self.exit()
            self.on_run_callback(params)  # 此时界面已关闭
        else:
            self._execute_command_line(params)

    def _collect_parameters(self) -> dict:
        """收集所有参数到字典"""
        params = {
            'options': {},
            'inputs': {}, # Combined inputs and selects here
            'preset': None
        }
        
        # 收集复选框状态
        selection_list = self.query_one(SelectionList)
        if selection_list:
            selected_options = selection_list.selected
            for opt in self.checkbox_options:
                params['options'][opt.arg] = opt.id in selected_options

        # 收集参数值 (Input only)
        for opt in self.parameter_options:
            widget = self.query_one(f"#{opt.id}")
            value = None
            if isinstance(widget, Input):
                value = widget.value.strip()

            # Store using the argument name as key, consistent with argparse
            params['inputs'][opt.arg] = value

        # 仅在存在预设时收集
        if self.presets:
            radio_set = self.query_one("#preset-radio", RadioSet)
            if radio_set and radio_set.pressed_index is not None:
                preset_name = list(self.presets.keys())[radio_set.pressed_index]
                params['preset'] = preset_name

        return params

    def _execute_command_line(self, params: dict) -> None:
        """原有的命令行执行逻辑"""
        # 构建命令时只使用有值的输入框
        cmd_args = [self.program.strip('"')]

        # 添加选中的功能选项
        selection_list = self.query_one(SelectionList)
        selected_options = selection_list.selected
        for opt in self.checkbox_options:
            if opt.id in selected_options:
                cmd_args.append(opt.arg)

        # 添加参数选项 (Input only)
        for opt in self.parameter_options:
            widget = self.query_one(f"#{opt.id}")
            value = None
            if isinstance(widget, Input):
                value = widget.value.strip()

            if value: # Append if value is not empty or None
                cmd_args.extend([opt.arg, str(value)]) # Ensure value is string

        # 添加额外参数
        if self.extra_args:
            cmd_args.extend(self.extra_args)

        # 从程序路径获取脚本名称
        script_path = os.path.normpath(self.program)  # 获取完整路径并规范化
        # script_name = os.path.splitext(os.path.basename(script_path))[0]  # 去除扩展名
        script_name = self.title
        # 生成时间戳 - 格式为 "MM-DD HH:MM"
        current_time = datetime.now().strftime("%m-%d %H:%M") # 不再需要时间戳
        terminal_title = f'{script_name} {current_time}' # 旧的标题生成方式

        # 获取Python路径
        python_path = os.getenv('PYTHON_PATH')
        

        # 尝试使用Windows Terminal
        try:
            # 优先使用Windows Terminal的PowerShell
            subprocess.run([
                'wt.exe', 
                '--window', '0',
                'new-tab', 
                '--title', terminal_title,  # 使用脚本名称和时间戳作为标题
                'powershell.exe', 
                '-NoExit', 
                '-Command', 
                f"& {{{python_path} '{script_path}' {' '.join(cmd_args[1:])}}}"  # 修改PowerShell命令格式
            ], check=True, timeout=10, shell=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # 保底方案：直接使用PowerShell
            subprocess.run(
                ['powershell.exe', '-NoExit', '-Command', f"& {{{python_path} '{script_path}' {' '.join(cmd_args[1:])}}}"],  # 修改PowerShell命令格式
                check=True,
                shell=True
            )
        finally:
            self.exit()  # 确保最后退出

    def get_checkbox_state(self, checkbox_id: str) -> bool:
        """获取复选框状态"""
        return checkbox_id in self._checkbox_states

    def get_input_value(self, input_id: str) -> str:
        """获取输入框值"""
        return self._input_values.get(input_id, "")

# 预设配置示例 - JSON 格式

def create_config_app(
    program: str,
    checkbox_options: List[tuple] = None,
    input_options: List[tuple] = None, # Keep for backward compatibility? Or remove? Let's keep for now.
    parameter_options: List[tuple] = None, # New combined list
    title: str = "配置界面",
    extra_args: List[str] = None,
    demo_mode: bool = False,
    preset_configs: dict = None,
    on_run: Callable[[dict], None] = None,  
    parser: argparse.ArgumentParser = None,  # parser 参数
    rich_mode: bool = False  # 是否使用Rich模式
) -> Union[ConfigTemplate, Tuple[bool, dict], dict]:
    """
    创建配置界面的便捷函数
    
    Args:
        program: 要运行的程序路径
        checkbox_options: 复选框选项列表，每项格式为 (label, id, arg) 或 (label, id, arg, default)
        input_options: [DEPRECATED] Use parameter_options instead. 输入框选项列表
        parameter_options: 参数选项列表 (Input/Select)，每项格式见下方
        title: 界面标题
        extra_args: 额外的命令行参数
        demo_mode: 是否为演示模式
        preset_configs: 预设配置字典
        on_run: 运行回调函数
        parser: ArgumentParser实例，用于自动生成选项
        rich_mode: 是否使用Rich模式界面
    """
    # 如果使用Rich模式，直接调用rich_preset模块
    if rich_mode:
        try:
            from .rich_preset import create_config_app as rich_create_config_app
            result = rich_create_config_app(
                program=program,
                # Pass original lists or adapt rich_create_config_app
                checkbox_options=checkbox_options,
                input_options=input_options, # Or pass parsed parameter_options if rich handles it
                title=title,
                extra_args=extra_args,
                demo_mode=demo_mode,
                preset_configs=preset_configs,
                on_run=on_run,
                parser=parser
            )
            return result
        except ImportError:
            import logging
            logging.warning("无法导入rich_preset模块，将使用textual界面替代")
            # Fallback to Textual
    
    checkbox_opts_internal = []
    param_opts_internal = [] # Combined list for InputOption

    # 1. Process explicitly provided options (if any)
    if checkbox_options:
        for item in checkbox_options:
            # ... (existing checkbox processing) ...
            if len(item) == 4:
                label, id, arg, default = item
            else:
                label, id, arg = item
                default = False
            checkbox_opts_internal.append(CheckboxOption(label, id, arg, default))

    # Process combined parameter_options OR legacy input_options
    options_to_process = parameter_options if parameter_options else input_options
    if options_to_process:
        for item in options_to_process:
            # Treat all as InputOption: (label, id, arg, default, placeholder)
            label, id, arg, *rest = item
            default = rest[0] if len(rest) > 0 else ""
            placeholder = rest[1] if len(rest) > 1 else ""
            # If choices were provided (e.g., item[3] was a list), add them to placeholder
            if len(item) >= 4 and isinstance(item[3], (list, tuple)):
                 choices_str = ", ".join(map(str, item[3]))
                 placeholder += f" (可选: {choices_str})"
            param_opts_internal.append(InputOption(label, id, arg, default, placeholder))


    # 2. If parser is provided and options were NOT explicitly provided, generate from parser
    elif parser: # Generate only if checkbox_options and parameter_options were None
        for action in parser._actions:
            # 跳过帮助选项和位置参数
            if action.dest == 'help' or not action.option_strings:
                continue

            # 获取选项名称和帮助信息
            opt_name = action.option_strings[0]  # 使用第一个选项字符串
            # Use help as label, fallback to dest
            label = action.help or action.dest.replace('_', ' ').title()
            opt_id = action.dest # Use dest for ID, usually more stable

            if isinstance(action, argparse._StoreTrueAction):
                # 布尔标志 -> 复选框
                checkbox_opts_internal.append(CheckboxOption(label, opt_id, opt_name, action.default))
            else:
                # 其他带值的参数 (including those with choices) -> 输入框
                default = str(action.default) if action.default is not None else ""
                placeholder = f"默认: {default}" if default else ""
                # If choices exist, add them to the placeholder
                if action.choices:
                    choices_str = ", ".join(map(str, action.choices))
                    placeholder += f" (可选: {choices_str})"
                param_opts_internal.append(InputOption(label, opt_id, opt_name, default, placeholder))

    # 处理预设配置 (No change needed here, input_values handles both)
    preset_configs = preset_configs or {}
    preset_list = []
    for name, config in preset_configs.items():
        preset_list.append(PresetConfig(
            name=name,
            description=config.get("description", ""),
            checkbox_options=config.get("checkbox_options", []),
            input_values=config.get("input_values", {})
        ))

    
    # 正常模式，返回应用实例
    return ConfigTemplate(
        program=program,
        title=title,
        checkbox_options=checkbox_opts_internal,
        parameter_options=param_opts_internal, # <-- Pass the InputOption list
        extra_args=extra_args,
        demo_mode=demo_mode,
        presets=preset_list,
        on_run=on_run  # 传递回调函数
    )

# 使用示例
if __name__ == "__main__":
    # 演示用例
    parser = argparse.ArgumentParser(description='Test argument parser')
    parser.add_argument('--feature1', action='store_true', help='功能选项1')
    parser.add_argument('--feature2', action='store_true', help='功能选项2')
    parser.add_argument('--number', type=int, default=100, help='数字参数')
    parser.add_argument('--text', type=str, help='文本参数')
    parser.add_argument('--choice', choices=['A', 'B', 'C'], default='A', help='选择参数 (现在是输入框)') # Updated help text
    PRESET_CONFIGS = {
        "默认配置": {
            "description": "基础配置示例",
            "checkbox_options": ["feature1"], # Use opt_id from parser (dest)
            "input_values": {
                "number": "100", # Use opt_id from parser (dest)
                "text": "",
                "choice": "A" # Use opt_id from parser (dest), value is now string input
            }
        },
        "快速模式": {
            "description": "优化性能的配置",
            "checkbox_options": ["feature1", "feature2"], # Use opt_id
            "input_values": {
                "number": "200",
                "text": "fast",
                "choice": "B" # Value is now string input
            }
        }
    }

    # Run Textual App (rich_mode=False or omitted)
    app = create_config_app(
        program="demo_program.py",
        # title="TUI配置界面演示 (无下拉选择)", # Updated title
        parser=parser, # Let it generate options from parser
        preset_configs=PRESET_CONFIGS,
        # rich_mode=True # Set to True to test rich mode (requires rich_preset.py update)
    )
    if app:
        app.run()
        # If on_run callback was used, result would be handled there.
        # If app.run() finishes without on_run, it means user quit.
        print("Textual app finished.")
    else:
         print("Failed to create Textual app.")


    # Example for rich_mode=True (requires rich_preset.py update)
    # print("\n--- Running with rich_mode=True ---")
    # result = create_config_app(
    #     program="demo_program.py",
    #     title="TUI配置界面演示",
    #     parser=parser,
    #     preset_configs=PRESET_CONFIGS,
    #     rich_mode=True
    # )
    # if result:
    #     print("Rich mode finished. User selected config:", result)
    # else:
    #     print("Rich mode cancelled or failed.")
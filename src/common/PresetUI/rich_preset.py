from __future__ import annotations

from typing import Dict, List, Union, Optional, Any, Callable, Tuple
import subprocess
import argparse
import sys
import os
import pyperclip
import yaml
import json
from datetime import datetime
import shutil
from pathlib import Path
import time

# rich库导入
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, InvalidResponse
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.padding import Padding
from rich.text import Text
from rich.box import Box, ROUNDED
from rich.style import Style
from rich import print as rprint
from rich.layout import Layout
from rich.live import Live
# rich库不包含checkbox模块

# 可选的dotenv导入
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 使用共同的类定义，保持兼容性
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

class SelectOption(ConfigOption):
    """下拉选择框选项"""
    def __init__(self, label: str, id: str, arg: str, choices: List[str], default: Optional[str] = None):
        super().__init__(label, id, arg)
        # Ensure choices are strings
        self.choices = [str(c) for c in choices]
        # Ensure default is a string and exists in choices, otherwise use the first choice or None
        str_default = str(default) if default is not None else None
        if str_default in self.choices:
            self.default = str_default
        elif self.choices:
            self.default = self.choices[0]
        else:
            self.default = None

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

class RichConfigApp:
    """使用Rich库实现的配置应用"""
    
    def __init__(
        self,
        program: str,
        title: str = "配置界面",
        checkbox_options: List[CheckboxOption] = None,
        parameter_options: List[Union[InputOption, SelectOption]] = None, # <-- Use combined list
        extra_args: List[str] = None,
        demo_mode: bool = False,
        presets: List[PresetConfig] = None
    ):
        self.console = Console()
        self.program = program
        self.title = title
        self.checkbox_options = checkbox_options or []
        self.parameter_options = parameter_options or [] # <-- Store combined list
        self.extra_args = extra_args or []
        self.demo_mode = demo_mode
        self.presets = {preset.name: preset for preset in (presets or [])}
        self._checkbox_states = {opt.id: opt.default for opt in self.checkbox_options}
        # Initialize parameter values (both input and select)
        self._parameter_values = {}
        for opt in self.parameter_options:
             self._parameter_values[opt.id] = opt.default
        self._selected_preset = None
        self._preset_selected = False
    
    def _generate_command_preview(self) -> str:
        """生成命令预览字符串"""
        # 使用简化的python命令前缀
        cmd = ["python"]
        
        # 添加程序路径（去掉多余的引号）
        program_path = self.program.strip('"')
        cmd.append(program_path)

        # 添加选中的功能选项
        for opt in self.checkbox_options:
            if self._checkbox_states.get(opt.id, False):
                cmd.append(opt.arg)

        # 添加参数选项 (Input 和 Select)
        for opt in self.parameter_options:
            value = self._parameter_values.get(opt.id, "")
            # Ensure value is treated as string, especially for Select which might return None initially
            str_value = str(value) if value is not None else ""
            if str_value: # Only add if there's a non-empty value
                cmd.extend([opt.arg, str_value])

        # 添加额外参数
        if self.extra_args:
            cmd.extend(self.extra_args)

        return " ".join(cmd)
    
    def _apply_preset(self, preset_name: str) -> None:
        """应用预设配置"""
        if preset_name not in self.presets:
            return

        preset = self.presets[preset_name]
        
        # 重置所有复选框
        for opt in self.checkbox_options:
            self._checkbox_states[opt.id] = False
            
        # 设置预设中指定的复选框
        for option_id in preset.checkbox_options:
            self._checkbox_states[option_id] = True
            
        # 重置所有参数值 (Input 和 Select)
        for opt in self.parameter_options:
            self._parameter_values[opt.id] = opt.default # Reset to default

        # 设置预设中指定的参数值
        for option_id, value in preset.input_values.items():
            if option_id in self._parameter_values:
                # Find the option to check if it's a SelectOption and validate choice
                option = next((opt for opt in self.parameter_options if opt.id == option_id), None)
                if isinstance(option, SelectOption):
                    # Ensure the preset value is valid for the Select choices
                    if value in option.choices:
                        self._parameter_values[option_id] = value
                    else:
                        # If invalid, keep the default (already set) or log a warning
                        self.console.print(f"[yellow]警告: 预设 '{preset_name}' 的参数 '{option_id}' 值 '{value}' 无效，使用默认值 '{self._parameter_values[option_id]}'")
                else: # For InputOption
                    self._parameter_values[option_id] = value

        self._selected_preset = preset_name

    def _generate_preset_command(self, preset_name: str) -> str:
        """根据预设配置生成命令字符串"""
        if preset_name not in self.presets:
            return ""
            
        preset = self.presets[preset_name]
        
        # 临时保存当前状态
        temp_checkbox_states = self._checkbox_states.copy()
        temp_parameter_values = self._parameter_values.copy() # <-- Use parameter values
        
        # 应用预设设置
        self._apply_preset(preset_name)
        
        # 生成命令
        cmd = self._generate_command_preview()
        
        # 恢复临时状态
        self._checkbox_states = temp_checkbox_states
        self._parameter_values = temp_parameter_values # <-- Restore parameter values
        
        return cmd
        
    def _display_presets(self) -> None:
        """显示预设配置选项"""
        if not self.presets:
            return
        
        # 先显示剪贴板内容
        try:
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                self.console.print(Panel(
                    Text(clipboard_content, style="yellow"),
                    title="剪贴板内容",
                    border_style="yellow"
                ))
                self.console.print("")  # 添加空行分隔
        except Exception as e:
            self.console.print(f"[red]无法读取剪贴板内容: {str(e)}[/]")
            
        # 显示预设配置
        preset_table = Table(box=ROUNDED, border_style="blue", title="预设配置")
        preset_table.add_column("序号", justify="center", style="cyan", no_wrap=True)
        preset_table.add_column("名称", style="green")
        preset_table.add_column("描述", style="yellow")
        preset_table.add_column("命令行参数", style="magenta")
        
        for i, (name, preset) in enumerate(self.presets.items(), 1):
            # 生成此预设的命令行参数
            cmd_preview = self._generate_preset_command(name)
            # 只保留参数部分（去掉python和程序路径）
            cmd_parts = cmd_preview.split(" ")
            if len(cmd_parts) > 2:
                cmd_args = " ".join(cmd_parts[2:])
            else:
                cmd_args = "(无参数)"
                
            preset_table.add_row(
                str(i), 
                name, 
                preset.description,
                cmd_args
            )
        
        self.console.print(preset_table)
        
        # 底部显示操作说明
        self.console.print("\n[bold]操作说明[/]: ")
        self.console.print("• 输入 [bold cyan]预设序号[/] (如 [bold cyan]2[/]): 选择预设并继续配置")
        self.console.print("• 直接回车: 跳过预设配置")
        
        # 让用户选择预设
        if self.presets:
            preset_choice = Prompt.ask(
                "请选择预设配置",
                default="1"
            )
            
            choice = preset_choice.strip()
            
            # 检查是否为双位数(如22表示运行预设2)
            if len(choice) == 2 and choice[0] == choice[1] and choice.isdigit():
                try:
                    preset_idx = int(choice[0]) - 1
                    if 0 <= preset_idx < len(self.presets):
                        preset_name = list(self.presets.keys())[preset_idx]
                        self._apply_preset(preset_name)
                        self._selected_preset = preset_name
                        self._preset_selected = True
                        self.console.print(f"[green]已选择并立即运行预设: {preset_name}[/]")
                        # 设置标志表明已请求执行
                        self._execution_requested = True
                        return
                    else:
                        self.console.print("[yellow]无效的预设序号，跳过预设配置[/]")
                        self._preset_selected = False
                except ValueError:
                    self.console.print("[yellow]输入格式错误，跳过预设配置[/]")
                    self._preset_selected = False
            # 单个数字表示选择该预设
            elif choice.isdigit():
                preset_idx = int(choice) - 1
                # 检查是否为0(跳过)或有效的预设序号
                if choice == "0":
                    self.console.print("[yellow]跳过预设配置[/]")
                    self._preset_selected = False
                elif 0 <= preset_idx < len(self.presets):
                    preset_name = list(self.presets.keys())[preset_idx]
                    self._apply_preset(preset_name) # Apply preset values
                    self._selected_preset = preset_name
                    self._preset_selected = True
                    self.console.print(f"[green]已应用预设配置: {preset_name}[/]")
                    return # Return after applying preset
                else:
                    self.console.print("[yellow]无效的预设序号，跳过预设配置[/]")
                    self._preset_selected = False
            else:
                self.console.print("[yellow]输入格式错误，跳过预设配置[/]")
                self._preset_selected = False
        
    def _display_title(self) -> None:
        """显示标题"""
        self.console.print(Panel(f"[bold blue]{self.title}[/]", 
                                 border_style="blue"))
        
    def _display_command_preview(self) -> None:
        """显示命令预览"""
        command = self._generate_command_preview()
        self.console.print(Panel(
            Text(command, style="bold green"), 
            title="命令预览", 
            border_style="green"
        ))
    
    def _display_checkbox_options(self) -> None:
        """显示复选框选项"""
        if not self.checkbox_options:
            return
            
        self.console.print("[bold]功能选项[/]:")
        
        for i, opt in enumerate(self.checkbox_options, 1):
            checked = "✓" if self._checkbox_states.get(opt.id, False) else " "
            self.console.print(f"{i}. [{checked}] {opt.label} ({opt.arg})")
        
        # 让用户选择
        self.console.print("\n[bold cyan]选择功能选项（输入序号，多选用空格分隔，回车保持当前选择）[/]")
        choice = Prompt.ask("序号", default="")
        
        if choice.strip():
            try:
                selected_indices = [int(x.strip()) for x in choice.split() if x.strip()]
                
                # 处理选择
                for i, opt in enumerate(self.checkbox_options, 1):
                    # 切换选中状态
                    if i in selected_indices:
                        self._checkbox_states[opt.id] = not self._checkbox_states.get(opt.id, False)
                
                self.console.print("[green]已更新功能选择[/]")
            except ValueError:
                self.console.print("[yellow]无效的输入格式，保持当前选择[/]")
    
    def _display_parameter_options(self) -> None: # Renamed from _display_input_options
        """显示参数选项 (Input 和 Select)"""
        if not self.parameter_options:
            return

        self.console.print("\n[bold]参数设置[/]:")

        # Display current values first
        for i, opt in enumerate(self.parameter_options, 1):
            current_value = self._parameter_values.get(opt.id, opt.default)
            value_display = f"[cyan]{current_value}[/]" if current_value is not None else "[dim]未设置[/]"
            default_display = ""
            if isinstance(opt, InputOption):
                 default_display = f" [dim](默认: {opt.default or '空'})[/]" if opt.default != current_value else ""
                 placeholder = f" [dim]提示: {opt.placeholder}[/]" if opt.placeholder else ""
                 self.console.print(f"{i}. {opt.label} ({opt.arg}): {value_display}{default_display}{placeholder}")
            elif isinstance(opt, SelectOption):
                 default_display = f" [dim](默认: {opt.default or '无'})[/]" if opt.default != current_value else ""
                 choices_display = f" [dim]选项: {' / '.join(opt.choices)}[/]"
                 self.console.print(f"{i}. {opt.label} ({opt.arg}): {value_display}{default_display}{choices_display}")


        # Let user modify values
        self.console.print("\n[bold cyan]设置参数（格式: 序号 参数值，或仅输入序号以选择，空行结束）[/]")
        self.console.print("[dim]例如：\n1 新值\n3  (选择选项3)\n[/]")

        while True:
            line = Prompt.ask("输入", default="")
            if not line.strip():
                break

            parts = line.strip().split(None, 1)
            value_provided = len(parts) == 2
            idx_str = parts[0]

            try:
                idx = int(idx_str)
                if not (1 <= idx <= len(self.parameter_options)):
                    self.console.print(f"[yellow]序号 {idx} 超出范围[/]")
                    continue

                opt = self.parameter_options[idx-1]

                if isinstance(opt, InputOption):
                    value = parts[1] if value_provided else "" # Allow clearing value
                    self._parameter_values[opt.id] = value
                    self.console.print(f"[green]已设置 {opt.label}: {value or '(空)'}[/]")
                elif isinstance(opt, SelectOption):
                    if value_provided: # User provided a value directly
                        value = parts[1]
                        if value in opt.choices:
                            self._parameter_values[opt.id] = value
                            self.console.print(f"[green]已设置 {opt.label}: {value}[/]")
                        else:
                            self.console.print(f"[yellow]无效的值 '{value}'。可选值: {', '.join(opt.choices)}[/]")
                    else: # User only provided index, prompt for choice
                        try:
                            selected_choice = Prompt.ask(
                                f"为 '{opt.label}' 选择",
                                choices=opt.choices,
                                default=self._parameter_values.get(opt.id, opt.default) # Show current as default
                            )
                            self._parameter_values[opt.id] = selected_choice
                            self.console.print(f"[green]已选择 {opt.label}: {selected_choice}[/]")
                        except InvalidResponse:
                             self.console.print("[yellow]无效的选择。[/]")

            except ValueError:
                self.console.print("[yellow]无效的序号，请输入数字[/]")
            except Exception as e:
                 self.console.print(f"[red]处理输入时出错: {e}[/]")

    def _collect_parameters(self) -> dict:
        """收集所有参数到字典"""
        params = {
            'options': {},
            'inputs': {}, # Combined inputs and selects here
            'preset': None
        }
        
        # 收集复选框状态
        for opt in self.checkbox_options:
            params['options'][opt.arg] = self._checkbox_states.get(opt.id, False)

        # 收集参数值 (Input 和 Select)
        for opt in self.parameter_options:
            value = self._parameter_values.get(opt.id)
            # Store using the argument name as key, consistent with argparse
            # Ensure value is string for consistency, handle None
            params['inputs'][opt.arg] = str(value) if value is not None else ""

        # 设置选中的预设
        params['preset'] = self._selected_preset
        
        return params
    
    def run(self) -> dict:
        """运行配置应用，返回收集的参数"""
        self._execution_requested = False  # 初始化执行请求标志
        self._display_title()
        self._display_presets()
        
        # 如果在预设选择时使用了双数字快捷方式，已设置执行请求标志
        if hasattr(self, '_execution_requested') and self._execution_requested:
            params = self._collect_parameters()
            self.console.print("[green]配置已收集，正在运行...[/]")
            return params
        
        # 如果没有选择预设，显示常规配置选项
        if not self._preset_selected:
            self._display_checkbox_options()
            self._display_parameter_options() # <-- Call the updated method
        
        # 显示命令预览
        self._display_command_preview()
        
        # 默认执行运行操作，不再显示操作选项
        params = self._collect_parameters()
        self.console.print("[green]配置已收集，正在运行...[/]")
        return params
    
    def get_checkbox_state(self, checkbox_id: str) -> bool:
        """获取复选框状态"""
        return self._checkbox_states.get(checkbox_id, False)

    def get_input_value(self, input_id: str) -> str:
        """获取输入框值"""
        return self._parameter_values.get(input_id, "")

def create_config_app(
    program: str,
    checkbox_options: List[tuple] = None,
    input_options: List[tuple] = None, # Keep for backward compatibility
    parameter_options: List[tuple] = None, # New combined list
    title: str = "配置界面",
    extra_args: List[str] = None,
    demo_mode: bool = False,
    preset_configs: dict = None,
    on_run: Callable[[dict], None] = None,  
    parser: argparse.ArgumentParser = None,
    run_in_subprocess: bool = False,
    rich_mode: bool = False
) -> Any:
    """
    创建配置界面的便捷函数
    
    Args:
        program: 要运行的程序路径
        checkbox_options: 复选框选项列表，每项格式为 (label, id, arg) 或 (label, id, arg, default)
        input_options: 输入框选项列表，每项格式为 (label, id, arg, default, placeholder)
        parameter_options: 参数选项列表（包括 InputOption 和 SelectOption）
        title: 界面标题
        extra_args: 额外的命令行参数
        demo_mode: 是否为演示模式
        preset_configs: 预设配置字典
        on_run: 运行回调函数（在rich版本中忽略）
        parser: ArgumentParser实例，用于自动生成选项
        run_in_subprocess: 是否在子进程中运行（在rich版本中忽略）
        rich_mode: 是否使用rich模式返回结果
    
    Returns:
        返回一个包含配置结果的对象:
        - 如果rich_mode为True或没有parser，返回包含配置信息的字典
        - 如果提供了parser，返回解析好的args对象
        - 可以通过结果的result属性访问原始字典，通过args属性访问解析后的命名空间
    """
    # 如果提供了parser并且没有提供选项，则从parser自动生成
    if parser and not (checkbox_options or input_options or parameter_options):
        # 自动从parser生成选项
        checkbox_options = []
        # input_options = [] # Deprecated
        parameter_options = [] # Use the new combined list
        
        for action in parser._actions:
            # 跳过帮助选项和位置参数
            if action.dest == 'help' or not action.option_strings:
                continue
            
            # 获取选项名称和帮助信息
            opt_name = action.option_strings[0]  # 使用第一个选项字符串
            help_text = action.help or ""
            opt_id = action.dest # Use dest for ID
            
            if isinstance(action, argparse._StoreTrueAction):
                # 布尔标志 -> 复选框
                checkbox_options.append((help_text, opt_id, opt_name, action.default))
            elif action.choices:
                 # 带 choices 的参数 -> 下拉选择框
                 default = str(action.default) if action.default is not None else None
                 # Add to parameter_options as SelectOption format: (label, id, arg, choices, default)
                 parameter_options.append((help_text, opt_id, opt_name, action.choices, default))
            else:
                # 其他带值的参数 -> 输入框
                default = str(action.default) if action.default is not None else ""
                choices = "/".join(str(c) for c in action.choices) if action.choices else ""
                placeholder = choices or f"默认: {default}" if default else ""
                # Add to parameter_options as InputOption format: (label, id, arg, default, placeholder)
                parameter_options.append((help_text, opt_id, opt_name, default, placeholder))

    # 处理checkbox选项
    checkbox_opts = []
    if checkbox_options:
        for item in checkbox_options:
            if len(item) == 4:
                label, id, arg, default = item
            else:
                label, id, arg = item
                default = False
            checkbox_opts.append(CheckboxOption(label, id, arg, default))

    # 处理参数选项 (Input 和 Select)
    param_opts = []
    # Process combined parameter_options OR legacy input_options
    options_to_process = parameter_options if parameter_options else input_options
    if options_to_process:
        for item in options_to_process:
            # Heuristic to differentiate: check if 4th element is list/tuple (choices)
            if len(item) >= 4 and isinstance(item[3], (list, tuple)): # SelectOption: (label, id, arg, choices, default)
                label, id, arg, choices, *rest = item
                default = rest[0] if rest else None
                param_opts.append(SelectOption(label, id, arg, choices, default))
            else: # InputOption: (label, id, arg, default, placeholder)
                label, id, arg, *rest = item
                default = rest[0] if len(rest) > 0 else ""
                placeholder = rest[1] if len(rest) > 1 else ""
                param_opts.append(InputOption(label, id, arg, default, placeholder))

    # 处理预设配置
    preset_configs = preset_configs or {}
    preset_list = []
    for name, config in preset_configs.items():
        preset_list.append(PresetConfig(
            name=name,
            description=config.get("description", ""),
            checkbox_options=config.get("checkbox_options", []),
            input_values=config.get("input_values", {}) # Handles both input/select values
        ))

    # 创建应用实例
    app = RichConfigApp(
        program=program,
        title=title,
        checkbox_options=checkbox_opts,
        parameter_options=param_opts, # <-- Pass combined list
        extra_args=extra_args,
        demo_mode=demo_mode,
        presets=preset_list
    )
    
    # 运行应用并返回结果
    result = app.run()
    args = None
    
    # 如果提供了parser参数，将结果转换为args对象
    if parser and result:
        # 将配置结果转换为命令行参数列表
        cmd_args = []
        
        # 添加布尔选项
        for arg, enabled in result['options'].items():
            if enabled:
                cmd_args.append(arg)
        
        # 添加输入值选项
        for arg, value in result['inputs'].items():
            # Ensure value is treated as string, especially for Select which might be None
            str_value = str(value) if value is not None else ""
            if str_value:  # 只添加非空字符串值
                cmd_args.append(arg)
                cmd_args.append(str_value)
        
        # 添加额外参数
        if extra_args:
            cmd_args.extend(extra_args)
        
        # 使用parser解析参数并返回args对象
        args = parser.parse_args(cmd_args)
    
    # 创建一个结果对象，同时包含原始字典和args对象
    class ConfigResult:
        def __init__(self, result_dict, args_namespace):
            self.result = result_dict
            self.args = args_namespace
            
            # 将args的属性直接暴露在对象上
            if args_namespace:
                for key in dir(args_namespace):
                    if not key.startswith('_'):
                        setattr(self, key, getattr(args_namespace, key))
                        
            # 将result字典的内容也直接暴露
            if result_dict:
                for key, value in result_dict.items():
                    if not hasattr(self, key):  # 避免覆盖已有属性
                        setattr(self, key, value)
        
        def __getitem__(self, key):
            # 支持字典式访问
            if hasattr(self, key):
                return getattr(self, key)
            return None
    
    config_result = ConfigResult(result, args)
    
    # 根据rich_mode决定返回什么
    if rich_mode or not parser:
        return config_result.result  # 返回原始结果字典
    else:
        return config_result  # 返回组合对象，可以通过.args或.result访问

# 使用示例
if __name__ == "__main__":
    # 演示用例
    parser = argparse.ArgumentParser(description='Test argument parser')
    parser.add_argument('--feature1', action='store_true', help='功能选项1')
    parser.add_argument('--feature2', action='store_true', help='功能选项2')
    parser.add_argument('--number', type=int, default=100, help='数字参数')
    parser.add_argument('--text', type=str, help='文本参数')
    parser.add_argument('--choice', choices=['A', 'B', 'C'], default='A', help='选择参数')
    PRESET_CONFIGS = {
        "默认配置": {
            "description": "基础配置示例",
            "checkbox_options": ["feature1"], # Use opt_id (dest)
            "input_values": {
                "number": "100", # Use opt_id (dest)
                "text": "",
                # "path": "", # Assuming no path arg
                "choice": "A" # Use opt_id (dest)
            }
        },
        "快速模式": {
            "description": "优化性能的配置",
            "checkbox_options": ["feature1", "feature2"], # Use opt_id
            "input_values": {
                "number": "200",
                "text": "fast",
                # "path": "/tmp",
                "choice": "B" # Use opt_id
            }
        }
    }

    # 直接运行配置界面并获取结果
    result = create_config_app(
        program="demo_program.py",
        title="Rich配置界面演示 (含下拉选择)",
        parser=parser,
        preset_configs=PRESET_CONFIGS,
        rich_mode=True # Force rich mode for testing
    )

    # 处理结果 (rich_mode=True returns the dict)
    if result:
        print("\n--- 配置结果 ---")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Example of how to use the result with the original parser
        # (This part is usually done by the calling script)
        print("\n--- 解析为 Args ---")
        cmd_args_list = []
        for arg, enabled in result['options'].items():
            if enabled: cmd_args_list.append(arg)
        for arg, value in result['inputs'].items():
             str_value = str(value) if value is not None else ""
             if str_value:
                 cmd_args_list.extend([arg, str_value])
        try:
            parsed_args = parser.parse_args(cmd_args_list)
            print(parsed_args)
        except Exception as e:
            print(f"无法解析参数: {e}")

    else:
        print("操作被取消")
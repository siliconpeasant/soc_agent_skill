#!/usr/bin/env python3
"""
SoC Integrate - SOC顶层集成脚本
功能: 提取子模块端口、自动生成实例化、集成到顶层
"""

import re
import os
import sys
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime


class VerilogModule:
    """表示一个Verilog模块"""
    def __init__(self, name=""):
        self.name = name
        self.params = []      # [(name, default_value, type_str)]
        self.ports = []       # [(direction, width, name)]
    
    def __repr__(self):
        return f"Module({self.name}, ports={len(self.ports)}, params={len(self.params)})"


def extract_modules(filepath):
    """从Verilog文件中提取所有模块定义"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    modules = []
    
    # 找到所有 module 定义的位置
    module_pattern = r'\bmodule\s+(\w+)'
    module_matches = list(re.finditer(module_pattern, content))
    
    for i, match in enumerate(module_matches):
        module_name = match.group(1)
        start_pos = match.start()
        
        # 找到对应的 endmodule
        if i + 1 < len(module_matches):
            end_pos = module_matches[i + 1].start()
        else:
            # 查找最后一个 endmodule
            endmatch = list(re.finditer(r'\bendmodule\b', content[start_pos:]))
            if endmatch:
                end_pos = start_pos + endmatch[-1].end()
            else:
                end_pos = len(content)
        
        module_content = content[start_pos:end_pos]
        module = parse_module(module_name, module_content)
        modules.append(module)
    
    return modules


def parse_module(name, content):
    """解析单个模块的内容"""
    module = VerilogModule(name)
    
    # 提取参数 (parameter / localparam)
    param_pattern = r'parameter\s+(?:\[(\d+:\d+)\]\s+)?(\w+)\s*=\s*([^,;)]+)'
    for match in re.finditer(param_pattern, content):
        width = match.group(1) if match.group(1) else ""
        param_name = match.group(2).strip()
        default = match.group(3).strip()
        module.params.append((param_name, default, width))
    
    # 提取端口 - 支持多种格式
    # 格式1: input [7:0] port_name,
    # 格式2: output reg [7:0] port_name,
    # 格式3: inout wire port_name
    
    # 先找到端口声明区域（module 名后到 ); 之间）
    port_section = extract_port_section(content)
    if port_section:
        ports = parse_ports_from_section(port_section)
        module.ports = ports
    
    return module


def extract_port_section(content):
    """提取模块括号内的端口声明部分"""
    # 找到第一个 ( 和匹配的 )
    paren_start = content.find('(')
    if paren_start == -1:
        return None
    
    # 考虑参数列表 #(...)
    # 跳过 parameter 列表
    hash_pos = content.find('#')
    if hash_pos != -1 and hash_pos < paren_start:
        # 有参数，找到 # 后的 ( 和 )
        param_paren = content.find('(', hash_pos)
        if param_paren != -1:
            # 找到匹配的 )
            depth = 1
            pos = param_paren + 1
            while pos < len(content) and depth > 0:
                if content[pos] == '(':
                    depth += 1
                elif content[pos] == ')':
                    depth -= 1
                pos += 1
            # 真正的端口列表在参数列表之后
            paren_start = content.find('(', pos)
            if paren_start == -1:
                return None
    
    # 找到匹配的 )
    depth = 1
    pos = paren_start + 1
    while pos < len(content) and depth > 0:
        if content[pos] == '(':
            depth += 1
        elif content[pos] == ')':
            depth -= 1
        if depth == 0:
            break
        pos += 1
    
    if depth == 0:
        return content[paren_start+1:pos]
    return None


def parse_ports_from_section(section):
    """从端口声明字符串中解析端口列表"""
    ports = []
    
    # 清理注释
    section = re.sub(r'//.*', '', section)
    section = re.sub(r'/\*.*?\*/', '', section, flags=re.DOTALL)
    
    # 按逗号分割，但要处理数组维度中的逗号
    # 使用更智能的方法：按分号/逗号分割，但要注意括号匹配
    items = split_port_items(section)
    
    inherited = None
    for item in items:
        item = item.strip()
        if not item:
            continue
        port, inherited = parse_single_port(item, inherited)
        ports.append(port)
    
    return ports


def split_port_items(section):
    """智能分割端口声明项"""
    items = []
    current = ""
    paren_depth = 0
    bracket_depth = 0
    
    for char in section:
        if char == '(':
            paren_depth += 1
            current += char
        elif char == ')':
            paren_depth -= 1
            current += char
        elif char == '[':
            bracket_depth += 1
            current += char
        elif char == ']':
            bracket_depth -= 1
            current += char
        elif char == ',' and paren_depth == 0 and bracket_depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += char
    
    if current.strip():
        items.append(current.strip())
    
    return items


def parse_single_port(item, inherited=None):
    """解析单个端口声明"""
    # 模式: [direction] [reg/wire] [width] name
    # 简化模式: direction width name
    
    # 移除末尾的分号
    item = item.rstrip(';').strip()
    
    # 匹配方向
    direction_match = re.match(r'(input|output|inout)\b', item, re.IGNORECASE)
    if direction_match:
        direction = direction_match.group(1).lower()
        remaining = item[direction_match.end():].strip()
        inherited_width = ""
    elif inherited:
        direction, inherited_width = inherited
        remaining = item
    else:
        raise ValueError(
            "only ANSI-style port declarations are supported; "
            f"cannot parse port item: {item!r}"
        )
    
    # 跳过 reg/wire 关键字
    remaining = re.sub(r'^(reg|wire|logic|var)\b\s*', '', remaining, flags=re.IGNORECASE).strip()
    if re.match(r'^(signed|unsigned)\b', remaining, re.IGNORECASE) or '::' in remaining:
        raise ValueError(
            "signed or package-typed ports require a normalized wrapper: "
            f"{item!r}"
        )
    
    # 提取位宽 [msb:lsb]
    width = inherited_width
    width_match = re.match(r'(\[.*?\])', remaining)
    if width_match:
        width = width_match.group(1)
        remaining = remaining[width_match.end():].strip()
    
    # 剩余部分应该是端口名（可能包含 = default）
    name_match = re.match(r'(\w+)', remaining)
    if name_match:
        name = name_match.group(1)
        port = (direction, width, name)
        return port, (direction, width)

    raise ValueError(f"cannot parse ANSI port item: {item!r}")


def generate_instance(module, instance_name=None, signal_prefix=None, show_width=True):
    """生成实例化代码
    signal_prefix: 信号名前缀，用于多模块集成时避免冲突
    show_width: 是否在信号名后显示位宽
    """
    if not instance_name:
        instance_name = f"u_{module.name.lower()}"
    
    lines = []
    max_port_len = max(len(name) for _, _, name in module.ports) if module.ports else 0
    
    # 参数实例化
    if module.params:
        lines.append(f"    {module.name} #(")
        for i, (pname, pdefault, pwidth) in enumerate(module.params):
            comma = "," if i < len(module.params) - 1 else ""
            lines.append(f"        .{pname:<{max_port_len}} ({pdefault}){comma}")
        lines.append(f"    ) {instance_name} (")
    else:
        lines.append(f"    {module.name} {instance_name} (")
    
    # 端口实例化（位宽显示在信号名后: .port (signal[width])）
    for i, (direction, width, name) in enumerate(module.ports):
        comma = "," if i < len(module.ports) - 1 else ""
        w = resolve_param_width(width, module.params) if width else ""
        
        # 自动生成连接信号名
        prefix = signal_prefix if signal_prefix else ""
        if direction == "input":
            connect_sig = f"{prefix}{name}_i"
        elif direction == "output":
            connect_sig = f"{prefix}{name}_o"
        else:
            connect_sig = f"{prefix}{name}_io"
        
        if show_width and w:
            lines.append(f"        .{name:<{max_port_len}} ({connect_sig}{w}){comma}")
        else:
            lines.append(f"        .{name:<{max_port_len}} ({connect_sig}){comma}")
    
    lines.append("    );")
    return "\n".join(lines)


def generate_port_declarations(module):
    """生成端口声明代码（用于顶层）"""
    lines = []
    for direction, width, name in module.ports:
        width_str = f" {width}" if width else ""
        lines.append(f"    {direction}{width_str} {name},")
    return "\n".join(lines)


def generate_signal_declarations(module, signal_prefix=None):
    """生成内部信号声明
    signal_prefix: 信号名前缀，用于多模块集成时避免冲突
    """
    lines = []
    prefix = signal_prefix if signal_prefix else ""
    lines.append(f"    // {module.name} signals")
    for direction, width, name in module.ports:
        # 解析参数化位宽，尝试替换为默认值
        resolved_width = resolve_param_width(width, module.params)
        width_str = f" {resolved_width}" if resolved_width else ""
        if direction == "input":
            lines.append(f"    wire{width_str} {prefix}{name}_i;")
        elif direction == "output":
            lines.append(f"    wire{width_str} {prefix}{name}_o;")
        else:
            lines.append(f"    wire{width_str} {prefix}{name}_io;")
    return "\n".join(lines)


def resolve_param_width(width, params):
    """解析参数化位宽，尝试用参数默认值替换"""
    if not width:
        return ""
    
    # 检查位宽中是否包含参数名
    for pname, pdefault, pwidth in params:
        if pname in width:
            # 替换参数名为其默认值
            width = width.replace(pname, str(pdefault))
    
    return width


def generate_wrapper(module, wrapper_name=None):
    """生成wrapper模块 - 内部实例化直接连接wrapper端口"""
    if not wrapper_name:
        wrapper_name = f"{module.name}_wrap"
    
    lines = []
    max_port_len = max(len(name) for _, _, name in module.ports) if module.ports else 0
    max_dir_len = max(len(d) for d, _, _ in module.ports) if module.ports else 0
    max_width_len = max(len(w) if w else 0 for _, w, _ in module.ports) if module.ports else 0
    
    lines.append(f"module {wrapper_name} (")
    
    # 端口声明（对齐）
    port_decls = []
    for direction, width, name in module.ports:
        w = width if width else ""
        port_decls.append(f"    {direction:<{max_dir_len}} {w:<{max_width_len}} {name}")
    lines.append(",\n".join(port_decls))
    lines.append(");")
    lines.append("")
    
    # 实例化 - 直接用wrapper端口名连接（不加_i/_o后缀）
    instance_name = f"u_{module.name.lower()}_inst"
    
    if module.params:
        lines.append(f"    {module.name} #(")
        for i, (pname, pdefault, pwidth) in enumerate(module.params):
            comma = "," if i < len(module.params) - 1 else ""
            lines.append(f"        .{pname:<{max_port_len}} ({pdefault}){comma}")
        lines.append(f"    ) {instance_name} (")
    else:
        lines.append(f"    {module.name} {instance_name} (")
    
    for i, (direction, width, name) in enumerate(module.ports):
        comma = "," if i < len(module.ports) - 1 else ""
        w = resolve_param_width(width, module.params) if width else ""
        if w:
            lines.append(f"        .{name:<{max_port_len}} ({name}{w}){comma}")
        else:
            lines.append(f"        .{name:<{max_port_len}} ({name}){comma}")
    
    lines.append("    );")
    lines.append("")
    lines.append("endmodule")
    
    return "\n".join(lines)


def export_csv(module, filepath):
    """导出端口信息到CSV"""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Direction', 'Width', 'Port Name'])
        for direction, width, name in module.ports:
            writer.writerow([direction, width, name])
    print(f"Info: CSV exported to {filepath}")


def do_update(config, config_path, top_name_override=None, output_file_override=None, map_file_override=None):
    """核心 update 逻辑：根据配置重新生成顶层"""
    top_name = top_name_override if top_name_override else config['top_module']
    output_file = output_file_override if output_file_override else config.get('output_file')
    
    # === 第1步：如果顶层文件存在，先提取当前的手动修改 ===
    if output_file and os.path.exists(output_file):
        print(f"Info: Extracting current mappings from {output_file}")
        extracted = extract_map_from_top(output_file)
        extracted_map = extracted.get('mappings', {})
        extracted_shared = extracted.get('shared_signals', {})
        
        if extracted_map:
            config['mappings'] = extracted_map
            config['shared_signals'] = extracted_shared
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"Info: Synced {len(extracted_map)} mappings from top to config")
            for sig, conns in extracted_shared.items():
                print(f"  {sig}: {', '.join(conns)}")
            print()
    
    # 端口映射
    if map_file_override:
        with open(map_file_override, 'r') as f:
            map_data = json.load(f)
        port_map = map_data.get('mappings', {})
        print(f"Info: Using override port map from {map_file_override}")
    else:
        port_map = config.get('mappings', {})
        if port_map:
            print(f"Info: Using port map ({len(port_map)} mappings)")
    
    print(f"Info: Updating top module '{top_name}' from config: {config_path}")
    print(f"      Modules:")
    for mod in config['modules']:
        print(f"        - {mod['module_name']} ({mod['file']})")
    print()
    
    # 重新提取所有模块端口
    all_modules = []
    for mod in config['modules']:
        filepath = mod['file']
        if not os.path.exists(filepath):
            print(f"Error: Module file not found: {filepath}")
            sys.exit(1)
        modules = extract_modules(filepath)
        selected = next((m for m in modules if m.name == mod['module_name']), None)
        if not selected:
            print(f"Error: Module '{mod['module_name']}' not found in {filepath}")
            sys.exit(1)
        all_modules.append(selected)
        print(f"Info: Refreshed {mod['module_name']} from {filepath}")
    
    # === 计算端口变更 ===
    old_snapshot = config.get('port_snapshot', {})
    port_changes = {}
    deleted_ports = {}
    new_snapshot = {}
    has_changes = False
    
    for module in all_modules:
        mod_name = module.name
        old_ports = {p['name']: (p['direction'], p['width']) for p in old_snapshot.get(mod_name, [])}
        new_ports = {n: (d, w) for d, w, n in module.ports}
        new_snapshot[mod_name] = [{'direction': d, 'width': w, 'name': n} for d, w, n in module.ports]
        
        mod_changes = {}
        for port_name, (direction, width) in new_ports.items():
            if port_name not in old_ports:
                mod_changes[port_name] = 'NEW'
                has_changes = True
            elif old_ports[port_name] != (direction, width):
                mod_changes[port_name] = 'MOD'
                has_changes = True
        
        mod_deleted = []
        for port_name in old_ports:
            if port_name not in new_ports:
                direction, width = old_ports[port_name]
                mod_deleted.append((port_name, direction, width))
                has_changes = True
        
        if mod_deleted:
            deleted_ports[mod_name] = mod_deleted
            deleted_names = [p[0] for p in mod_deleted]
            print(f"  [!] {mod_name}: deleted ports: {', '.join(deleted_names)}")
        
        if mod_changes:
            port_changes[mod_name] = mod_changes
            for port_name, mark in mod_changes.items():
                print(f"  [{mark}] {mod_name}.{port_name}")
    
    if has_changes:
        print()
    
    # 重新生成顶层
    top_code = generate_top(all_modules, top_name, port_map, port_changes, deleted_ports)
    
    # 更新配置文件中的快照
    config['port_snapshot'] = new_snapshot
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(top_code)
        print(f"\nInfo: Top module updated and written to {output_file}")
    else:
        print(f"\nInfo: Top module '{top_name}' updated (no output file specified)")
        print(top_code)
    
    # 保存更新后的配置文件
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"Info: Config updated: {config_path}")
    
    # 生成 CSV review 文件
    config_dir = os.path.dirname(config_path)
    csv_path = os.path.join(config_dir, f"{top_name}.integrate.csv")
    
    csv_rows = [['Module', 'Port', 'Direction', 'Width', 'Signal', 'Shared_With', 'Status']]
    for module in all_modules:
        mod_name = module.name
        mod_changes_map = port_changes.get(mod_name, {})
        old_ports_dict = {p['name']: (p['direction'], p['width']) for p in old_snapshot.get(mod_name, [])}
        
        for direction, width, port_name in module.ports:
            map_key = f"{mod_name}.{port_name}"
            signal = port_map.get(map_key, f"{mod_name.lower()}_{port_name}")
            
            shared_with = ''
            shared_signals = config.get('shared_signals', {})
            if signal in shared_signals:
                others = [mp.split('.', 1)[0] for mp in shared_signals[signal] if mp != map_key]
                if others:
                    shared_with = ', '.join(sorted(set(others)))
            
            status = mod_changes_map.get(port_name, '')
            csv_rows.append([
                mod_name, port_name, direction, width if width else '',
                signal, shared_with, status
            ])
        
        current_port_names = {n for _, _, n in module.ports}
        for port_name, (direction, width) in old_ports_dict.items():
            if port_name not in current_port_names:
                csv_rows.append([
                    mod_name, port_name, direction, width if width else '',
                    '', '', 'DEL'
                ])
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)
    print(f"Info: CSV review updated: {csv_path}")


def generate_top(modules, top_name="soc_top", port_map=None, port_changes=None, deleted_ports=None):
    """
    port_changes: {module_name: {port_name: 'NEW'|'MOD', ...}, ...}
    deleted_ports: {module_name: [(port_name, direction, width), ...], ...}
    """
    """生成顶层SoC模块，智能连接同名端口
    
    规则：
    1. 同名端口且所有方向都是 input/inout → 顶层 input 端口（外部输入）
    2. 同名端口 output + input 混合 → 内部 wire（output 驱动 input）
    3. 同名端口 output + output → 不共享，各自独立
    4. 独有端口 → 作为顶层端口（加模块前缀避免冲突）
    5. 端口映射: 通过 port_map 把不同名端口映射到同一信号名
    
    port_map 格式: {"module_name.port_name": "target_signal_name", ...}
    """
    if port_map is None:
        port_map = {}
    
    # 1. 收集所有端口，应用映射，按 target_name 分组
    mapped_ports = {}  # target_name -> [(module, direction, width, original_name), ...]
    for module in modules:
        for direction, width, name in module.ports:
            map_key = f"{module.name}.{name}"
            target_name = port_map.get(map_key, name)
            
            if target_name not in mapped_ports:
                mapped_ports[target_name] = []
            mapped_ports[target_name].append((module, direction, width, name))
    
    # 2. 判断共享端口（基于 target_name）
    #   input+input   → external_shared: 顶层 input 端口（外部输入）
    #   output+input  → internal_signals: 内部 wire（output 驱动 input）
    #   output+output → module_unique:   各自独立，不共享
    external_shared = {}   # target_name -> (direction, width)  顶层端口
    internal_signals = {}  # target_name -> width               内部 wire
    module_unique = {}     # module.name -> {original_port_name: (direction, width, target_name)}
    
    for target_name, entries in mapped_ports.items():
        directions = [e[1] for e in entries]
        unique_dirs = set(directions)
        
        # input + input (>=2 modules, all input/inout) → 顶层 input 端口
        if len(entries) >= 2 and len(unique_dirs) == 1 and list(unique_dirs)[0] in ('input', 'inout'):
            width = entries[0][2]
            first_module = entries[0][0]
            resolved_width = resolve_param_width(width, first_module.params)
            external_shared[target_name] = (list(unique_dirs)[0], resolved_width)
        
        # output + input (mixed) → 内部 wire（output 驱动 input）
        elif len(entries) >= 2 and unique_dirs == {'input', 'output'} and directions.count('output') == 1:
            output_entry = next(e for e in entries if e[1] == 'output')
            width = output_entry[2]
            resolved_width = resolve_param_width(width, output_entry[0].params)
            internal_signals[target_name] = resolved_width
        
        # 其他情况（包括 output+output）→ 不共享
        else:
            for module, direction, width, original_name in entries:
                if module.name not in module_unique:
                    module_unique[module.name] = {}
                resolved_width = resolve_param_width(width, module.params)
                module_unique[module.name][original_name] = (direction, resolved_width, target_name)
    
    # 3. 计算对齐参数
    # 收集所有顶层端口用于计算对齐宽度
    all_top_ports = []
    for name, (direction, width) in external_shared.items():
        all_top_ports.append((direction, width, name))
    for module in modules:
        if module.name in module_unique:
            for name, (direction, width, target_name) in module_unique[module.name].items():
                map_key = f"{module.name}.{name}"
                if map_key in port_map:
                    sig_name = target_name
                else:
                    sig_name = f"{module.name.lower()}_{target_name}"
                all_top_ports.append((direction, width, sig_name))
    
    max_dir_len = max(len(d) for d, _, _ in all_top_ports) if all_top_ports else 0
    max_width_len = max(len(w) if w else 0 for _, w, _ in all_top_ports) if all_top_ports else 0
    
    # 计算每个模块实例化的端口名最大长度（用于 .port(signal) 对齐）
    inst_port_max = {}
    for module in modules:
        inst_port_max[module.name] = max(len(name) for _, _, name in module.ports) if module.ports else 0
    
    # 辅助函数：格式化端口声明行
    def fmt_port(direction, width, name):
        w = width if width else ""
        return f"    {direction:<{max_dir_len}} {w:<{max_width_len}} {name}"
    
    # 辅助函数：格式化 wire 声明行
    def fmt_wire(width, name, mod_max_width):
        w = width if width else ""
        return f"    wire {w:<{mod_max_width}} {name};"
    
    # 辅助函数：格式化实例化端口连接
    def fmt_inst(port, signal, max_len):
        return f"        .{port:<{max_len}} ({signal})"
    
    # 4. 生成顶层模块
    lines = []
    lines.append("// ============================================================================")
    lines.append(f"// {top_name}")
    lines.append("// ============================================================================")
    lines.append("// AUTO-GENERATED by soc_integrate.py")
    lines.append(f"// Timestamp: {datetime.now().isoformat()}")
    lines.append("//")
    lines.append("// DO NOT EDIT THIS FILE DIRECTLY.")
    lines.append("// Modify sub-modules and re-run: soc_integrate.py integrate ...")
    lines.append("// For manual connections, use assign statements in a separate file.")
    lines.append("// ============================================================================")
    lines.append("")
    lines.append(f"module {top_name} (")
    
    # 顶层端口列表
    top_port_list = []
    internal_wires = []
    
    # 外部共享端口（input+input）→ 顶层 input 端口
    for name, (direction, width) in external_shared.items():
        top_port_list.append(fmt_port(direction, width, name))
    
    # 内部共享信号（output+input）→ 内部 wire 声明
    for name, width in internal_signals.items():
        w_str = f" {width}" if width else ""
        internal_wires.append(f"    wire{w_str} {name};")
    
    # 独有端口 → 顶层端口
    for module in modules:
        if module.name in module_unique:
            for original_name, (direction, width, target_name) in module_unique[module.name].items():
                map_key = f"{module.name}.{original_name}"
                if map_key in port_map:
                    sig_name = target_name
                else:
                    sig_name = f"{module.name.lower()}_{target_name}"
                top_port_list.append(fmt_port(direction, width, sig_name))
    
    lines.append(",\n".join(top_port_list))
    lines.append(");")
    lines.append("")
    
    # 内部wire声明
    if internal_wires:
        lines.append("    // Internal shared signals")
        for wire_decl in internal_wires:
            lines.append(wire_decl)
        lines.append("")
    
    # 5. 实例化
    for module in modules:
        instance_name = f"u_{module.name.lower()}"
        max_p = inst_port_max[module.name]
        
        # 参数
        if module.params:
            lines.append(f"    {module.name} #(")
            for i, (pname, pdefault, pwidth) in enumerate(module.params):
                comma = "," if i < len(module.params) - 1 else ""
                lines.append(f"        .{pname:<{max_p}} ({pdefault}){comma}")
            lines.append(f"    ) {instance_name} (")
        else:
            lines.append(f"    {module.name} {instance_name} (")
        
        # 先计算所有端口连接行的最大长度（用于注释对齐）
        port_lines = []
        for i, (direction, width, name) in enumerate(module.ports):
            comma = "," if i < len(module.ports) - 1 else ""
            w = resolve_param_width(width, module.params) if width else ""
            map_key = f"{module.name}.{name}"
            target_name = port_map.get(map_key, name)
            
            if target_name in external_shared or target_name in internal_signals:
                signal = target_name
            else:
                if map_key in port_map:
                    signal = target_name
                else:
                    signal = f"{module.name.lower()}_{target_name}"
            
            if w:
                line = f"        .{name:<{max_p}} ({signal}{w}){comma}"
            else:
                line = f"        .{name:<{max_p}} ({signal}){comma}"
            port_lines.append((line, direction, width, name))
        
        max_line_len = max(len(l) for l, _, _, _ in port_lines) if port_lines else 0
        
        # 输出端口连接，注释放在行尾
        mod_changes = (port_changes or {}).get(module.name, {})
        for line, direction, width, name in port_lines:
            change_mark = mod_changes.get(name, '')
            if change_mark:
                comment = f"// {direction} [{change_mark}]"
            else:
                comment = f"// {direction}"
            lines.append(f"{line:<{max_line_len}}  {comment}")
        
        # 添加删除端口的注释
        mod_deleted = (deleted_ports or {}).get(module.name, [])
        for port_name, direction, width in mod_deleted:
            w_str = f" {width}" if width else ""
            lines.append(f"        // [DEL] {port_name} ({direction}{w_str})")
        
        lines.append("    );")
        lines.append("")
    
    lines.append("endmodule")
    return "\n".join(lines)


def extract_map_from_top(top_file):
    """从顶层 .v 文件中提取实例化连接关系，生成 port map
    
    返回: {
        "mappings": {"module.port": "signal", ...},
        "shared_signals": {"signal": ["module.port", ...], ...},
        "instances": [{"module": "...", "instance": "...", "ports": {...}}, ...]
    }
    """
    with open(top_file, 'r') as f:
        content = f.read()
    
    # 去掉单行注释和多行注释
    content = re.sub(r'//.*', '', content)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # 先去掉参数块 #( ... )，处理一层嵌套括号
    content = re.sub(r'#\s*\((?:[^()]|\([^)]*\))*\)', '', content)
    
    # 匹配实例化块: module_name instance_name ( ... );
    # 排除 module 声明 (module top_name (...))
    inst_pattern = r'(\w+)\s+(\w+)\s*\((.*?)\)\s*;'
    
    mappings = {}
    shared_signals = {}  # signal -> [module.port, ...]
    instances = []
    
    for match in re.finditer(inst_pattern, content, re.DOTALL):
        module_name = match.group(1)
        instance_name = match.group(2)
        port_block = match.group(3)
        
        # 跳过 module 声明
        if module_name == 'module' or module_name == 'endmodule':
            continue
        
        # 提取 .port(signal) 连接
        port_pattern = r'\.(\w+)\s*\(\s*([^)]+?)\s*\)'
        inst_ports = {}
        
        for port_match in re.finditer(port_pattern, port_block):
            port_name = port_match.group(1)
            signal_name = port_match.group(2).strip()
            
            # 去掉位宽标注，如 signal[3:0]、signal[31:0] → signal
            signal_name = re.sub(r'\[.*?\]$', '', signal_name)
            
            inst_ports[port_name] = signal_name
            
            map_key = f"{module_name}.{port_name}"
            mappings[map_key] = signal_name
            
            # 记录共享信号
            if signal_name not in shared_signals:
                shared_signals[signal_name] = []
            shared_signals[signal_name].append(map_key)
        
        instances.append({
            'module': module_name,
            'instance': instance_name,
            'ports': inst_ports
        })
    
    # 只保留真正有共享的信号（连接数 >= 2）
    shared_signals = {k: v for k, v in shared_signals.items() if len(v) >= 2}
    
    return {
        'mappings': mappings,
        'shared_signals': shared_signals,
        'instances': instances
    }


def main():
    parser = argparse.ArgumentParser(description='SoC Integrate - 顶层集成工具')
    subparsers = parser.add_subparsers(dest='command')
    
    # extract 命令
    extract_parser = subparsers.add_parser('extract', help='提取模块端口')
    extract_parser.add_argument('file', help='Verilog文件路径')
    extract_parser.add_argument('-m', '--module', help='指定模块名（文件中有多个模块时）')
    extract_parser.add_argument('-o', '--output', help='输出文件路径')
    
    # instantiate 命令
    inst_parser = subparsers.add_parser('instantiate', help='生成实例化代码')
    inst_parser.add_argument('file', help='Verilog文件路径')
    inst_parser.add_argument('-m', '--module', help='指定模块名')
    inst_parser.add_argument('-n', '--name', help='实例名')
    inst_parser.add_argument('-o', '--output', help='输出文件路径')
    
    # wrap 命令
    wrap_parser = subparsers.add_parser('wrap', help='生成wrapper模块')
    wrap_parser.add_argument('file', help='Verilog文件路径')
    wrap_parser.add_argument('-m', '--module', help='指定模块名')
    wrap_parser.add_argument('-n', '--name', help='wrapper模块名')
    wrap_parser.add_argument('-o', '--output', help='输出文件路径')
    
    # csv 命令
    csv_parser = subparsers.add_parser('csv', help='导出端口到CSV')
    csv_parser.add_argument('file', help='Verilog文件路径')
    csv_parser.add_argument('-m', '--module', help='指定模块名')
    csv_parser.add_argument('-o', '--output', default='ports.csv', help='CSV文件路径')
    
    # snapshot 命令 - 保存端口快照
    snap_parser = subparsers.add_parser('snapshot', help='保存端口快照')
    snap_parser.add_argument('file', help='Verilog文件路径')
    snap_parser.add_argument('-m', '--module', help='指定模块名')
    snap_parser.add_argument('-o', '--output', help='输出文件路径前缀（默认: <module>_ports）')
    snap_parser.add_argument('-f', '--format', choices=['json', 'csv', 'both'], default='both',
                            help='输出格式: json/csv/both (默认: both)')
    snap_parser.add_argument('-v', '--version', default='1.0.0', help='版本号 (默认: 1.0.0)')
    snap_parser.add_argument('-c', '--changelog', default='', help='变更说明')
    
    # diff 命令 - 比较端口变化
    diff_parser = subparsers.add_parser('diff', help='对比当前端口与快照的差异')
    diff_parser.add_argument('file', help='当前Verilog文件路径')
    diff_parser.add_argument('snapshot', help='快照JSON文件路径')
    diff_parser.add_argument('-m', '--module', help='指定模块名')
    
    # check 命令 - 检查端口完整性
    check_parser = subparsers.add_parser('check', help='检查端口是否符合规范')
    check_parser.add_argument('file', help='Verilog文件路径')
    check_parser.add_argument('spec', help='规范JSON文件路径（快照）')
    check_parser.add_argument('-m', '--module', help='指定模块名')
    
    # extract-map 命令 - 从顶层 .v 提取连接关系
    emap_parser = subparsers.add_parser('extract-map', help='从顶层 .v 提取实例化连接关系，生成 port map')
    emap_parser.add_argument('file', help='顶层Verilog文件路径')
    emap_parser.add_argument('-o', '--output', help='输出JSON文件路径（默认: stdout）')
    emap_parser.add_argument('--verify', nargs='+', help='原始模块Verilog文件列表，用于验证模块和端口存在性')
    
    # integrate 命令
    int_parser = subparsers.add_parser('integrate', help='集成多个模块到顶层')
    int_parser.add_argument('files', nargs='+', help='Verilog文件路径列表')
    int_parser.add_argument('-n', '--name', default='soc_top', help='顶层模块名')
    int_parser.add_argument('-o', '--output', help='输出文件路径')
    int_parser.add_argument('--map', help='端口映射JSON文件路径 (格式: {"mappings": {"module.port": "signal"}})')
    int_parser.add_argument('--no-config', action='store_true',
                           help='不生成 integrate 配置文件')
    
    # update 命令 - 一键刷新端口重新生成顶层
    update_parser = subparsers.add_parser('update', help='根据配置文件重新生成顶层')
    update_parser.add_argument('config', help='integrate 配置文件路径 (.integrate.json)')
    update_parser.add_argument('-o', '--output', help='覆盖输出文件路径')
    update_parser.add_argument('--map', help='覆盖端口映射文件路径')
    update_parser.add_argument('-n', '--name', help='覆盖顶层模块名')
    
    # remove 命令 - 从集成配置中删除模块并自动刷新顶层
    remove_parser = subparsers.add_parser('remove', help='从集成配置中删除指定模块并自动刷新顶层')
    remove_parser.add_argument('config', help='integrate 配置文件路径 (.integrate.json)')
    remove_parser.add_argument('module_name', help='要删除的模块名')
    

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    if args.command == 'extract':
        modules = extract_modules(args.file)
        
        if args.module:
            module = next((m for m in modules if m.name == args.module), None)
            if not module:
                print(f"Error: Module '{args.module}' not found in {args.file}")
                sys.exit(1)
            modules = [module]
        
        for module in modules:
            print(f"\nModule: {module.name}")
            print(f"Parameters ({len(module.params)}):")
            for pname, pdefault, pwidth in module.params:
                width_str = f" {pwidth}" if pwidth else ""
                print(f"  parameter{width_str} {pname} = {pdefault}")
            
            print(f"\nPorts ({len(module.ports)}):")
            print(f"{'Direction':<10} {'Width':<12} {'Name'}")
            print("-" * 40)
            for direction, width, name in module.ports:
                width_str = width if width else "1"
                print(f"{direction:<10} {width_str:<12} {name}")
            
            print(f"\n--- Port Declarations ---")
            print(generate_port_declarations(module))
    
    elif args.command == 'instantiate':
        modules = extract_modules(args.file)
        
        if args.module:
            module = next((m for m in modules if m.name == args.module), None)
        else:
            module = modules[0] if modules else None
        
        if not module:
            print("Error: No module found")
            sys.exit(1)
        
        instance_code = generate_instance(module, args.name)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(instance_code)
            print(f"Info: Instance code written to {args.output}")
        else:
            print(instance_code)
    
    elif args.command == 'wrap':
        modules = extract_modules(args.file)
        
        if args.module:
            module = next((m for m in modules if m.name == args.module), None)
        else:
            module = modules[0] if modules else None
        
        if not module:
            print("Error: No module found")
            sys.exit(1)
        
        wrapper_code = generate_wrapper(module, args.name)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(wrapper_code)
            print(f"Info: Wrapper written to {args.output}")
        else:
            print(wrapper_code)
    
    elif args.command == 'csv':
        modules = extract_modules(args.file)
        
        if args.module:
            module = next((m for m in modules if m.name == args.module), None)
        else:
            module = modules[0] if modules else None
        
        if not module:
            print("Error: No module found")
            sys.exit(1)
        
        export_csv(module, args.output)
    
    elif args.command == 'extract-map':
        result = extract_map_from_top(args.file)
        
        # 可选：验证模块和端口是否存在于原始文件中
        verified_modules = {}
        if args.verify:
            for vfile in args.verify:
                modules = extract_modules(vfile)
                for m in modules:
                    verified_modules[m.name] = {n for _, _, n in m.ports}
        
        # 过滤验证结果
        valid_mappings = {}
        warnings = []
        for map_key, signal in result['mappings'].items():
            if verified_modules:
                module_name, port_name = map_key.split('.', 1)
                if module_name not in verified_modules:
                    warnings.append(f"Warning: Module '{module_name}' not found in verification files")
                    valid_mappings[map_key] = signal
                elif port_name not in verified_modules[module_name]:
                    warnings.append(f"Warning: Port '{map_key}' not found in module definition")
                else:
                    valid_mappings[map_key] = signal
            else:
                valid_mappings[map_key] = signal
        
        result['mappings'] = valid_mappings
        
        if warnings:
            for w in warnings:
                print(w)
            print()
        
        # 输出报告
        print(f"Extracted {len(result['instances'])} instances, {len(valid_mappings)} mappings")
        print(f"Shared signals: {len(result['shared_signals'])}")
        for sig, conns in result['shared_signals'].items():
            print(f"  {sig}: {', '.join(conns)}")
        print()
        
        # 生成JSON输出
        output_data = {
            'source_file': args.file,
            'mappings': valid_mappings
        }
        if result['shared_signals']:
            output_data['shared_signals'] = result['shared_signals']
        
        json_str = json.dumps(output_data, indent=2, ensure_ascii=False)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(json_str)
            print(f"Info: Port map written to {args.output}")
        else:
            print(json_str)
    
    elif args.command == 'integrate':
        all_modules = []
        module_configs = []
        for filepath in args.files:
            filepath_abs = os.path.abspath(filepath)
            modules = extract_modules(filepath)
            if modules:
                # 默认只取每个文件的第一个模块（主模块）
                # 如果文件名和模块名匹配，取匹配的模块
                basename = os.path.splitext(os.path.basename(filepath))[0]
                matched = [m for m in modules if m.name == basename]
                if matched:
                    selected = matched[0]
                else:
                    selected = modules[0]
                all_modules.append(selected)
                module_configs.append({
                    'file': filepath_abs,
                    'module_name': selected.name
                })
        
        # 加载端口映射文件
        port_map = {}
        port_map_file = None
        if args.map:
            port_map_file = os.path.abspath(args.map)
            with open(args.map, 'r') as f:
                map_data = json.load(f)
            port_map = map_data.get('mappings', {})
            print(f"Info: Loaded port mappings from {args.map}")
            for key, val in port_map.items():
                print(f"  {key} → {val}")
            print()
        
        top_code = generate_top(all_modules, args.name, port_map)
        
        output_file = args.output
        if output_file:
            output_file = os.path.abspath(output_file)
            with open(output_file, 'w') as f:
                f.write(top_code)
            print(f"Info: Top module written to {output_file}")
        else:
            print(top_code)
        
        # 保存配置文件（默认启用，--no-config 禁用）
        if not args.no_config:
            # 计算共享信号信息（用于配置和CSV）
            # 反向计算：signal -> [module.port, ...]
            shared_signals = {}
            for map_key, signal in port_map.items():
                if signal not in shared_signals:
                    shared_signals[signal] = []
                shared_signals[signal].append(map_key)
            shared_signals = {k: v for k, v in shared_signals.items() if len(v) >= 2}
            
            # 保存端口快照（用于下次 update 时检测增删改）
            port_snapshot = {}
            for module in all_modules:
                port_snapshot[module.name] = [
                    {'direction': d, 'width': w, 'name': n}
                    for d, w, n in module.ports
                ]
            
            config_data = {
                'top_module': args.name,
                'output_file': output_file,
                'modules': module_configs,
                'mappings': port_map,
                'shared_signals': shared_signals,
                'port_snapshot': port_snapshot,
                'generated_at': datetime.now().isoformat()
            }
            # 配置文件放在输出文件同目录，或当前目录
            if output_file:
                config_dir = os.path.dirname(output_file)
                config_path = os.path.join(config_dir, f"{args.name}.integrate.json")
                csv_path = os.path.join(config_dir, f"{args.name}.integrate.csv")
            else:
                config_path = f"{args.name}.integrate.json"
                csv_path = f"{args.name}.integrate.csv"
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"Info: Integrate config saved to {config_path}")
            
            # 生成 CSV review 文件
            csv_rows = [['Module', 'Port', 'Direction', 'Width', 'Signal', 'Shared_With', 'Status']]
            for module in all_modules:
                for direction, width, port_name in module.ports:
                    map_key = f"{module.name}.{port_name}"
                    signal = port_map.get(map_key, f"{module.name.lower()}_{port_name}")
                    
                    # 查找共享该信号的其他模块
                    shared_with = ''
                    if signal in shared_signals:
                        others = [mp.split('.', 1)[0] for mp in shared_signals[signal] if mp != map_key]
                        if others:
                            shared_with = ', '.join(sorted(set(others)))
                    
                    csv_rows.append([
                        module.name,
                        port_name,
                        direction,
                        width if width else '',
                        signal,
                        shared_with,
                        ''
                    ])
            
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(csv_rows)
            print(f"Info: Integrate review CSV saved to {csv_path}")
            print(f"      Use 'python3 scripts/soc_integrate.py update {config_path}' to refresh")
            

    
    elif args.command == 'remove':
        # 读取配置文件
        with open(args.config, 'r') as f:
            config = json.load(f)
        
        module_name = args.module_name
        modules = config.get('modules', [])
        removed_mods = [m for m in modules if m['module_name'] == module_name]
        
        if not removed_mods:
            print(f"Error: Module '{module_name}' not found in config")
            sys.exit(1)
        
        # 从 modules 列表中删除
        config['modules'] = [m for m in modules if m['module_name'] != module_name]
        
        # 清理 port_snapshot 中该模块的快照
        if 'port_snapshot' in config and module_name in config['port_snapshot']:
            del config['port_snapshot'][module_name]
        
        # 清理 mappings 中该模块相关的条目
        prefix = module_name + '.'
        if 'mappings' in config:
            config['mappings'] = {k: v for k, v in config['mappings'].items() if not k.startswith(prefix)}
        
        # 清理 shared_signals 中该模块相关的条目
        if 'shared_signals' in config:
            new_shared = {}
            for sig, conns in config['shared_signals'].items():
                filtered = [mp for mp in conns if not mp.startswith(prefix)]
                if filtered:
                    new_shared[sig] = filtered
            config['shared_signals'] = new_shared
        
        print(f"Info: Removed module '{module_name}' from config")
        print(f"Info: Auto-updating top module ...")
        print()
        
        # 保存中间配置
        with open(args.config, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        # 自动执行 update
        do_update(config, args.config)
    
    elif args.command == 'update':
        # 读取配置文件
        with open(args.config, 'r') as f:
            config = json.load(f)
        
        do_update(config, args.config, args.name, args.output, args.map)
        

    
    elif args.command == 'snapshot':
        modules = extract_modules(args.file)
        
        if args.module:
            module = next((m for m in modules if m.name == args.module), None)
        else:
            module = modules[0] if modules else None
        
        if not module:
            print("Error: No module found")
            sys.exit(1)
        
        # 构建快照数据
        snapshot = {
            "module_name": module.name,
            "file": os.path.basename(args.file),
            "timestamp": datetime.now().isoformat(),
            "version": args.version,
            "changelog": args.changelog,
            "params": [
                {"name": p[0], "default": p[1], "width": p[2]}
                for p in module.params
            ],
            "ports": [
                {"direction": d, "width": w, "name": n}
                for d, w, n in module.ports
            ]
        }
        
        # Default snapshot path = alongside the Verilog source (RTL dir),
        # not the current working directory. Keeps port history co-located
        # with the file it describes.
        if args.output:
            output_prefix = args.output
        else:
            src_dir = os.path.dirname(os.path.abspath(args.file))
            output_prefix = os.path.join(src_dir, f"{module.name}_ports")
        
        # 输出 JSON
        if args.format in ('json', 'both'):
            json_file = output_prefix + ".json"
            with open(json_file, 'w') as f:
                json.dump(snapshot, f, indent=2)
            print(f"Info: JSON snapshot saved to {json_file}")
        
        # 输出 CSV
        if args.format in ('csv', 'both'):
            csv_file = output_prefix + ".csv"
            with open(csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Module', module.name])
                writer.writerow(['Version', args.version])
                writer.writerow(['File', os.path.basename(args.file)])
                writer.writerow(['Timestamp', snapshot['timestamp']])
                if args.changelog:
                    writer.writerow(['Changelog', args.changelog])
                writer.writerow([])
                
                if module.params:
                    writer.writerow(['=== Parameters ==='])
                    writer.writerow(['Name', 'Default', 'Width'])
                    for p in module.params:
                        writer.writerow([p[0], p[1], p[2]])
                    writer.writerow([])
                
                writer.writerow(['=== Ports ==='])
                writer.writerow(['Direction', 'Width', 'Name'])
                for d, w, n in module.ports:
                    writer.writerow([d, w if w else '', n])
            print(f"Info: CSV snapshot saved to {csv_file}")
    
    elif args.command == 'diff':
        modules = extract_modules(args.file)
        
        if args.module:
            module = next((m for m in modules if m.name == args.module), None)
        else:
            module = modules[0] if modules else None
        
        if not module:
            print("Error: No module found")
            sys.exit(1)
        
        # 加载快照
        with open(args.snapshot, 'r') as f:
            snapshot = json.load(f)
        
        # 构建当前端口字典
        current_ports = {n: (d, w) for d, w, n in module.ports}
        snapshot_ports = {p['name']: (p['direction'], p['width']) for p in snapshot['ports']}
        
        current_names = set(current_ports.keys())
        snapshot_names = set(snapshot_ports.keys())
        
        added = current_names - snapshot_names
        removed = snapshot_names - current_names
        common = current_names & snapshot_names
        
        modified = []
        for name in common:
            curr_dir, curr_w = current_ports[name]
            snap_dir, snap_w = snapshot_ports[name]
            if curr_dir != snap_dir or curr_w != snap_w:
                modified.append({
                    'name': name,
                    'old': (snap_dir, snap_w),
                    'new': (curr_dir, curr_w)
                })
        
        # 输出差异报告
        print(f"\n{'='*60}")
        print(f"Port Diff: {module.name}")
        print(f"{'='*60}")
        print(f"Snapshot: {snapshot['file']} ({snapshot['timestamp']})")
        print(f"Current:  {os.path.basename(args.file)}")
        print()
        
        if added:
            print(f"[+] Added ({len(added)}):")
            for name in sorted(added):
                d, w = current_ports[name]
                w_str = f" {w}" if w else ""
                print(f"    {d:<6}{w_str:<12} {name}")
            print()
        
        if removed:
            print(f"[-] Removed ({len(removed)}):")
            for name in sorted(removed):
                d, w = snapshot_ports[name]
                w_str = f" {w}" if w else ""
                print(f"    {d:<6}{w_str:<12} {name}")
            print()
        
        if modified:
            print(f"[~] Modified ({len(modified)}):")
            for item in modified:
                name = item['name']
                old_d, old_w = item['old']
                new_d, new_w = item['new']
                old_w_str = old_w if old_w else ""
                new_w_str = new_w if new_w else ""
                
                changes = []
                if old_d != new_d:
                    changes.append(f"direction: {old_d}→{new_d}")
                if old_w != new_w:
                    changes.append(f"width: {old_w_str}→{new_w_str}")
                
                print(f"    {old_d:<6} {old_w_str:<10} {name}")
                print(f"    ↓")
                print(f"    {new_d:<6} {new_w_str:<10} {name}  ({', '.join(changes)})")
                print()
        
        if not added and not removed and not modified:
            print("✓ No changes detected. Ports are identical.")
        else:
            total = len(added) + len(removed) + len(modified)
            print(f"Summary: {total} changes ({len(added)} added, {len(removed)} removed, {len(modified)} modified)")
    
    elif args.command == 'check':
        modules = extract_modules(args.file)
        
        if args.module:
            module = next((m for m in modules if m.name == args.module), None)
        else:
            module = modules[0] if modules else None
        
        if not module:
            print("Error: No module found")
            sys.exit(1)
        
        # 加载规范
        with open(args.spec, 'r') as f:
            spec = json.load(f)
        
        current_ports = {n: (d, w) for d, w, n in module.ports}
        spec_ports = {p['name']: (p['direction'], p['width']) for p in spec['ports']}
        
        current_names = set(current_ports.keys())
        spec_names = set(spec_ports.keys())
        
        missing = spec_names - current_names      # 规范有但当前没有
        extra = current_names - spec_names         # 当前有但规范没有
        common = current_names & spec_names
        
        mismatched = []
        for name in common:
            curr_dir, curr_w = current_ports[name]
            spec_dir, spec_w = spec_ports[name]
            if curr_dir != spec_dir or curr_w != spec_w:
                mismatched.append({
                    'name': name,
                    'expected': (spec_dir, spec_w),
                    'actual': (curr_dir, curr_w)
                })
        
        print(f"\n{'='*60}")
        print(f"Port Check: {module.name}")
        print(f"{'='*60}")
        print(f"Spec:     {args.spec}")
        print(f"Current:  {os.path.basename(args.file)}")
        print()
        
        errors = 0
        
        if missing:
            print(f"[!] Missing ({len(missing)}) - required by spec but not found:")
            for name in sorted(missing):
                d, w = spec_ports[name]
                w_str = f" {w}" if w else ""
                print(f"    {d:<6}{w_str:<12} {name}")
                errors += 1
            print()
        
        if extra:
            print(f"[!] Extra ({len(extra)}) - not in spec:")
            for name in sorted(extra):
                d, w = current_ports[name]
                w_str = f" {w}" if w else ""
                print(f"    {d:<6}{w_str:<12} {name}")
                errors += 1
            print()
        
        if mismatched:
            print(f"[!] Mismatched ({len(mismatched)}) - does not match spec:")
            for item in mismatched:
                name = item['name']
                exp_d, exp_w = item['expected']
                act_d, act_w = item['actual']
                exp_w_str = exp_w if exp_w else ""
                act_w_str = act_w if act_w else ""
                print(f"    Expected: {exp_d:<6} {exp_w_str:<10} {name}")
                print(f"    Actual:   {act_d:<6} {act_w_str:<10} {name}")
                errors += 1
            print()
        
        if errors == 0:
            print(f"✓ All {len(spec_ports)} ports match the spec.")
        else:
            print(f"✗ Found {errors} issues. Please fix before integration.")
            sys.exit(1)


if __name__ == '__main__':
    main()

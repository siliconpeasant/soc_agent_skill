---
name: cr-tree-diag-gen
description: "Clock/Reset Tree Diagram Generator. Convert Excel timing tables into Draw.io (.drawio) and Excalidraw (.excalidraw) diagrams with hierarchical layout, MUX support, root-source edge coloring, and frequency annotations."
---

# CR Tree Diagram Generator

时钟/复位树链路图生成器。将 Excel 表格转换为 Draw.io 或 Excalidraw 格式的拓扑图。

## Capabilities

- **时钟树可视化**：从 Excel 时钟表生成完整链路图（Source → MUX → DIV → OCC → ICG → Output）
- **复位树可视化**：从 Excel 复位表生成复位链路图（含 SOFT/REG/AND 节点）
- **双格式输出**：同时生成 `.drawio`（diagrams.net）和 `.excalidraw`（excalidraw.com）
- **智能布局**：按表格原始顺序从上到下排列，中间节点按链路长度动态分布
- **MUX 支持**：SRC0/SRC1 双输入 MUX 节点，动态计算 level
- **边着色**：不同源头时钟的边使用不同颜色（红/蓝/绿等）
- **频率标注**：NOTE 列内容（如 1000MHz）自动显示在节点框内
- **正交布线**：Draw.io 支持跳线 arc，Excalidraw 支持先垂直后水平布线

## When to Use

当用户需要：

- 画时钟树 / 画复位树 / 画时钟链路图
- 把 Excel 时钟表转成拓扑图
- 生成 drawio / excalidraw 时钟图
- 可视化 CRG / 时钟分配 / 复位分配
- 检查时钟来源和分频关系

## Input Format

### 时钟树表格（Clock Tree）

| 列名        | 说明                          | 示例            |
| --------- | --------------------------- | ------------- |
| NAME      | 信号名                         | `core_clk`    |
| ATTR      | 属性：input/internal/output/na | `output`      |
| SRC0      | 父时钟0（主源）                    | `pll_mux_clk` |
| SRC1      | 父时钟1（MUX 第二输入）              | `pad_src_clk` |
| MUX_DFLT  | MUX 默认值                     | `0`           |
| DIV       | 分频器                         | `2`           |
| DIV_WIDTH | 分频器位宽                       | `4`           |
| DIV_DFLT  | 分频器默认值                      | `1`           |
| OCC       | OCC 控制                      | `Y`           |
| ICG       | ICG 控制                      | `Y`           |
| ICG_DFLT  | ICG 默认值                     | `1`           |
| NOTE      | 注释/频率                       | `1000MHz`     |

### 复位树表格（Reset Tree）

| 列名        | 说明                       | 示例           |
| --------- | ------------------------ | ------------ |
| NAME      | 信号名                      | `core_rst_n` |
| ATTR      | 属性：input/internal/output | `output`     |
| SRC0      | 父复位0                     | `por_rst_n`  |
| SRC1~SRC3 | 额外输入（AND 门）              | `soft_rst_n` |
| SOFT_DFLT | 软件默认值                    | `1`          |

## How to Use

### 命令行

```bash
# 同时生成 drawio + excalidraw
python3 cr_tree_diag_gen/main.py input.xlsx

# 指定输出路径（只生成一种格式）
python3 cr_tree_diag_gen/main.py input.xlsx output.drawio
python3 cr_tree_diag_gen/main.py input.xlsx output.excalidraw
```

### MCP Tool

通过 `cr_tree_diag_gen` 工具直接生成：

```json
{
  "input_path": "/path/to/clock_table.xlsx",
  "output_dir": "/path/to/output"
}
```

返回生成文件列表。

## Output

| 文件                  | 打开方式                         |
| ------------------- | ---------------------------- |
| `*_tree.drawio`     | https://app.diagrams.net     |
| `*_tree.excalidraw` | https://excalidraw.com（直接拖入） |

## Node Types & Colors

| 类型              | 颜色           | 说明             |
| --------------- | ------------ | -------------- |
| source_input    | 绿 `#27ae60`  | 外部输入时钟         |
| source_internal | 灰 `#7f8c8d`  | 内部生成时钟         |
| na              | 橙 `#f39c12`  | 中间节点（非 output） |
| output          | 浅蓝 `#aed6f1` | 最终输出时钟         |
| div             | 白 `#ffffff`  | 分频器            |
| occ             | 紫 `#f5eef8`  | 时钟门控控制器        |
| icg             | 绿 `#d5f5e3`  | 时钟门控           |
| mux             | 紫 `#e8daef`  | 多路选择器          |
| rst_and         | 黄 `#fff3bf`  | 复位与门           |
| reg             | 蓝 `#d6eaf8`  | 寄存器节点          |
| soft            | 橙 `#fdebd0`  | 软件控制节点         |

## Design Principles

- **零侵入**：纯 Python 脚本，不依赖 draw.io / excalidraw 安装
- **表格驱动**：Excel 是唯一输入，修改表格即修改图
- **自动推导**：不指定输出路径时自动推导文件名，同时生成两种格式
- **向后兼容**：NOTE 列可选，无 NOTE 时不影响生成

## Dependencies

```bash
pip install pandas openpyxl
```

## MCP Server

### 快速配置

在 `.kimi/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "cr-tree-diag-gen": {
      "command": "python3",
      "args": ["/path/to/cr_tree_diag_gen/mcp_server.py"]
    }
  }
}
```

### 暴露工具

| Tool                          | 功能                         |
| ----------------------------- | -------------------------- |
| `cr_tree_diag_gen`            | xlsx → drawio + excalidraw |
| `cr_tree_diag_gen_drawio`     | xlsx → drawio only         |
| `cr_tree_diag_gen_excalidraw` | xlsx → excalidraw only     |

## Notes

1. **自动检测表格类型**：有 `SOFT_DFLT` 列 → 复位树，否则 → 时钟树
2. **中间节点**：DIV/OCC/ICG 根据表格列自动创建，不需要单独定义
3. **孤立源过滤**：无出边的 test_mode / clk_gen_rst_n 等输入节点自动隐藏
4. **Excalidraw 限制**：不支持 arc 跳线，梯形 MUX 渲染为矩形

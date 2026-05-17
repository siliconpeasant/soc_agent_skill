---
name: crg-req-to-design
description: "Convert CRG requirement table (subsystem, IP, clock/reset signals, notes) into clock tree design table and reset tree design table, with PLL count recommendation and architecture report."
---

# CRG Requirement → Design Table Generator

将 **CRG 需求表**（子系统、IP、时钟/复位信号名、备注/频率）自动转换为 **时钟树设计表** 和 **复位树设计表**，并推荐 PLL 数量与时钟树架构。

生成的设计表可直接作为 `cr_tree_diag_gen` 的输入，形成完整 pipeline：

```
需求表 → crg_req_to_design → 设计表 → cr_tree_diag_gen → drawio / excalidraw
```

## Capabilities

- **需求表解析**：支持 Excel（.xlsx/.xls）和 CSV，列名模糊匹配（中英双语）
- **频率自动提取**：从备注中识别 `200MHz`、`3Mhz`、`20/25MHz` 等格式，自动归一化为 MHz
- **信号自动分类**：根据后缀（`_clk`、`_rst_n` 等）自动区分时钟与复位
- **Pad 输入识别**：根据信号名（`pad`、`xtal`、`osc`）或备注（"外部"/"输入"）识别外部时钟源
- **PLL 数量推荐**：基于整数分频关系，优先用 pad 时钟推导内部时钟；无法推导时按频率聚类推荐 PLL
- **时钟树架构生成**：自动推断 `SRC0`、`DIV`、`DIV_WIDTH`、`DIV_DFLT`，生成符合 `cr_tree_diag_gen` 格式的时钟树设计表
- **复位树默认生成**：以 `PORESETn` 为根，自动为所有子系统复位信号生成输出节点
- **架构报告输出**：文本报告汇总推荐 PLL、分频链路和复位树结构

## Input Format (需求表)

| 列名 | 别名 | 说明 |
|------|------|------|
| 子系统 | subsystem, 模块, block | 所属子系统（支持 Excel 合并单元格） |
| IP | ip, 模块名 | 所属 IP（可选） |
| 时钟复位需求 | signal, 信号名, name, 时钟/复位 | 信号名（如 `core_clk`） |
| 备注 | note, 频率, freq, remark, 注释 | 频率、说明等（如 `200MHz`） |

## Output Files

运行后会在输出目录生成 3 个文件：

| 文件 | 说明 |
|------|------|
| `clock_design.xlsx` | 时钟树设计表（兼容 `cr_tree_diag_gen`） |
| `reset_design.xlsx` | 复位树设计表（兼容 `cr_tree_diag_gen`） |
| `crg_report.txt` | PLL 推荐与时钟树架构报告 |

## How to Use

### 命令行

```bash
# 基本用法
python scripts/main.py <req_table.xlsx> [output_dir]

# 示例
python scripts/main.py examples/input/req_table.xlsx output/
```

### MCP Server

在 `.kimi/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "crg-req-to-design": {
      "command": "python3",
      "args": ["/path/to/crg_req_to_design/mcp_server.py"]
    }
  }
}
```

**暴露工具**：

| Tool | 功能 |
|------|------|
| `crg_req_to_design` | 需求表 → 时钟设计表 + 复位设计表 + 架构报告 |

**调用参数**：

```json
{
  "input_path": "/path/to/req_table.xlsx",
  "output_dir": "/path/to/output"
}
```

返回生成文件列表、PLL 推荐和分频链路摘要。

### 与 cr_tree_diag_gen 联动

```bash
# 1. 生成设计表
python crg_req_to_design/scripts/main.py req_table.xlsx output/

# 2. 生成时钟树拓扑图
python cr_tree_diag_gen/scripts/main.py output/clock_design.xlsx clock_tree.drawio

# 3. 生成复位树拓扑图
python cr_tree_diag_gen/scripts/main.py output/reset_design.xlsx reset_tree.drawio
```

## Design Principles

- **表格驱动**：Excel 需求表是唯一输入，修改需求即修改架构
- **最小 PLL 原则**：优先利用已有 pad 时钟或 PLL 的整数分频关系，减少 PLL 数量
- **可编辑中间产物**：生成的设计表保留为 Excel，用户可手动微调 SRC、DIV、MUX 等细节后再送入画图工具
- **零侵入**：纯 Python，不依赖 EDA 工具

## Dependencies

```bash
pip install pandas openpyxl
```

## Algorithm Details

### PLL 推荐逻辑

1. 对每个内部时钟，遍历所有 pad 时钟，寻找整数分频比 `div ∈ [1, 64]`
2. 若 `|pad_freq / div - tgt_freq| / tgt_freq ≤ 5%`，认为该时钟可由 pad 分频得到
3. 若无法由 pad 得到，尝试由已创建的 PLL 分频得到（高频 PLL 优先）
4. 若仍无法得到，为该频率创建新 PLL，同频时钟共享此 PLL

### 复位树逻辑

- `PORESETn`（或第一个复位信号）作为 `input` 根节点
- `nTRST`、`nSRST` 等调试复位作为独立 `input`
- 其余子系统复位作为 `output`，`SRC0 = PORESETn`

## Notes

1. **多频率 pad**：备注如 "20/25MHz" 会提取第一个频率作为主频，完整字符串保留在 NOTE 列供手动编辑
2. **无频率时钟**：若某时钟未标注频率，不会为其创建 PLL，SRC0 留空，需用户手动指定
3. **ICG/OCC**：需求表通常不包含门控/扫描信息，设计表中 ICG/OCC 列留空，用户可后续补充
4. **同 pad 名区分**：不同子系统的 `pad_clk` 会被视为独立输入节点；如需合并，请在需求表中统一命名或于设计表中手动合并

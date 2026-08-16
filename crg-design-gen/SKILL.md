---
name: crg-design-gen
description: >
  CRG frontend design flow: requirement table → clock/reset design tables + PLL
  report, and/or reviewed design tables → Draw.io/Excalidraw topology diagrams.
  Merges former crg-req-to-design and cr-tree-diag-gen. Does not generate CRG RTL
  (use crg-gen after tables are approved).
---

# CRG Design Generator (`crg-design-gen`)

Merged from `crg-req-to-design` + `cr-tree-diag-gen`.

Turn a CRG **requirement table** into **clock/reset design tables**, a PLL/architecture report, and a crg-gen-ready workbook. After review, turn design tables into Draw.io / Excalidraw topology diagrams.

This skill does **not** generate synthesizable CRG RTL.

## Pipeline

```text
需求表 (req)
  → crg_req_to_design          # stage 1：设计表 + PLL 报告 + crg workbook
  → [人工评审 design xlsx]
  → cr_tree_diag_gen           # stage 2：拓扑图
  → [可选] crg-gen             # 另一 skill：RTL/SDC
```

One-shot draft (**unreviewed**, exploration only):

```text
crg_req_pipeline(req.xlsx, with_diagram=true)
  → design 表 + 报告 + 可选图（summary 标 UNREVIEWED）
```

## MCP tools

Tool names stay stable so existing agent prompts keep working.

| Tool | 作用 |
|------|------|
| `crg_req_to_design` | 需求表 → `clock_design.xlsx` / `reset_design.xlsx` / `crg_report.txt` / `<design>_crg.xlsx` |
| `cr_tree_diag_gen` | 设计表 → drawio + excalidraw |
| `cr_tree_diag_gen_drawio` | 仅 Draw.io |
| `cr_tree_diag_gen_excalidraw` | 仅 Excalidraw |
| `crg_req_pipeline` | stage1 + 可选 stage2（默认 `with_diagram=false`） |

Register the bundled stdio server:

```json
{
  "mcpServers": {
    "crg-design-gen": {
      "command": "python3",
      "args": ["/path/to/crg-design-gen/mcp_server.py"]
    }
  }
}
```

## Stage 1 — 需求 → 设计表 + crg-gen workbook

```bash
python3 crg-design-gen/scripts/design_main.py \
  path/to/req_table.xlsx [output_dir]
```

- Input: `.xlsx` / `.xls` / `.csv`
- Default output directory: `output/` (CLI) or `<input-stem>_design/` (MCP)

| 文件 | 用途 |
|------|------|
| **`<design>_crg.xlsx`** | **主交付**：与 `crg-gen` 模板同构，可直接改后跑 `crg-gen` |
| `clock_design.xlsx` | 树图用精简时钟表（从 clk_gen 抽出） |
| `reset_design.xlsx` | 树图用精简复位表 |
| `crg_report.txt` | PLL/架构说明 |
| `README_CRG_HANDOFF.txt` | 交接说明 |

### Requirement table columns

| 列名 | 别名 | 说明 |
|------|------|------|
| 子系统 | subsystem, 模块, block | 所属子系统（支持 Excel 合并单元格） |
| IP | ip, 模块名 | 所属 IP（可选） |
| 时钟复位需求 | signal, 信号名, name, 时钟/复位 | 信号名（如 `core_clk`） |
| 备注 | note, 频率, freq, remark | 频率、说明等（如 `200MHz`） |

### `<design>_crg.xlsx` sheets

| Sheet | 内容 |
|-------|------|
| `top_info` | design name / protocol / addr / design_hier…（可改） |
| `clk_gen` | **全列**（含 Clock source / Groups / ICG_* / DIV_*…） |
| `rst_gen` | **全列**（含 REG_NAME / SYNC / INOUT…） |
| `user_defined_reg` | 空表头，填寄存器 |
| `user_defined_intp` | 空表头 |
| `user_code` | 空表头 |
| `user_sdc` | 空表头 |

Auto-filled: pad clocks get `Clock source = source get_ports {name}` and default `Clock Groups0`; `test_mode` / `clk_gen_rst_n` boilerplate rows are added.

Domain reset outputs default to **`SYNC=N`** (CRG does source combining only; sync release is not in CRG). Do not flip this to `SYNC=Y` just to simplify integration.

## Stage 2 — 设计表 → 图

```bash
# both formats
python3 crg-design-gen/scripts/tree_main.py path/to/clock_design.xlsx

# one format
python3 crg-design-gen/scripts/tree_main.py path/to/clock_design.xlsx clock_tree.drawio
python3 crg-design-gen/scripts/tree_main.py path/to/reset_design.xlsx reset_tree.excalidraw
```

- Use slim `clock_design.xlsx` / `reset_design.xlsx` (same source as the PRIMARY workbook)
- Default output: `<input-stem>_diagram/` (MCP) or `examples/output/` (CLI when no path is given)

Table type is auto-detected: a `SOFT_DFLT` column means reset tree, otherwise clock tree.

### Clock tree columns

| 列名 | 说明 | 示例 |
|------|------|------|
| NAME | 信号名 | `core_clk` |
| ATTR | input / internal / output / na | `output` |
| SRC0 | 父时钟 0 | `pll_mux_clk` |
| SRC1 | MUX 第二输入 | `pad_src_clk` |
| MUX_DFLT | MUX 默认值 | `0` |
| DIV | 分频比 | `2` |
| DIV_WIDTH | 分频器位宽 | `4` |
| DIV_DFLT | 分频器默认值 | `1` |
| OCC | OCC 控制 | `Y` |
| ICG | ICG 控制 | `Y` |
| ICG_DFLT | ICG 默认值 | `1` |
| NOTE | 注释/频率 | `1000MHz` |

### Reset tree columns

| 列名 | 说明 | 示例 |
|------|------|------|
| NAME | 信号名 | `core_rst_n` |
| ATTR | input / internal / output | `output` |
| SRC0 | 父复位 0 | `por_rst_n` |
| SRC1~SRC3 | 额外输入（AND 门） | `soft_rst_n` |
| SOFT_DFLT | 软件默认值 | `1` |

| 文件 | 打开方式 |
|------|----------|
| `*_tree.drawio` | https://app.diagrams.net |
| `*_tree.excalidraw` | https://excalidraw.com（直接拖入） |

## Local CLI

| 入口 | 说明 |
|------|------|
| `scripts/design_main.py` | 需求 → crg-gen workbook + slim 设计表 |
| `scripts/tree_main.py` | slim 设计表 → 图 |
| `scripts/crg_config_writer.py` | 写 workbook 的库 |

```bash
# stage 1
python3 crg-design-gen/scripts/design_main.py \
  crg-design-gen/examples/input/req_table_complex.xlsx output/

# stage 2
python3 crg-design-gen/scripts/tree_main.py output/clock_design.xlsx
python3 crg-design-gen/scripts/tree_main.py output/reset_design.xlsx
```

## Boundary with `crg-gen`

| Skill | 产物 |
|-------|------|
| **crg-design-gen** | 可编辑的 crg Excel + 报告 + 可选图 |
| **crg-gen** | 基于该 Excel 生成 CRG RTL + SDC（本仓库未收录） |

Edit `<design>_crg.xlsx` in place, then run `crg-gen` on that file. Do not recopy tables.

## Capabilities

- Parse Excel/CSV requirement tables with bilingual fuzzy column names
- Extract frequencies such as `200MHz`, `3Mhz`, `20/25MHz`
- Classify clocks vs resets from suffixes (`_clk`, `_rst_n`, …)
- Recognize pad/xtal/osc sources from names or notes
- Recommend a minimal PLL set via integer-divide matching, then emit clock/reset design tables
- Write a crg-gen-compatible multi-sheet workbook
- Render clock/reset trees to Draw.io and Excalidraw with hierarchical layout, MUX nodes, and frequency notes

## Dependencies

```bash
pip install pandas openpyxl
```

For the MCP server:

```bash
pip install mcp
```

## Algorithm notes

### PLL recommendation

1. For each internal clock, try integer divides `div ∈ [1, 64]` from every pad clock
2. Accept a pad source when `|pad_freq / div - tgt_freq| / tgt_freq ≤ 5%`
3. Otherwise try an already-created PLL (higher frequency first)
4. Otherwise create a new PLL; same-frequency clocks share it

### Reset tree

- `PORESETn` (or the first reset) is the `input` root
- Debug resets such as `nTRST` / `nSRST` stay independent `input`s
- Remaining subsystem resets are `output` with `SRC0 = PORESETn`

## Node types (diagrams)

| 类型 | 颜色 | 说明 |
|------|------|------|
| source_input | 绿 `#27ae60` | 外部输入时钟 |
| source_internal | 灰 `#7f8c8d` | 内部生成时钟 |
| na | 橙 `#f39c12` | 中间节点（非 output） |
| output | 浅蓝 `#aed6f1` | 最终输出时钟 |
| div | 白 `#ffffff` | 分频器 |
| occ | 紫 `#f5eef8` | 时钟门控控制器 |
| icg | 绿 `#d5f5e3` | 时钟门控 |
| mux | 紫 `#e8daef` | 多路选择器 |
| rst_and | 黄 `#fff3bf` | 复位与门 |
| reg | 蓝 `#d6eaf8` | 寄存器节点 |
| soft | 橙 `#fdebd0` | 软件控制节点 |

## Notes

1. Multi-frequency pads such as `20/25MHz` keep the first frequency as primary; the full string stays in NOTE
2. Clocks without a frequency do not get a PLL; SRC0 is left blank
3. ICG/OCC are usually absent from requirement tables and left blank for later edit
4. Same pad names in different subsystems stay independent unless renamed/merged
5. Isolated `test_mode` / `clk_gen_rst_n` inputs with no outgoing edges are hidden in diagrams
6. Excalidraw has no arc jumpers; trapezoid MUXes render as rectangles
7. Review design tables before treating diagrams as approved or handing the workbook to `crg-gen`

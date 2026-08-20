# crg-design-gen

CRG **frontend** design skill: requirement table → clock/reset design tables,
PLL report, and optional Draw.io / Excalidraw trees.

It does **not** generate synthesizable CRG RTL. After you review the workbook,
use `crg-gen` (separate skill, not in this repo) for RTL/SDC.

Merged from former `crg-req-to-design` and `cr-tree-diag-gen`.

## Install

```bash
npx skills add siliconpeasant/soc_agent_skill --skill crg-design-gen -g
```

```bash
pip install pandas openpyxl
pip install mcp   # MCP server only
```

## Pipeline

```text
req table
  → crg_req_to_design     # design xlsx + PLL report + crg-gen workbook
  → [human review]
  → cr_tree_diag_gen      # Draw.io / Excalidraw
  → [optional] crg-gen    # RTL/SDC, another skill
```

Domain reset outputs default to `SYNC=N`: CRG combines sources only; sync
release belongs at integration, not in generated CRG.

## MCP

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

| Tool | Purpose |
| --- | --- |
| `crg_req_to_design` | Req table → design workbooks + report |
| `cr_tree_diag_gen` | Design tables → Draw.io + Excalidraw |
| `cr_tree_diag_gen_drawio` | Draw.io only |
| `cr_tree_diag_gen_excalidraw` | Excalidraw only |
| `crg_req_pipeline` | Stage 1 plus optional unreviewed diagrams |

`crg_req_pipeline` is a draft. Do not treat its diagrams as approved.

## CLI

```bash
python3 scripts/design_main.py examples/input/req_table_complex.xlsx output/
python3 scripts/tree_main.py output/clock_design.xlsx
python3 scripts/tree_main.py output/reset_design.xlsx
```

Examples live under `examples/input/` and `examples/output/`.

## Boundary

| Skill | Output |
| --- | --- |
| **crg-design-gen** | Editable CRG Excel, report, optional trees |
| **crg-gen** | CRG RTL + SDC from that Excel |
| **soc-integrate** | Chip top; per-domain `rst_synchronizer` on gated clocks |

Edit `<design>_crg.xlsx` in place, then run `crg-gen` on that file.

See [SKILL.md](SKILL.md) for column maps, PLL matching, and node styles.

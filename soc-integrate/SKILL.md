---
name: soc-integrate
description: >
  Extract RTL ports, generate instances/wrappers/top modules, and track
  interface changes through snapshots and integration configs. Use for
  generated SoC top-level integration and port-change maintenance.
  soc_update only after listed submodule ports change; do not regenerate a
  top just to close a delivery stage.
---

# SoC Integrate (`soc-integrate`)

Generate and maintain a **chip/subsystem top** from Verilog submodule files.
Do not hand-edit generated instances. Keep connection intent in a port-map JSON.

Prefer the bundled MCP server. CLI is available for local use and tests.

## MCP tools

| Tool | Purpose |
|---|---|
| `soc_extract` | Parse ANSI module ports |
| `soc_instantiate` | Emit `.port(signal)` instance |
| `soc_wrap` | Pass-through wrapper |
| `soc_csv` | Port CSV |
| `soc_snapshot` / `soc_diff` | Port snapshot and delta |
| `soc_integrate` | Stitch modules into a generated top + `.integrate.json` |
| `soc_extract_map` | Recover mappings from an existing top |
| `soc_update` | Refresh that top after **listed submodule ports change** |
| `soc_remove` | Drop a module from the config and refresh |

Register stdio:

```json
{
  "mcpServers": {
    "soc-integrate": {
      "command": "python3",
      "args": ["/path/to/soc-integrate/mcp_server.py"]
    }
  }
}
```

Requires `pip install mcp`.

## When to `soc_update`

`soc_update` refreshes an **already generated** top after a module named in
`.integrate.json` adds, removes, renames, or resizes a port.

Do **not** run it when submodule ports are unchanged. Snapshot/CSV evidence is
enough. Regenerating just to close a stage rewrites the top with no intent change.

The generated-top owner runs `soc_update`. Leaf IP workspaces do not update the
chip top.

If a close skips `soc_update`, say **why**: `ports unchanged`, or name the
deferred port delta. Bare `soc_update not run` is ambiguous.

## Connection rules

Same-name ports, direction-compatible:

- all `input`/`inout` → top input
- one `output` plus `input`s → internal wire
- `output`+`output` or mixed mismatch → unique ports (prefixed unless mapped)

Automatic sharing is only for simple cases. Review multi-driver, width,
clock-domain, reset-domain, and protocol connections explicitly. Put those
intents in `--map` / port-map JSON:

```json
{ "mappings": { "uart.clk_i": "clk_sys_i", "gpio.clk_i": "clk_sys_i" } }
```

Parser accepts ANSI Verilog/SystemVerilog ports and fails closed on non-ANSI
lists and package-typed ports (`pkg::word_t`). Wrap those modules first.

Internal nets that are not ports (gated clocks, synced resets, hierarchical
IRQ taps) cannot be stitched by this skill. Export them from a glue module,
then integrate the glue.

## Reset ownership

CRG owns clock trees and **combinational** reset-source combine.
Integration owns one `rst_synchronizer` (`STAGES=2`) per domain on the
**gated** domain clock (`rst_<dom>_sync_ni`). Do not put sync-release flops
inside generated CRG or each leaf IP.

## CLI

```bash
python3 soc-integrate/scripts/soc_integrate.py extract path/to/mod.v
python3 soc-integrate/scripts/soc_integrate.py integrate a.v b.v \
  -n chip_top -o chip_top.v --map port_map.json
python3 soc-integrate/scripts/soc_integrate.py update chip_top.integrate.json
```

```bash
python3 soc-integrate/tests/test_parser.py -v
```

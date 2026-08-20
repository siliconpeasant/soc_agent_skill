# soc-integrate

Generate and maintain a Verilog **chip/subsystem top** from submodule files.
This is a standalone Agent Skill plus stdio MCP server. It is not part of
`soc-build`.

Do not hand-edit generated instances. Keep connection intent in a port-map JSON.

## Install

```bash
npx skills add siliconpeasant/soc_agent_skill --skill soc-integrate -g
```

Python 3.8+ and:

```bash
pip install mcp
```

## MCP

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

| Tool | Purpose |
| --- | --- |
| `soc_extract` | Parse ANSI module ports |
| `soc_instantiate` | Emit an instance |
| `soc_wrap` | Pass-through wrapper |
| `soc_csv` | Port CSV |
| `soc_snapshot` / `soc_diff` | Port snapshot and delta |
| `soc_integrate` | Stitch modules into a generated top + `.integrate.json` |
| `soc_extract_map` | Recover mappings from an existing top |
| `soc_update` | Refresh that top after listed submodule **ports** change |
| `soc_remove` | Drop a module from the config and refresh |

## When to `soc_update`

Run `soc_update` only when a module listed in `.integrate.json` added, removed,
renamed, or resized a port.

Do **not** run it to close a delivery stage if ports are unchanged. Snapshot or
CSV evidence is enough. Regenerating the top with no port delta only rewrites
the file.

The generated-top owner runs `soc_update`. Leaf IP workspaces do not update the
chip top. Skip notes must say `ports unchanged` or name the deferred port.

## CLI

```bash
python3 scripts/soc_integrate.py extract examples/uart.v

python3 scripts/soc_integrate.py integrate \
  examples/uart.v examples/gpio.v \
  -n demo_top -o /tmp/demo_top.v \
  --map examples/port_map.json

python3 scripts/soc_integrate.py update /tmp/demo_top.integrate.json
```

Shared `clk_i` / `rst_ni` become top inputs; unique pads stay on the top.

## Limits

- ANSI Verilog/SystemVerilog ports only. Non-ANSI lists and `pkg::t` ports fail
  closed — wrap them first.
- Same-name auto-connect is only for simple direction-compatible wires.
- Internal nets that are not ports (gated clocks, synced resets, hierarchical
  IRQs) need a glue module; this skill cannot tap them.
- CRG owns combinational reset combine. Integration owns one
  `rst_synchronizer` (2 stages) per domain on the **gated** clock.

## Test

```bash
python3 tests/test_parser.py -v
```

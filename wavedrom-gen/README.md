# wavedrom-gen

Turn natural-language timing into official WaveJSON/JSON5 and render it with
the pinned `wavedrom@3.6.2` engine. Local only — no API key.

## Install

```bash
npx skills add siliconpeasant/soc_agent_skill --skill wavedrom-gen -g
```

Then in the installed `wavedrom-gen` directory:

```bash
npm ci --omit=dev
```

Node.js 20+ is required.

## Register MCP

```bash
node scripts/register-mcp.mjs --agent codex
node scripts/register-mcp.mjs --agent claude-code --scope user
node scripts/register-mcp.mjs --agent generic
```

`--dry-run` prints commands without writing config. Existing registrations are
kept unless `--force` is set.

| Tool | Purpose |
| --- | --- |
| `wavedrom_help` | Official WaveJSON guidance by topic |
| `wavedrom_validate` | JSON5 parse, official render probe, optional strict lint |
| `wavedrom_render` | SVG / PNG / self-contained offline HTML |

## CLI

```bash
node scripts/validate-wavejson.mjs --input examples/qspi-quad-io-read.json5
node scripts/render-wavedrom.mjs --input examples/qspi-quad-io-read.json5 \
  --svg /tmp/qspi.svg
```

## Examples

| Example | Source | Preview |
| --- | --- | --- |
| AXI4 read/write bursts | [JSON5](examples/axi4-read-write.json5) | [SVG](examples/axi4-read-write.svg) |
| QSPI 1-4-4 Quad I/O | [JSON5](examples/qspi-quad-io-read.json5) | [SVG](examples/qspi-quad-io-read.svg) |
| Async FIFO CDC | [JSON5](examples/async-fifo-cdc.json5) | [SVG](examples/async-fifo-cdc.svg) |
| A_PGM datasheet dimensions | [JSON5](examples/a-pgm-mode-datasheet.json5) | [SVG](examples/a-pgm-mode-datasheet.svg) |

The skill pins `wavedrom@3.6.2` and all six shipped skins. PNG is derived from
the canonical SVG with `@resvg/resvg-js`.

## Test

From the repository root:

```bash
cd wavedrom-gen && npm ci && cd ..
node .github/scripts/wavedrom-gen-self-test.mjs
```

See [SKILL.md](SKILL.md) for the authoring workflow and quality gates.

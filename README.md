# SoC Agent Skills

Open Agent Skills and MCP tools for SoC design workflows.

## Skills

| Skill | Purpose | MCP |
| --- | --- | --- |
| `crg-req-to-design` | Convert CRG requirements into clock/reset design tables | Included |
| `cr-tree-diag-gen` | Generate clock/reset tree diagrams | Included |
| `wavedrom-gen` | Generate validated WaveDrom and Datasheet-grade timing diagrams from natural language | Included, stdio |

## Install `wavedrom-gen` for any supported Agent

The skill follows the open [Agent Skills specification](https://agentskills.io/specification). Install it with the cross-agent `skills` CLI:

```bash
npx skills add siliconpeasant/soc_agent_skill --skill wavedrom-gen -g
```

The installer supports Codex, Claude Code, Cursor, OpenCode, Cline, GitHub Copilot and many other Agent Skills clients. Remove `-g` for a project-local installation, or select clients explicitly with `-a`, for example:

```bash
npx skills add siliconpeasant/soc_agent_skill --skill wavedrom-gen -g -a codex -a claude-code
```

## Register the bundled MCP server

`wavedrom-gen` is a standalone Skill, not a Codex or Claude plugin. Its MCP server, pinned dependencies, and registration helper all live inside the Skill directory.

After installation, enter the installed `wavedrom-gen` directory and install its runtime dependencies:

```bash
npm ci --omit=dev
```

Register it with Codex:

```bash
node scripts/register-mcp.mjs --agent codex
```

Register it with Claude Code at user scope:

```bash
node scripts/register-mcp.mjs --agent claude-code --scope user
```

For any other stdio MCP-compatible Agent, print a portable JSON configuration containing the resolved absolute server path:

```bash
node scripts/register-mcp.mjs --agent generic
```

Use `--dry-run` to inspect native registration commands without changing Agent configuration. Existing `wavedrom-gen` registrations are never replaced unless `--force` is explicitly supplied.

The server exposes:

- `wavedrom_help`: versioned official WaveJSON guidance by topic;
- `wavedrom_validate`: JSON5 parsing, official-engine render probing, and optional strict quality lint;
- `wavedrom_render`: preserves JSON5, renders official `signal`, `assign`, and `reg` diagrams through `wavedrom@3.6.2`, and optionally adds Datasheet-grade setup/hold/width/period dimensions consistently to SVG, PNG, and self-contained offline HTML.

All rendering is local. No API key or remote rendering service is required.

## WaveDrom examples

Each example includes editable JSON5 and a GitHub-viewable SVG. Generated HTML previews, PNG QA files, and temporary scripts are intentionally excluded.

| Example | Source | Preview |
| --- | --- | --- |
| AXI4 read/write bursts | [JSON5](wavedrom-gen/examples/axi4-read-write.json5) | [SVG](wavedrom-gen/examples/axi4-read-write.svg) |
| QSPI 1-4-4 Quad I/O continuous read | [JSON5](wavedrom-gen/examples/qspi-quad-io-read.json5) | [SVG](wavedrom-gen/examples/qspi-quad-io-read.svg) |
| Asynchronous FIFO CDC with Gray pointers | [JSON5](wavedrom-gen/examples/async-fifo-cdc.json5) | [SVG](wavedrom-gen/examples/async-fifo-cdc.svg) |
| A_PGM Datasheet-style timing dimensions | [JSON5](wavedrom-gen/examples/a-pgm-mode-datasheet.json5) | [SVG](wavedrom-gen/examples/a-pgm-mode-datasheet.svg) |

<details>
<summary>Preview: QSPI 1-4-4 Quad I/O continuous read</summary>

![QSPI 1-4-4 Quad I/O continuous read](wavedrom-gen/examples/qspi-quad-io-read.svg)

</details>

<details>
<summary>Preview: A_PGM Datasheet annotations</summary>

![A_PGM Datasheet annotations](wavedrom-gen/examples/a-pgm-mode-datasheet.svg)

</details>

### Official compatibility baseline

The skill pins the official main package `wavedrom@3.6.2` rather than the older standalone `wavedrom-cli` package. The same official `renderAny` engine and all six shipped skins power validation, SVG output, MCP rendering, and offline HTML preview. PNG is derived locally from the canonical SVG with pinned `@resvg/resvg-js`; `npm audit` reports no known vulnerabilities in the locked dependency tree.

## Develop and test

```bash
cd wavedrom-gen
npm ci
cd ..
node .github/scripts/wavedrom-gen-self-test.mjs
```

The test performs a real MCP handshake, discovers the tools, validates WaveJSON, renders every supported output, and checks invalid-input and overwrite protection.

# SoC Agent Skills

Open Agent Skills and MCP tools for SoC design workflows.

## Skills

| Skill | Purpose | MCP |
| --- | --- | --- |
| `crg-req-to-design` | Convert CRG requirements into clock/reset design tables | Included |
| `cr-tree-diag-gen` | Generate clock/reset tree diagrams | Included |
| `wavedrom-gen` | Generate validated WaveDrom timing diagrams from natural language | Included, stdio |

## Install `wavedrom-gen` for any supported Agent

The skill follows the open [Agent Skills specification](https://agentskills.io/specification). Install it with the cross-agent `skills` CLI:

```bash
npx skills add siliconpeasant/soc_agent_skill --skill wavedrom-gen -g
```

The installer supports Codex, Claude Code, Cursor, OpenCode, Cline, GitHub Copilot and many other Agent Skills clients. Remove `-g` for a project-local installation, or select clients explicitly with `-a`, for example:

```bash
npx skills add siliconpeasant/soc_agent_skill --skill wavedrom-gen -g -a codex -a claude-code
```

For direct script use after a Skill-only installation, install its pinned runtime dependencies once from the installed `wavedrom-gen` directory:

```bash
npm install --omit=dev
```

## Connect the MCP server

Any stdio MCP client can launch the server directly from GitHub. This command downloads the package and its pinned dependencies through npm, so it does not depend on the Skill installation path:

```json
{
  "mcpServers": {
    "wavedrom-gen": {
      "command": "npx",
      "args": [
        "-y",
        "--package=github:siliconpeasant/soc_agent_skill",
        "wavedrom-gen-mcp",
        "--stdio"
      ]
    }
  }
}
```

The repository-level [`.mcp.json`](.mcp.json) contains the same portable configuration. Clients that support project MCP discovery can use it after cloning the repository.

The server exposes:

- `wavedrom_help`: compact WaveJSON guidance;
- `wavedrom_validate`: deterministic JSON5 and timing-structure validation;
- `wavedrom_render`: preserves JSON5 and renders SVG, PNG, and self-contained offline HTML through the official `wavedrom-cli`.

All rendering is local. No API key or remote rendering service is required.

### Dependency security note

The package pins the current official `wavedrom-cli` release (`3.2.0`). Its legacy PNG conversion dependency tree currently produces five moderate npm audit findings and no high or critical findings. They are confined to Jimp/file-type/phin transitive packages; `wavedrom-gen` passes only its own locally generated SVG to that conversion path and performs no authenticated HTTP requests. The lockfile keeps this state reviewable until the upstream CLI updates the converter stack.

## Develop and test

```bash
npm ci
npm test
```

The test performs a real MCP handshake, discovers the tools, validates WaveJSON, renders every supported output, and checks invalid-input and overwrite protection.

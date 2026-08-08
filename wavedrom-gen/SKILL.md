---
name: wavedrom-gen
description: Generate, revise, validate, and render WaveDrom digital timing diagrams from natural-language descriptions, protocol requirements, timing tables, or existing WaveJSON/JSON5, using bundled MCP tools when available and local scripts otherwise. Use for clocks, digital waveforms, buses, SPI, I2C, UART, AXI valid/ready, request/acknowledge, GPIO, PWM, reset sequences, and signal timing documentation when the deliverables should include wavedrom-cli input plus SVG, PNG, or an offline interactive HTML preview. Do not use for analog waveforms, software sequence diagrams, generic flowcharts, or continuous-time signal analysis.
---

# WaveDrom Gen

Turn the user's description into editable WaveJSON/JSON5, prove that the source renders with the official `wavedrom-cli`, and deliver the source and diagram together.

## Required outputs

- Preserve the editable source as `<descriptive-name>.json5`.
- Render `<descriptive-name>.svg` by default.
- Also render PNG when the user asks for it or when PNG is needed for visual inspection.
- Also render a self-contained HTML preview when the user wants browser editing, interactive review, or a portable offline viewer.
- State all assumptions that materially affect timing semantics.
- Return absolute paths for every artifact.

## Workflow

1. **Classify the request.** Determine whether the user wants a conceptual illustration or an implementation-accurate diagram. Treat an existing specification, RTL, trace, or timing table as authoritative.
2. **Build a timing contract.** Before writing WaveJSON, identify:
   - time unit or clock domain;
   - active clock edge and initial state;
   - signal names, kinds, active levels, and grouping;
   - ordered events, latency, transfer conditions, and final state;
   - unresolved facts and explicit assumptions.
3. **Resolve ambiguity proportionally.** Ask a focused question only when a missing fact would produce a semantically different diagram and the user requested implementation accuracy. For a conceptual draft, use conventional defaults and disclose them.
4. **Read the relevant guidance.** Read [references/wavejson-signal.md](references/wavejson-signal.md) for WaveJSON encoding. For standard protocols, also read [references/protocol-questions.md](references/protocol-questions.md). For synchronous or implementation-accurate work, read [references/semantic-review.md](references/semantic-review.md).
5. **Write the CLI input.** Create valid JSON5 with a top-level `signal` array. Prefer explicit, readable formatting. Use one time slot consistently unless `period` or `phase` is genuinely required.
6. **Validate deterministically.** Prefer the `wavedrom_validate` MCP tool when it is available. Pass the complete WaveJSON/JSON5 source and enable strict mode when warnings must fail the gate. If MCP is unavailable, resolve script paths relative to this `SKILL.md`, then run:

   ```text
   node <skill-dir>/scripts/validate-wavejson.mjs --input <source.json5>
   ```

   Fix every error before rendering. Review warnings instead of ignoring them mechanically.
7. **Render with the official CLI.** Prefer the `wavedrom_render` MCP tool when it is available. Pass an absolute output directory, a safe base name, the requested formats, and `overwrite: true` only when replacement is intentional. The tool preserves the JSON5 source and always creates the SVG baseline. Read [references/mcp-tools.md](references/mcp-tools.md) for its contract. If MCP is unavailable, run:

   ```text
   node <skill-dir>/scripts/render-wavedrom.mjs --input <source.json5> --svg <output.svg>
   ```

   Add `--png <output.png>` when PNG is required. Add `--html <output.html>` for an offline browser preview with JSON5 editing, live re-rendering, validation, zoom, copy, and SVG/PNG download controls. The generated HTML must remain self-contained and must not depend on a CDN. Do not silently install Node.js, `wavedrom-cli`, Inkscape, or any other dependency; report the missing dependency and request permission when installation is necessary. When permission is granted, install the pinned local dependencies with `npm ci --omit=dev` from the skill directory.
8. **Inspect the result.** Confirm that labels are legible, transitions align with the intended slots or edges, groups are useful, arrows land on the correct nodes, and nothing is clipped. Use the PNG for visual QA when the available viewer cannot inspect SVG directly.
9. **Perform semantic review.** Reconcile the rendered diagram with the timing contract and the user's source material. A successful CLI exit proves renderability, not protocol correctness.

## Natural-language policy

- Preserve explicit user facts; do not replace them with protocol defaults.
- Distinguish unknown (`x`), high impedance (`z`), held state (`.`), and labeled bus data (`=` or `2`-`9`).
- Never invent a signal solely to make the picture look complete.
- For an ambiguous named protocol, either ask for the parameters listed in the protocol reference or make a small conceptual example with conspicuous assumptions.
- Keep one diagram focused. Split unrelated phases or clock domains into separate diagrams when that improves correctness or readability.

## Quality gates

- JSON5 parsing succeeds.
- Every data box has a label; extra labels are reviewed.
- Every edge endpoint names an existing node.
- Synchronous transitions and transfer cycles match the timing contract.
- `wavedrom-cli` exits successfully.
- The SVG exists, is non-empty, and contains an SVG root.
- When HTML is requested, it exists, is self-contained, opens without network access, and can re-render the embedded source.
- The final response links the source and rendered artifacts and lists assumptions.

## Dependency baseline

The MCP server and local scripts require Node.js 18 or newer. This skill pins the official CLI in `package.json`; install it locally from the skill directory with:

```text
npm ci --omit=dev
```

The renderer also detects an existing global `wavedrom-cli` installation. Use the current CLI flags `-i/--input`, `-s/--svg`, and `-p/--png`. PDF is not a native CLI output; only add an Inkscape conversion step when the user explicitly requests PDF.

When the MCP tools are not registered and the user wants them, read [references/mcp-registration.md](references/mcp-registration.md). Prefer the bundled registration script over editing an Agent's configuration directly.

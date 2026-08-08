---
name: wavedrom-gen
description: Generate, revise, validate, and render official WaveDrom diagrams from natural-language timing descriptions, protocol requirements, timing tables, or existing WaveJSON/JSON5. Use for clocks, digital waveforms, buses, SPI, QSPI, I2C, UART, AXI valid/ready, request/acknowledge, GPIO, PWM, reset sequences, sub-cycle timing, WaveDrom arrows, titles, skins, register or logic diagrams, and optional Datasheet-grade setup/hold/width/period dimensions. Deliver editable JSON5 plus SVG, PNG, or self-contained offline HTML through bundled MCP tools when available and local scripts otherwise. Do not use for analog waveforms, software sequence diagrams, generic flowcharts, or continuous-time signal analysis.
---

# WaveDrom Gen

Turn natural language into editable WaveJSON/JSON5 and render it with the pinned official `wavedrom` main-package engine. Treat `wavedrom@3.6.2` `renderAny` behavior as the syntax authority; use custom lint only as a quality layer.

## Required outputs

- Preserve editable source as `<descriptive-name>.json5`.
- Render `<descriptive-name>.svg` by default.
- Add PNG for raster delivery or visual inspection.
- Add self-contained HTML for offline editing, live rendering, validation, zoom, copy, and download controls.
- Keep optional Datasheet dimensions in the same JSON5 under top-level `datasheet.annotations`.
- State assumptions that materially affect timing semantics.
- Return absolute paths for every artifact.

## Workflow

1. **Classify the request.** Use `signal` for natural-language timing diagrams. Preserve or generate official `assign` and `reg` diagrams when explicitly requested. Treat a supplied specification, RTL, trace, or timing table as authoritative.
2. **Build a timing contract.** Identify the time unit or clock domain, active edge, initial state, signals and active levels, ordered events, latency, transfer conditions, final state, and unresolved assumptions.
3. **Resolve consequential ambiguity.** Ask only when a missing fact would materially change an implementation-accurate diagram. For a conceptual draft, apply conventional defaults and disclose them.
4. **Read the official syntax reference.** Read [references/wavejson-official.md](references/wavejson-official.md) before authoring WaveJSON. For standard protocols, also read [references/protocol-questions.md](references/protocol-questions.md). For synchronous or implementation-accurate work, read [references/semantic-review.md](references/semantic-review.md). For specification-sheet timing dimensions, read [references/datasheet-annotations.md](references/datasheet-annotations.md).
5. **Write official WaveJSON.** Preserve all official fields. Use `signal`, `assign`, or `reg` according to the requested diagram. For timing diagrams, use one slot consistently unless `period`, `phase`, or official `<...>` sub-cycle syntax is needed. Put causal relationships in `edge`; put Datasheet dimensions in `datasheet.annotations`. Do not duplicate the same endpoint pair in both.
6. **Validate with the official engine.** Prefer `wavedrom_validate` MCP. Otherwise run:

   ```text
   node <skill-dir>/scripts/validate-wavejson.mjs --input <source.json5>
   ```

   Default validation fails only on JSON5, official rendering, or Datasheet-extension errors; semantic lint remains advisory so official syntax is not blocked. Add `--strict` for natural-language-generated deliverables when every warning must fail the quality gate.
7. **Render locally.** Prefer `wavedrom_render` MCP. Otherwise run:

   ```text
   node <skill-dir>/scripts/render-wavedrom.mjs --input <source.json5> --svg <output.svg>
   ```

   Add `--png <output.png>` or `--html <output.html>` as needed. The renderer uses the same pinned official engine and all shipped skins for SVG and offline HTML. It post-processes `datasheet.annotations` only on `signal` diagrams and uses the enhanced SVG consistently for PNG and HTML. Do not silently install dependencies; when installation is authorized, run `npm ci --omit=dev` in the skill directory.
8. **Inspect and reconcile.** Check labels, transitions, grouping, arrows, cropping, skin, and clipping. For Datasheet dimensions, also check projection lines, arrowheads, subscripts, stacking, and hidden node labels. Reconcile the rendered result with the timing contract; renderability does not prove protocol correctness.

## Natural-language policy

- Preserve explicit facts instead of replacing them with protocol defaults.
- Distinguish unknown `x`, high impedance `z`, held state `.`, gaps `|`, data boxes `=`/`2`-`9`, and sub-cycles `<...>`.
- Never invent a signal solely to make the picture look complete.
- Ask for protocol parameters or produce a clearly labeled conceptual example when a named protocol is ambiguous.
- Keep one diagram focused; split unrelated phases or clock domains when clarity improves.
- Interpret setup/hold/width/period styling requests as changes to optional `datasheet.annotations`, not as replacements for official WaveJSON.
- Preserve existing official syntax verbatim unless the user asks to revise it.

## Quality gates

- JSON5 parses.
- The pinned official engine produces an SVG from `signal`, `assign`, or `reg`.
- Strict lint reports no unresolved labels, nodes, undocumented wave characters, or suspicious configuration when strict mode is requested.
- Datasheet annotations, when present, target existing `signal` nodes and do not duplicate an `edge` pair.
- Synchronous transitions and transfer cycles match the timing contract.
- SVG exists, is non-empty, and contains an SVG root.
- HTML, when requested, is self-contained and can re-render the embedded source without network access.
- Final delivery links the source and rendered artifacts and lists assumptions.

## Dependency baseline

Require Node.js 20 or newer. Pin the official main package as `wavedrom@3.6.2` and load its six shipped skins: `default`, `narrow`, `dark`, `lowkey`, `narrower`, and `narrowerer`. Use `@resvg/resvg-js` only to derive PNG from the canonical official SVG.

The official main-package CLI remains available separately as `npx wavedrom --input source.json5 > output.svg`; this skill calls the same package engine directly so MCP, SVG, PNG, and offline HTML share one compatibility baseline.

When MCP tools are not registered and the user wants them, read [references/mcp-registration.md](references/mcp-registration.md) and prefer the bundled registration script.

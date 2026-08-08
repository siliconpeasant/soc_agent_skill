# MCP tools

The skill repository bundles a local stdio MCP server named `wavedrom-gen`. It exposes deterministic WaveDrom operations and Datasheet annotation rendering; the agent using this skill remains responsible for translating natural language into semantically correct WaveJSON and `datasheet.annotations`.

## `wavedrom_help`

Returns a compact WaveJSON reminder and the recommended generation workflow. It does not read or write files.

## `wavedrom_validate`

Inputs:

- `source`: complete WaveJSON or JSON5 text;
- `strict`: optional boolean; warnings make the call fail when true.

Returns validation status, errors, warnings, and lane/data-box/node/edge counts. Validation uses a temporary file that is removed after the call.

## `wavedrom_render`

Inputs:

- `source`: complete WaveJSON or JSON5 text;
- `outputDirectory`: absolute destination directory;
- `baseName`: optional portable filename stem; defaults to `wavedrom-diagram`;
- `formats`: optional subset of `svg`, `png`, and `html`; defaults to `svg`;
- `strict`: optional boolean;
- `overwrite`: optional boolean; defaults to false.

The tool first validates the source, then saves `<baseName>.json5` and renders through the official `wavedrom-cli`. When the source contains `datasheet.annotations`, it post-processes the SVG with horizontal timing dimensions and uses that enhanced SVG for PNG and HTML too. SVG is always produced as the canonical baseline, even when only PNG or HTML was requested. Existing target files are rejected unless `overwrite` is explicitly true.

The HTML output is self-contained and supports offline editing, live rendering of WaveDrom plus Datasheet annotations, validation, zoom, copy, and SVG/PNG download.

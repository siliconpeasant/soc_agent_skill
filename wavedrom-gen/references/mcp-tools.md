# MCP tools

The skill repository bundles a local stdio MCP server named `wavedrom-gen`. It exposes deterministic WaveDrom operations; the agent using this skill remains responsible for translating natural language into semantically correct WaveJSON.

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

The tool first validates the source, then saves `<baseName>.json5` and renders through the official `wavedrom-cli`. SVG is always produced as the canonical baseline, even when only PNG or HTML was requested. Existing target files are rejected unless `overwrite` is explicitly true.

The HTML output is self-contained and supports offline editing, live rendering, validation, zoom, copy, and SVG/PNG download.

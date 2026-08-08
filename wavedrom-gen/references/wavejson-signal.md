# WaveJSON signal diagrams

Use this reference when translating a timing contract into input for `wavedrom-cli`.

Primary sources:

- WaveDrom tutorial: https://wavedrom.com/tutorial.html
- WaveDrom CLI: https://github.com/wavedrom/cli

## Basic structure

```json5
{
  signal: [
    { name: 'clk',   wave: 'p.......' },
    { name: 'valid', wave: '0.1...0.' },
    { name: 'data',  wave: 'x.2...x.', data: ['0x35'] },
  ],
  head: { text: 'Example', tick: 0 },
  config: { hscale: 1 },
}
```

Each `wave` character represents one time period. `.` holds the preceding state for another period.

## Wave characters

| Character | Meaning |
|---|---|
| `0`, `1` | Defined logic low or high |
| `x` | Unknown or intentionally unspecified |
| `z` | High impedance |
| `.` | Continue the previous state |
| `=` | Labeled multi-bit data region |
| `2`-`9` | Labeled data regions with different colors |
| `p`, `P` | Positive-polarity clock; uppercase marks the working edge |
| `n`, `N` | Negative-polarity clock; uppercase marks the working edge |
| `h`, `H`, `l`, `L` | Clock-level and marked clock-level segments |
| `u`, `d` | Pull-up or pull-down style transition states |
| `|` | Visible time-axis gap while continuing the timeline |

Provide one `data` label for every `=`, `2`, ..., `9` occurrence that introduces a data box. Labels may be an array or a whitespace-separated string. Prefer arrays when labels contain spaces.

## Groups and spacers

Use a nested array whose first element is the group name. Use an empty object as a vertical spacer.

```json5
{
  signal: [
    { name: 'clk', wave: 'p.....' },
    ['Master',
      { name: 'req',  wave: '0.1.0.' },
      { name: 'data', wave: 'x.2.x.', data: ['D0'] },
    ],
    {},
    ['Slave',
      { name: 'ack', wave: '0..10.' },
    ],
  ],
}
```

## Period and phase

- `period` scales the lane's horizontal period.
- `phase` shifts the lane horizontally and may be fractional.
- Use them only when a common slot grid cannot express the requested relationship clearly.
- Judge alignment from the rendered output, not raw string length alone.

## Titles, ticks, and scale

```json5
{
  signal: [{ name: 'clk', wave: 'p.......' }],
  head: { text: 'Read transaction', tick: 0, every: 2 },
  foot: { text: 'conceptual timing' },
  config: { hscale: 2, skin: 'default' },
}
```

- `head.text` and `foot.text` add captions.
- `tick` labels time boundaries; `tock` labels intervals between boundaries.
- `every` displays every Nth label.
- Positive integer `config.hscale` expands the horizontal scale.
- The CLI loads the WaveDrom skins supplied by its installed version; verify the selected skin by rendering.

## Nodes and edges

Place one-character node identifiers in a `node` string aligned to the lane's time positions, then connect them in top-level `edge` entries.

```json5
{
  signal: [
    { name: 'req', wave: '0.1..0', node: '..a..b' },
    { name: 'ack', wave: '0...10', node: '....c.' },
  ],
  edge: ['a~>c response', 'c->b clear'],
}
```

Common connectors include straight `->`, curved `~>`, orthogonal `-|>`, bidirectional `<->`, and measurement `+`. Render complex connectors before trusting their placement.

## CLI constraints

- Save a JSON or JSON5 object, not executable JavaScript.
- The tutorial's programmatic JavaScript example is appropriate for browser-side generation but is not direct JSON5 input for `wavedrom-cli`.
- Default to SVG output because it stays sharp and version-controllable.
- Use strict JSON when the target Markdown renderer does not accept JSON5, but keep CLI source as JSON5 when comments or trailing commas improve maintainability.

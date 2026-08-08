# Official WaveJSON reference

Use this reference when translating natural language into input for the pinned official `wavedrom@3.6.2` engine.

Primary sources:

- WaveDrom main repository: https://github.com/wavedrom/wavedrom
- Official tutorial: https://wavedrom.com/tutorial.html
- Official 3.6.2 source and tests: `lib/`, `skins/`, and `test/` in the main repository

## Diagram dispatch

The official `renderAny` engine recognizes these top-level keys in this precedence order:

1. `signal`: digital timing diagram;
2. `assign`: logic-expression diagram;
3. `reg`: register bit-field diagram.

Generate `signal` for natural-language timing requests. Preserve existing `assign` and `reg` source without translating it into a timing diagram unless the user asks for that change.

## Signal structure

```json5
{
  signal: [
    { name: 'clk', wave: 'p.......' },
    { name: 'bus', wave: 'x.3..4.x', data: ['ADDR', 'DATA'] },
  ],
  edge: [],
  head: { text: 'Transaction', tick: 0 },
  foot: { text: 'conceptual timing', tock: 0 },
  config: { hscale: 1, skin: 'default' },
}
```

Each ordinary `wave` character advances one time period. `.` and `|` extend the preceding state. A lane may use `period` to scale its period and `phase` to shift it horizontally; both may be fractional where the official renderer supports it.

### Wave characters

| Character | Meaning |
|---|---|
| `0`, `1` | Defined logic low or high |
| `x` | Unknown or intentionally unspecified |
| `z` | High impedance |
| `.` | Continue the previous state |
| `=` | Data box using the first data color |
| `2`-`9` | Data boxes using numbered colors |
| `p`, `P` | Positive-polarity clock; uppercase marks the working edge |
| `n`, `N` | Negative-polarity clock; uppercase marks the working edge |
| `h`, `H`, `l`, `L` | Clock-level and marked clock-level segments |
| `u`, `d` | Pull-up or pull-down transition style |
| `|` | Visible gap while continuing the time grid |
| `<`, `>` | Enter and leave a sub-cycle region |

Provide `data` as an array or whitespace-separated string. Prefer an array when a label contains spaces. The official engine can render unlabeled boxes, but natural-language generation should normally supply one label per `=`, `2`, ..., `9` box.

### Sub-cycles

Use `<...>` inside a wave string to place multiple transitions inside one normal period. This is official but advanced syntax; render and visually verify it.

```json5
{
  signal: [
    { name: 'P1', wave: '==2<30>2<0xx1>23', data: ['A', 'B', 'C', 'D', 'E', 'F'] },
    { name: 'P2', wave: '=2<15.1>2<01>23', period: 2, data: ['A', 'B', 'C', 'D', 'E'] },
  ],
}
```

### Groups and spacers

Use a nested array whose first item is the group name. Groups may be nested. Use `{}` as a spacer.

```json5
{
  signal: [
    ['Master',
      ['Control',
        { name: 'valid', wave: '01..0.' },
        { name: 'ready', wave: '0.1...' },
      ],
      { name: 'data', wave: 'x.3.x.', data: ['D0'] },
    ],
    {},
    ['Slave', { name: 'done', wave: '0...10' }],
  ],
}
```

### Nodes and edges

Place one-character event markers in a lane's `node` string. Each position aligns with that lane's time and respects its `period` and `phase`. Lowercase markers are visible; uppercase markers are useful when the marker label should remain hidden.

An edge string is:

```text
<from><shape><to> optional label
```

Official shapes in 3.6.2:

| Family | Shapes |
|---|---|
| Unarrowed | `-`, `~`, `-~`, `~-`, `-|`, `|-`, `-|-` |
| One-way arrows | `->`, `~>`, `-~>`, `~->`, `-|>`, `|->`, `-|->` |
| Two-way arrows | `<->`, `<~>`, `<-~>`, `<-|>`, `<-|->` |
| Dimension tees | `+` |

```json5
{
  signal: [
    { name: 'req', wave: '0.1...0', node: '..a...b' },
    { name: 'ack', wave: '0...1.0', node: '....c..' },
  ],
  edge: ['a~>c response', 'c-|->b clear', 'a+b interval'],
  config: { arcFontSize: 12 },
}
```

Use official `edge` for causal arrows and simple dimension tees. Use the optional `datasheet.annotations` extension only for Datasheet-style horizontal setup/hold/width/period dimensions.

### Head, foot, and JsonML text

`head` and `foot` support:

- `tick`: labels time boundaries from a starting value;
- `tock`: labels intervals between boundaries;
- `every`: shows every Nth label;
- `text`: plain text or JsonML SVG `tspan` content.

```json5
{
  signal: [{ name: 'clk', wave: 'p.....' }],
  head: {
    tick: 0,
    every: 2,
    text: ['tspan', ['tspan', { class: 'h2' }, 'Read '], ['tspan', { class: 'info' }, 'transaction']],
  },
  foot: { tock: 0, text: 'Figure 1' },
}
```

Predefined text classes include `h1` through `h6`, `muted`, `warning`, `error`, `info`, and `success`. JsonML may also carry SVG `tspan` attributes such as `fill`, `font-weight`, `font-style`, `text-decoration`, `baseline-shift`, `dy`, and `font-size`.

### Config and skins

Timing-diagram configuration supported by the official source includes:

- `hscale`: horizontal scale, rounded and capped at 100;
- `hbounds: [minimum, maximum]`: crop the visible horizontal tick range;
- `skin`: select a loaded skin;
- `arcFontSize`: edge-label font size.

The skill loads every skin shipped by `wavedrom@3.6.2`: `default`, `narrow`, `dark`, `lowkey`, `narrower`, and `narrowerer`.

## Assign diagrams

The official engine delegates `assign` to LogiDrom. The outer array contains output/expression pairs; nested prefix arrays describe operators.

```json5
{
  assign: [
    ['z', ['~&', ['~^', ['~', 'p0'], ['~', 'q0']], ['~', 'enable']]],
  ],
}
```

Pass user-provided official expressions directly to the engine. For natural-language logic generation, render small increments because operator layout is owned by the bundled LogiDrom version.

## Register diagrams

The official engine delegates `reg` to the bundled `bit-field` renderer.

```json5
{
  reg: [
    { bits: 7, name: 0x37, attr: ['OPIVI'] },
    { bits: 5, name: 'vd', type: 2 },
    { bits: 3, name: 3 },
    { bits: 5, name: 'simm5', type: 5 },
  ],
  config: { lanes: 1, bits: 20 },
}
```

Preserve official `reg` field and `config` properties. Do not apply Datasheet timing annotations to `assign` or `reg` diagrams.

## Compatibility rule

- Treat JSON5 parsing plus successful `wavedrom@3.6.2` `renderAny` SVG generation as the hard compatibility gate.
- Treat the skill's semantic checks as advisory warnings by default.
- Use strict validation for natural-language-generated deliverables when missing labels, unresolved nodes, undocumented wave characters, or suspicious configuration should fail the quality gate.
- Do not strip unknown top-level or lane fields before rendering; preserving the source allows official features to pass through unchanged.

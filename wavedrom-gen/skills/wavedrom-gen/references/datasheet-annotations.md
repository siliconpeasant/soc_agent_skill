# Datasheet annotations

Use the optional top-level `datasheet` object when timing parameters must look like specification-sheet dimensions instead of WaveDrom causal edges.

```json5
{
  signal: [
    { name: 'DATA', wave: 'x.=..x', data: ['A'], node: '..d...' },
    { name: 'CLK',  wave: '0..1..',             node: '...c..' },
  ],
  datasheet: {
    hideNodeLabels: 'all',
    annotations: [
      { from: 'd', to: 'c', label: 'T_SETUP', kind: 'setup' },
    ],
  },
}
```

The renderer keeps WaveDrom responsible for waveforms, then post-processes its SVG with horizontal double-headed dimension lines, projection lines, hidden endpoint markers, and SVG subscript text. PNG and offline HTML use the same enhanced SVG.

## Annotation fields

- `from`, `to`: required single-character WaveDrom node markers.
- `label`: required text. The first underscore starts the subscript, so `T_SUP_PD` renders `T` with `SUP_PD` as a subscript.
- `kind`: optional `setup`, `hold`, `width`, `period`, or `generic`.
- `placement`: optional `above` or `below`; defaults to `above`.
- `anchor`: optional `from`, `to`, `top`, or `bottom`. Setup defaults to `from`; hold defaults to `to`; other kinds default to `top`.
- `level`: optional non-negative stacking level. Omit it for automatic collision-aware placement.
- `offset`: optional distance from the anchor lane.
- `projection`: optional `dashed`, `solid`, or `none`; defaults to `dashed`.
- `hideNodes`: optional boolean; defaults to true.
- `hideNodeLabels`: optional global `used`, `all`, or `none`; defaults to `used`. Use `all` for clean publication output.

Endpoint convention:

- Setup: `from` is the constrained signal event and `to` is the reference event.
- Hold: `from` is the reference event and `to` is the constrained signal event.
- Width/period: order the endpoints from earlier to later time.

Do not also add the same endpoint pair to top-level `edge`; the validator warns because both annotations would render.

## Global style

Use `datasheet.style` only when the user requests a visual change:

```json5
datasheet: {
  style: {
    color: '#111',
    strokeWidth: 1.35,
    fontSize: 14,
    subscriptSize: 8.5,
    fontFamily: 'Arial, Helvetica, sans-serif',
    offset: 18,
    stackGap: 20,
    collisionPadding: 12,
    dash: '4 3',
    labelBackground: '#fff',
    margin: 12,
  },
  annotations: [],
}
```

## Natural-language edits

Translate requests by changing node markers or annotation objects, then validate and re-render:

- “把 DATA 到 CLK 上升沿标成建立时间 `T_SETUP`” → add a `setup` annotation from the DATA event node to the CLK node.
- “这条标注移到下面” → set `placement: 'below'`.
- “再错开一层” → increment `level`.
- “投影线改成实线” → set `projection: 'solid'`.
- “箭头名字改成 `T_SU_D`” → change `label`; the subscript is regenerated automatically.

Natural language is the authoring interface; `datasheet` is the deterministic intermediate representation.

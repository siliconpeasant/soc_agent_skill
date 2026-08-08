(function attachWaveDromDatasheet(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.WaveDromDatasheet = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function createWaveDromDatasheet() {
  'use strict';

  const KINDS = new Set(['setup', 'hold', 'width', 'period', 'generic']);
  const PLACEMENTS = new Set(['above', 'below']);
  const ANCHORS = new Set(['from', 'to', 'top', 'bottom']);
  const PROJECTIONS = new Set(['dashed', 'solid', 'none']);
  const NODE_VISIBILITY = new Set(['used', 'all', 'none']);
  const NODE_GROUP = /<g transform="translate\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"><rect\b[^>]*\/?><text\b[^>]*><tspan>([A-Za-z0-9])<\/tspan><\/text><\/g>/g;

  function escapeXml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&apos;');
  }

  function finiteNumber(value, fallback) {
    return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
  }

  function extractNodes(svg) {
    const nodes = new Map();
    const arcsStart = svg.search(/<g id="wavearcs_[^"]*">/i);
    const searchable = arcsStart >= 0 ? svg.slice(arcsStart) : svg;
    for (const match of searchable.matchAll(NODE_GROUP)) {
      nodes.set(match[3], {
        name: match[3],
        x: Number(match[1]),
        y: Number(match[2]),
        markup: match[0],
      });
    }
    return nodes;
  }

  function edgeEndpoints(edge) {
    const expression = String(edge).trim().split(/\s+/, 1)[0];
    const refs = expression.match(/[A-Za-z0-9]/g) || [];
    return refs.length >= 2 ? [refs[0], refs[refs.length - 1]] : [];
  }

  function validateDatasheetConfig(datasheet, knownNodes, edges) {
    const errors = [];
    const warnings = [];
    const nodes = knownNodes instanceof Set ? knownNodes : new Set(knownNodes || []);
    const edgePairs = new Set((edges || []).map(edgeEndpoints).filter(pair => pair.length === 2).map(pair => pair.sort().join(':')));
    let count = 0;

    if (datasheet === undefined) return { errors, warnings, count };
    if (!datasheet || typeof datasheet !== 'object' || Array.isArray(datasheet)) {
      return { errors: ['datasheet must be an object.'], warnings, count };
    }
    if (!Array.isArray(datasheet.annotations)) {
      return { errors: ['datasheet.annotations must be an array.'], warnings, count };
    }
    if (datasheet.hideNodeLabels !== undefined && !NODE_VISIBILITY.has(datasheet.hideNodeLabels)) {
      errors.push('datasheet.hideNodeLabels must be used, all, or none.');
    }

    const style = datasheet.style;
    if (style !== undefined && (!style || typeof style !== 'object' || Array.isArray(style))) {
      errors.push('datasheet.style must be an object.');
    }

    datasheet.annotations.forEach((annotation, index) => {
      const place = `datasheet.annotations[${index}]`;
      if (!annotation || typeof annotation !== 'object' || Array.isArray(annotation)) {
        errors.push(`${place} must be an object.`);
        return;
      }
      count += 1;
      for (const key of ['from', 'to']) {
        const value = annotation[key];
        if (typeof value !== 'string' || !/^[A-Za-z0-9]$/.test(value)) {
          errors.push(`${place}.${key} must be one WaveDrom node marker.`);
        } else if (!nodes.has(value)) {
          errors.push(`${place}.${key} references missing node: ${value}`);
        }
      }
      if (annotation.from === annotation.to && annotation.from !== undefined) errors.push(`${place} endpoints must be different.`);
      if (typeof annotation.label !== 'string' || annotation.label.trim() === '') errors.push(`${place}.label must be a non-empty string.`);
      if (annotation.kind !== undefined && !KINDS.has(annotation.kind)) errors.push(`${place}.kind must be setup, hold, width, period, or generic.`);
      if (annotation.placement !== undefined && !PLACEMENTS.has(annotation.placement)) errors.push(`${place}.placement must be above or below.`);
      if (annotation.anchor !== undefined && !ANCHORS.has(annotation.anchor)) errors.push(`${place}.anchor must be from, to, top, or bottom.`);
      if (annotation.projection !== undefined && !PROJECTIONS.has(annotation.projection)) errors.push(`${place}.projection must be dashed, solid, or none.`);
      if (annotation.level !== undefined && (!Number.isInteger(annotation.level) || annotation.level < 0)) errors.push(`${place}.level must be a non-negative integer.`);
      if (annotation.offset !== undefined && (typeof annotation.offset !== 'number' || !Number.isFinite(annotation.offset) || annotation.offset < 0)) errors.push(`${place}.offset must be a non-negative number.`);
      if (annotation.hideNodes !== undefined && typeof annotation.hideNodes !== 'boolean') errors.push(`${place}.hideNodes must be boolean.`);
      if (/^[A-Za-z0-9]$/.test(annotation.from || '') && /^[A-Za-z0-9]$/.test(annotation.to || '')) {
        const pair = [annotation.from, annotation.to].sort().join(':');
        if (edgePairs.has(pair)) warnings.push(`${place} duplicates a WaveDrom edge between ${annotation.from} and ${annotation.to}; remove that edge to avoid two annotations.`);
      }
    });
    return { errors, warnings, count };
  }

  function labelParts(label) {
    const text = String(label).trim();
    const split = text.indexOf('_');
    return split < 0 ? { base: text, subscript: '' } : { base: text.slice(0, split), subscript: text.slice(split + 1) };
  }

  function intervalOverlaps(left, right, padding) {
    return left.minX <= right.maxX + padding && right.minX <= left.maxX + padding;
  }

  function expandRoot(svg, minY, maxY, margin) {
    const rootMatch = svg.match(/<svg\b[^>]*>/i);
    if (!rootMatch) return svg;
    const tag = rootMatch[0];
    const viewMatch = tag.match(/viewBox="\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*"/i);
    if (!viewMatch) return svg;
    const x = Number(viewMatch[1]);
    const y = Number(viewMatch[2]);
    const width = Number(viewMatch[3]);
    const height = Number(viewMatch[4]);
    const extraTop = Math.max(0, Math.ceil(y - minY + margin));
    const extraBottom = Math.max(0, Math.ceil(maxY + 60 - (y + height) + margin));
    if (!extraTop && !extraBottom) return svg;
    const nextY = y - extraTop;
    const nextHeight = height + extraTop + extraBottom;
    let nextTag = tag.replace(viewMatch[0], `viewBox="${x} ${nextY} ${width} ${nextHeight}"`);
    nextTag = nextTag.replace(/height="(\d+(?:\.\d+)?)(?:px)?"/i, (_all, value) => `height="${Number(value) + extraTop + extraBottom}"`);
    return svg.replace(tag, nextTag);
  }

  function applyDatasheetAnnotations(svgText, datasheet) {
    if (!datasheet || !Array.isArray(datasheet.annotations) || datasheet.annotations.length === 0) {
      return { svg: svgText, count: 0, hiddenNodes: [] };
    }
    let svg = String(svgText);
    const nodes = extractNodes(svg);
    const validation = validateDatasheetConfig(datasheet, new Set(nodes.keys()), []);
    if (validation.errors.length) throw new Error(validation.errors.join(' '));

    const style = datasheet.style || {};
    const color = escapeXml(style.color || '#111');
    const strokeWidth = finiteNumber(style.strokeWidth, 1.35);
    const fontSize = finiteNumber(style.fontSize, 14);
    const subscriptSize = finiteNumber(style.subscriptSize, Math.max(8, fontSize * 0.62));
    const fontFamily = escapeXml(style.fontFamily || 'Arial, Helvetica, sans-serif');
    const defaultOffset = finiteNumber(style.offset, 18);
    const stackGap = finiteNumber(style.stackGap, 20);
    const collisionPadding = finiteNumber(style.collisionPadding, 12);
    const margin = finiteNumber(style.margin, 12);
    const markerId = 'datasheet-dim-arrow';
    const assignments = [];

    const prepared = datasheet.annotations.map((annotation, index) => {
      const from = nodes.get(annotation.from);
      const to = nodes.get(annotation.to);
      const kind = annotation.kind || 'generic';
      const placement = annotation.placement || 'above';
      const anchor = annotation.anchor || (kind === 'hold' ? 'to' : kind === 'setup' ? 'from' : 'top');
      const anchorY = anchor === 'from' ? from.y : anchor === 'to' ? to.y : anchor === 'bottom' ? Math.max(from.y, to.y) : Math.min(from.y, to.y);
      const offset = finiteNumber(annotation.offset, defaultOffset);
      const direction = placement === 'below' ? 1 : -1;
      const baseY = anchorY + direction * offset;
      const parts = labelParts(annotation.label);
      const estimatedWidth = Math.max(28, parts.base.length * fontSize * 0.62 + parts.subscript.length * subscriptSize * 0.6 + 12);
      const minX = Math.min(from.x, to.x);
      const maxX = Math.max(from.x, to.x);
      const centerX = (minX + maxX) / 2;
      const item = { annotation, index, from, to, kind, placement, direction, baseY, minX, maxX, parts, estimatedWidth, centerX, labelMinX: centerX - estimatedWidth / 2, labelMaxX: centerX + estimatedWidth / 2 };
      let level = annotation.level;
      if (level === undefined) {
        level = 0;
        while (assignments.some(existing => {
          const candidateY = baseY + direction * level * stackGap;
          return intervalOverlaps(
            { minX: item.labelMinX, maxX: item.labelMaxX },
            { minX: existing.labelMinX, maxX: existing.labelMaxX },
            collisionPadding,
          ) && Math.abs(candidateY - existing.y) < fontSize + 5;
        })) level += 1;
      }
      item.level = level;
      item.y = baseY + direction * level * stackGap;
      assignments.push(item);
      return item;
    });

    if (!svg.includes(`id="${markerId}"`)) {
      const marker = `<marker id="${markerId}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="${color}"/></marker>`;
      if (!/<\/defs>/i.test(svg)) throw new Error('WaveDrom SVG defs section was not found.');
      svg = svg.replace(/<\/defs>/i, `${marker}</defs>`);
    }

    const hideMode = datasheet.hideNodeLabels || 'used';
    const hiddenNodes = new Set(hideMode === 'all' ? nodes.keys() : []);
    const groups = prepared.map((item) => {
      const { annotation, from, to, y, minX, maxX, kind, index, parts, estimatedWidth, centerX } = item;
      if ((hideMode === 'used' && annotation.hideNodes !== false) || (hideMode === 'none' && annotation.hideNodes === true)) {
        hiddenNodes.add(annotation.from); hiddenNodes.add(annotation.to);
      }
      const inset = Math.min(4, Math.max(0, (maxX - minX) / 4));
      const projection = annotation.projection || 'dashed';
      const dash = projection === 'dashed' ? ` stroke-dasharray="${escapeXml(style.dash || '4 3')}"` : '';
      const projectionLines = projection === 'none' ? '' : `<line x1="${from.x}" y1="${from.y}" x2="${from.x}" y2="${y}" stroke="${color}" stroke-width="${strokeWidth}"${dash}/><line x1="${to.x}" y1="${to.y}" x2="${to.x}" y2="${y}" stroke="${color}" stroke-width="${strokeWidth}"${dash}/>`;
      const textY = y - 2;
      const label = parts.subscript
        ? `${escapeXml(parts.base)}<tspan baseline-shift="sub" font-size="${subscriptSize}" font-style="normal">${escapeXml(parts.subscript)}</tspan>`
        : escapeXml(parts.base);
      return `<g id="datasheet-dimension-${index}" data-kind="${escapeXml(kind)}" aria-label="${escapeXml(annotation.label)}">${projectionLines}<line x1="${minX + inset}" y1="${y}" x2="${maxX - inset}" y2="${y}" stroke="${color}" stroke-width="${strokeWidth}" marker-start="url(#${markerId})" marker-end="url(#${markerId})"/><rect x="${centerX - estimatedWidth / 2}" y="${textY - fontSize + 2}" width="${estimatedWidth}" height="${fontSize + 4}" fill="${escapeXml(style.labelBackground || '#fff')}"/><text x="${centerX}" y="${textY}" text-anchor="middle" fill="${color}" font-family="${fontFamily}" font-size="${fontSize}" font-style="italic">${label}</text></g>`;
    });

    const arcs = /<g id="wavearcs_[^"]*">/i;
    if (!arcs.test(svg)) throw new Error('WaveDrom SVG wavearcs group was not found.');
    svg = svg.replace(arcs, match => `${match}${groups.join('')}`);
    for (const nodeName of hiddenNodes) {
      const node = nodes.get(nodeName);
      if (node) svg = svg.replace(node.markup, '');
    }
    const ys = prepared.map(item => item.y);
    svg = expandRoot(svg, Math.min(...ys), Math.max(...ys), margin);
    return { svg, count: prepared.length, hiddenNodes: [...hiddenNodes] };
  }

  return { applyDatasheetAnnotations, extractNodes, validateDatasheetConfig };
}));

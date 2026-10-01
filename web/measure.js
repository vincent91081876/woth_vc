// Pure helpers for the map scale bar and distance tool (no DOM access, unit-testable with node).
// World coordinates are Unreal centimetres; distances here are metres (horizontal, ignoring height).
(function (root) {
  'use strict';
  const M = {};
  M.dist = (a, b) => Math.hypot(b.x - a.x, b.y - a.y) / 100;                // metres
  M.fmtDist = m => {
    if (!isFinite(m)) return '—';
    if (m < 1000) return (m < 10 ? m.toFixed(1) : Math.round(m)) + ' m';
    const k = m / 1000; return (k < 10 ? k.toFixed(2) : k.toFixed(1)) + ' km';
  };
  M.pathLength = pts => { let t = 0; for (let i = 1; i < pts.length; i++) t += M.dist(pts[i - 1], pts[i]); return t; };
  // Screen direction of a vector given in screen pixels (x right, y down) -> arrow + words.
  M.screenDir = (dx, dy) => {
    if (!dx && !dy) return '';
    const names = [['→', '右'], ['↘', '右下'], ['↓', '下'], ['↙', '左下'], ['←', '左'], ['↖', '左上'], ['↑', '上'], ['↗', '右上']];
    const i = Math.round(Math.atan2(dy, dx) / (Math.PI / 4) + 8) % 8;
    return names[i][0] + ' 圖上' + names[i][1] + '方';
  };
  // Pick a "nice" scale-bar length (1/2/5 x 10^k metres) whose on-screen width is <= maxPx.
  // pxPerM = screen pixels per metre. Returns {m, px, parts}.
  M.niceScale = (pxPerM, maxPx) => {
    maxPx = maxPx || 180;
    if (!(pxPerM > 0)) return null;
    let best = null;
    for (let e = -2; e <= 6; e++) for (const d of [1, 2, 5]) {
      const m = d * Math.pow(10, e), px = m * pxPerM;
      if (px <= maxPx && (!best || m > best.m)) best = { m, px, d };
    }
    if (!best) return null;
    best.parts = best.d === 2 ? 4 : 5;
    if (best.d === 5) best.parts = 5;
    return best;
  };
  // Zoom the map view by factor f about the screen point (mx,my) so the map point under the cursor stays put.
  // The map is drawn at  screen = pad + u*scale + offset  (pad = fixed margin), so pad must not be folded into offset.
  M.zoomAt = (view, mx, my, f, pad) => {
    pad = pad || 0;
    return { s: view.s * f, ox: mx - pad - (mx - pad - view.ox) * f, oy: my - pad - (my - pad - view.oy) * f };
  };
  M.scaleLabel = m => m >= 1000 ? (m / 1000) + ' km' : (m >= 1 ? m + ' m' : (m * 100) + ' cm');
  root.WothMeasure = M;
  if (typeof module !== 'undefined' && module.exports) module.exports = M;
})(typeof window !== 'undefined' ? window : globalThis);

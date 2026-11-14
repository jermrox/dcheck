/* Lot scene builder shared by the standalone lot page and the Interior Studio "Site" layer.
   buildLotScene(D, opts) -> {root, terrain, levelGroups, roofG, ceilG}; everything is in plot feet (x east, z south, y above datum). */
function buildLotScene(D, opts = {}) {
const root = new THREE.Group();
const G = D.ground, N = D.N;
// terrain: grid of heights, plot texture draped (x right, z down the plot = south)
const tg = new THREE.PlaneGeometry(G.w, G.h, N, N); tg.rotateX(-Math.PI / 2);
const pos = tg.attributes.position;
for (let j = 0; j <= N; j++) for (let i = 0; i <= N; i++) { const k = j * (N + 1) + i; pos.setXYZ(k, G.x + i * G.w / N, D.grid[j][i], G.z + j * G.h / N); }
tg.computeVertexNormals();
const tex = new THREE.TextureLoader().load(G.src, () => (window.__ready = 1, opts.onReady && opts.onReady())); tex.anisotropy = 8; tex.encoding = THREE.sRGBEncoding;
const landTex = G.land ? new THREE.TextureLoader().load(G.land) : tex; landTex.anisotropy = 8; landTex.encoding = THREE.sRGBEncoding;
const terrainM = new THREE.MeshLambertMaterial({ map: landTex });
const terrain = new THREE.Mesh(tg, terrainM); terrain.receiveShadow = true; root.add(terrain);
const setGround = kind => { terrainM.map = kind === 'survey' ? tex : landTex; terrainM.needsUpdate = true; };
const hAt = (x, z) => { const i = Math.max(0, Math.min(N, Math.round((x - G.x) / G.w * N))), j = Math.max(0, Math.min(N, Math.round((z - G.z) / G.h * N))); return D.grid[j][i]; };
const shapeGeo = (pts) => { const g = new THREE.ShapeGeometry(new THREE.Shape(pts.map(p => new THREE.Vector2(p[0], -p[1])))); g.rotateX(-Math.PI / 2); return g; };
const prism = (pts, y0, y1, mat) => { const g = new THREE.ExtrudeGeometry(new THREE.Shape(pts.map(p => new THREE.Vector2(p[0], -p[1]))), { depth: y1 - y0, bevelEnabled: false }); g.rotateX(-Math.PI / 2); const m = new THREE.Mesh(g, mat); m.position.y = y0; m.castShadow = m.receiveShadow = true; return m; };
const E = D.extras;
function canvasTex(draw, n = 256) { const c = document.createElement('canvas'); c.width = c.height = n; draw(c.getContext('2d'), n); const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; t.encoding = THREE.sRGBEncoding; return t; }
const brickTex = canvasTex((g, n) => { g.fillStyle = '#cfccc5'; g.fillRect(0, 0, n, n); const bh = n / 12, bw = n / 4;
  for (let r = 0; r < 12; r++) for (let c = -1; c < 5; c++) { const x = c * bw + (r % 2 ? bw / 2 : 0), v = 238 + Math.random() * 14; g.fillStyle = `rgb(${v},${v - 1},${v - 4})`; g.fillRect(x + 1.5, r * bh + 1.5, bw - 3, bh - 3); } }, 512);
const shingleTex = canvasTex((g, n) => { g.fillStyle = '#3d3632'; g.fillRect(0, 0, n, n);
  for (let r = 0; r < 16; r++) for (let c = -1; c < 9; c++) { const v = 50 + Math.random() * 22; g.fillStyle = `rgb(${v + 6},${v},${v - 4})`; g.fillRect(c * n / 8 + (r % 2 ? n / 16 : 0) + 1, r * n / 16 + 1, n / 8 - 2, n / 16 - 3); } });
const uvScale = (geo, su, sv) => { const uv = geo.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * su, uv.getY(i) * sv); };
{ const fnd = prism(E.foundation.pts, E.foundation.bottom, E.foundation.top, new THREE.MeshLambertMaterial({ map: brickTex })); uvScale(fnd.geometry, 0.25, 0.4); root.add(fnd); }
// levels
const wallM = new THREE.MeshLambertMaterial({ color: 0xf3efe7 }), brickM = new THREE.MeshLambertMaterial({ map: brickTex }), frameM = new THREE.MeshLambertMaterial({ color: 0x1d1f22 }), garageM = new THREE.MeshLambertMaterial({ map: canvasTex((g, n) => { g.fillStyle = '#2e2c2a'; g.fillRect(0, 0, n, n); g.strokeStyle = '#1a1918'; g.lineWidth = 6; for (let i = 1; i < 4; i++) { g.beginPath(); g.moveTo(0, i * n / 4); g.lineTo(n, i * n / 4); g.stroke(); } g.fillStyle = '#5d6a73'; for (let i = 0; i < 6; i++) g.fillRect(i * n / 6 + 8, 10, n / 6 - 16, n / 5); }) }),
  glassM = new THREE.MeshStandardMaterial({ color: 0x1c2630, roughness: 0.08, metalness: 0.55, transparent: true, opacity: 0.82 }), muntinM = new THREE.MeshLambertMaterial({ color: 0x141517 });
const fp = E.foundation.pts, inside = (x, z) => { let c = false; for (let i = 0, j = fp.length - 1; i < fp.length; j = i++) { const [xi, zi] = fp[i], [xj, zj] = fp[j]; if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) c = !c; } return c; };
function awning(p0, p1, a, b, y, L) {   // shingled shed roof over a bay window, projecting 2.5 ft
  const ax = p0[0] + (p1[0] - p0[0]) * a, az = p0[1] + (p1[1] - p0[1]) * a, bx = p0[0] + (p1[0] - p0[0]) * b, bz = p0[1] + (p1[1] - p0[1]) * b;
  const len = Math.hypot(bx - ax, bz - az), ux = (bx - ax) / len, uz = (bz - az) / len; let nx = -uz, nz = ux;
  const mx = (ax + bx) / 2, mz = (az + bz) / 2; if (inside(mx + nx * 2, mz + nz * 2)) { nx = -nx; nz = -nz; }
  const d = 2.5, ext = 0.8, y0 = L.base + y + 0.4, rise = 1.4;
  const P = [[ax - ux * ext, az - uz * ext], [bx + ux * ext, bz + uz * ext]], Q = P.map(p => [p[0] + nx * d, p[1] + nz * d]);
  const V = [P[0][0], y0 + rise, P[0][1], P[1][0], y0 + rise, P[1][1], Q[1][0], y0, Q[1][1], P[0][0], y0 + rise, P[0][1], Q[1][0], y0, Q[1][1], Q[0][0], y0, Q[0][1]];
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(V, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, len / 6, 0, len / 6, 0.5, 0, 0, len / 6, 0.5, 0, 0.5], 2)); g.computeVertexNormals();
  awnG.add(new THREE.Mesh(g, new THREE.MeshLambertMaterial({ map: shingleTex, side: THREE.DoubleSide })));
  const f = new THREE.Mesh(new THREE.BoxGeometry(len + 2 * ext, 0.5, 0.2), new THREE.MeshLambertMaterial({ color: 0x1d1f22 })); f.position.set((Q[0][0] + Q[1][0]) / 2, y0 - 0.2, (Q[0][1] + Q[1][1]) / 2); f.rotation.y = Math.atan2(-uz, ux); awnG.add(f);
}
const awnG = new THREE.Group(); root.add(awnG);
const levelGroups = D.levels.map((L, li) => {
  const g = new THREE.Group(); root.add(g);
  const slab = new THREE.Group(); g.add(slab);
  for (const rm of L.rooms) { const m = new THREE.Mesh(shapeGeo(rm.pts), new THREE.MeshLambertMaterial({ color: rm.col })); m.position.y = L.base + 0.02 - (rm.drop || 0); m.receiveShadow = true; slab.add(m);
    if (rm.drop) { const sk = prism(rm.pts, L.base - rm.drop - 0.5, L.base - rm.drop, new THREE.MeshLambertMaterial({ color: 0xb5b2ac })); slab.add(sk); } }
  const piece = (p0, p1, f0, f1, y0, y1, mat) => {
    const ax = p0[0] + (p1[0] - p0[0]) * f0, az = p0[1] + (p1[1] - p0[1]) * f0, bx = p0[0] + (p1[0] - p0[0]) * f1, bz = p0[1] + (p1[1] - p0[1]) * f1;
    const len = Math.hypot(bx - ax, bz - az); if (len < 0.05 || y1 <= y0) return;
    const geo = new THREE.BoxGeometry(len, y1 - y0, mat === glassM ? 0.08 : mat === muntinM ? 0.16 : mat === frameM ? 0.6 : 0.5); if (mat === brickM) uvScale(geo, len / 4, (y1 - y0) / 2.5);
    const b = new THREE.Mesh(geo, mat);
    b.position.set((ax + bx) / 2, L.base + (y0 + y1) / 2, (az + bz) / 2); b.rotation.y = Math.atan2(-(bz - az), bx - ax); b.castShadow = mat !== glassM; g.add(b);
  };
  for (const [p0, p1, ops, ext] of L.walls) {
    const M = ext ? brickM : wallM, len = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]); let f = 0; ops.sort((a, b) => a[0] - b[0]);
    for (const [a, b, t] of ops) {
      piece(p0, p1, f, a, 0, L.h, M); const fr = 0.25 / Math.max(len, 1);
      if (t === 'window' || t === 'bay') {   // black-framed windows with a grid of muntins (Elevation A)
        const lo = L.h >= 10 ? 2 : 2.5, hi = L.h >= 10 ? 8 : 7.5, wl = (b - a) * len;
        piece(p0, p1, a, b, 0, lo, M); piece(p0, p1, a, b, hi, L.h, M); piece(p0, p1, a, b, lo, hi, glassM);
        piece(p0, p1, a, b, lo - 0.25, lo, frameM); piece(p0, p1, a, b, hi, hi + 0.25, frameM); piece(p0, p1, a, a + fr, lo, hi, frameM); piece(p0, p1, b - fr, b, lo, hi, frameM);
        if (ext) { const nv = Math.max(1, Math.round(wl / 1.6)) ; for (let i = 1; i < nv; i++) { const m = a + (b - a) * i / nv; piece(p0, p1, m - fr * 0.25, m + fr * 0.25, lo, hi, muntinM); }
          for (const yy of [lo + (hi - lo) * 0.62]) piece(p0, p1, a, b, yy - 0.06, yy + 0.06, muntinM); }
        if (t === 'bay') awning(p0, p1, a, b, hi, L);
      }
      else if (t === 'garage') { piece(p0, p1, a, b, 0, 8, garageM); piece(p0, p1, a, b, 8, L.h, M); piece(p0, p1, a, b, 8, 8.3, frameM); }
      else if (ext && t === 'door') { piece(p0, p1, a, b, 8, L.h, M); piece(p0, p1, a, b, 0, 8, glassM); piece(p0, p1, a, a + fr, 0, 8, frameM); piece(p0, p1, b - fr, b, 0, 8, frameM); piece(p0, p1, a, b, 7.75, 8, frameM); piece(p0, p1, (a + b) / 2 - fr * 0.4, (a + b) / 2 + fr * 0.4, 0, 8, frameM); }
      else piece(p0, p1, a, b, t === 'door' ? 7 : 8, L.h, M);
      f = b;
    }
    piece(p0, p1, f, 1, 0, L.h, M);
    if (ext && li > 0) { const gap = L.base - (D.levels[0].base + D.levels[0].h); if (gap > 0.05) piece(p0, p1, 0, 1, -gap - 0.05, 0, brickM); }   // floor band
  }
  for (const it of (L.furn || [])) {   // furniture from the visualizer's starter layout
    const m = new THREE.Mesh(new THREE.BoxGeometry(it.w, it.h, it.d), new THREE.MeshLambertMaterial({ color: it.c }));
    m.position.set(it.p[0], L.base + it.e + it.h / 2, it.p[1]); m.rotation.y = -it.rot; m.castShadow = true; g.add(m);
  }
  return g;
});
// ceilings: flat at the room's height, vaulted (gable along the long side) or raised tray, with beams
const ceilG = new THREE.Group(); ceilG.visible = false; root.add(ceilG);
const ceilM = new THREE.MeshLambertMaterial({ color: 0xfbf9f4, side: THREE.DoubleSide }), beamM = new THREE.MeshLambertMaterial({ color: 0x7a5536 });
const beam = (p, q, y, w, h) => { const len = Math.hypot(q[0] - p[0], q[1] - p[1]); const b = new THREE.Mesh(new THREE.BoxGeometry(len, h, w), beamM); b.position.set((p[0] + q[0]) / 2, y - h / 2, (p[1] + q[1]) / 2); b.rotation.y = Math.atan2(-(q[1] - p[1]), q[0] - p[0]); ceilG.add(b); };
const lerp2 = (p, q, t) => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
for (const L of D.levels) for (const rm of L.rooms) {
  const [a, b, c, d] = rm.pts, base = L.base - (rm.drop || 0), wallTop = L.base + L.h;
  if (rm.ceil === 'vault') {
    const long = rm.w >= rm.d, rise = Math.min(rm.w, rm.d) * 0.25, y0 = wallTop, y1 = wallTop + rise;
    const [p0, p1, q0, q1] = long ? [a, b, d, c] : [a, d, b, c];         // eaves p0-p1 and q0-q1, ridge between
    const r0 = lerp2(p0, q0, 0.5), r1 = lerp2(p1, q1, 0.5), V = [];
    const tri = (A, B, C) => V.push(A[0], A[2], A[1], B[0], B[2], B[1], C[0], C[2], C[1]);
    const P0 = [p0[0], p0[1], y0], P1 = [p1[0], p1[1], y0], Q0 = [q0[0], q0[1], y0], Q1 = [q1[0], q1[1], y0], R0 = [r0[0], r0[1], y1], R1 = [r1[0], r1[1], y1];
    tri(P0, P1, R1); tri(P0, R1, R0); tri(Q0, R0, R1); tri(Q0, R1, Q1);
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(V, 3)); g.computeVertexNormals(); ceilG.add(new THREE.Mesh(g, ceilM));
    beam(r0, r1, y1, 0.67, 1.0);                                        // 8x12 ridge beam
    const n = Math.max(2, Math.round(Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 4));
    for (let i = 1; i < n; i++) { const t = i / n, e0 = lerp2(p0, p1, t), e1 = lerp2(q0, q1, t), m = lerp2(r0, r1, t); beam(e0, e1, y0 + 0.01, 0.67, 0.67); }
  } else {
    const h = typeof rm.ceil === 'number' ? rm.ceil : L.h, y = base + h;
    const m = new THREE.Mesh(shapeGeo(rm.pts), ceilM); m.position.y = y; ceilG.add(m);
    if (rm.name === 'Great Room') {                                      // recessed: one 12 in step, 8x4 box beams
      const inset = (p, k) => lerp2(p, lerp2(lerp2(a, c, 0.5), lerp2(a, c, 0.5), 0), k);
      const ctr = lerp2(a, c, 0.5), ins = [a, b, c, d].map(p => lerp2(p, ctr, 0.18));
      const tr = new THREE.Mesh(shapeGeo(ins), ceilM); tr.position.y = y + 1; ceilG.add(tr); m.position.y = y;
      for (let i = 1; i < 4; i++) { beam(lerp2(ins[0], ins[1], i / 4), lerp2(ins[3], ins[2], i / 4), y + 1, 0.67, 0.33); beam(lerp2(ins[0], ins[3], i / 4), lerp2(ins[1], ins[2], i / 4), y + 1, 0.67, 0.33); }
    }
  }
}
// hip roofs on each rectangle (pitch rise/run)
const roofG = new THREE.Group(); root.add(roofG); const roofM = new THREE.MeshLambertMaterial({ map: shingleTex, side: THREE.DoubleSide }), gableM = new THREE.MeshLambertMaterial({ map: brickTex, side: THREE.DoubleSide }), fasciaM = new THREE.MeshLambertMaterial({ color: 0x1d1f22 });
for (const R of D.roofs) {
  const [a, b, c, d] = R.pts, long = R.w >= R.d, half = Math.min(R.w, R.d) / 2, rise = half * R.pitch;
  const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2], lerp = (p, q, t) => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
  // ridge endpoints: inset by half the short side along the long axis
  let r0, r1;
  if (long) { const m0 = mid(a, d), m1 = mid(b, c), t = half / R.w; r0 = lerp(m0, m1, t); r1 = lerp(m0, m1, 1 - t); }
  else { const m0 = mid(a, b), m1 = mid(d, c), t = half / R.d; r0 = lerp(m0, m1, t); r1 = lerp(m0, m1, 1 - t); }
  const y0 = R.base, y1 = R.base + rise, V = [];
  const tri = (p, q, s) => V.push(p[0], p[2], p[1], q[0], q[2], q[1], s[0], s[2], s[1]);
  const A = [a[0], a[1], y0], B = [b[0], b[1], y0], C = [c[0], c[1], y0], Dd = [d[0], d[1], y0], R0 = [r0[0], r0[1], y1], R1 = [r1[0], r1[1], y1];
  const GV = [];
  if (R.kind === 'front') {           // ridge runs to the street; brick gable end at the front (d-c), hip at the back (a-b)
    const W2 = R.w / 2, rise2 = W2 * R.pitch, fm = mid(d, c), bm = mid(a, b), rb = lerp(bm, fm, Math.min(0.45, W2 / R.d)), Y1 = y0 + rise2;
    const FM = [fm[0], fm[1], Y1], RB = [rb[0], rb[1], Y1];
    tri(Dd, FM, RB); tri(Dd, RB, A); tri(C, B, RB); tri(C, RB, FM); tri(A, RB, B);
    GV.push(Dd[0], Dd[2], Dd[1], C[0], C[2], C[1], FM[0], FM[2], FM[1]);
    for (const [P1, P2] of [[Dd, FM], [FM, C]]) {   // black rake trim on the gable, as on Elevation A
      const dx = P2[0] - P1[0], dz = P2[1] - P1[1], dy = P2[2] - P1[2], l3 = Math.hypot(dx, dy, dz), tr = new THREE.Mesh(new THREE.BoxGeometry(l3, 0.75, 0.3), fasciaM);
      tr.position.set((P1[0] + P2[0]) / 2, (P1[2] + P2[2]) / 2 - 0.2, (P1[1] + P2[1]) / 2);
      tr.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), new THREE.Vector3(dx, dy, dz).normalize()); roofG.add(tr); }
  } else if (long) { tri(A, B, R1); tri(A, R1, R0); tri(C, Dd, R0); tri(C, R0, R1); tri(B, C, R1); tri(Dd, A, R0); }
  else { tri(B, C, R1); tri(B, R1, R0); tri(Dd, A, R0); tri(Dd, R0, R1); tri(A, B, R0); tri(C, Dd, R1); }
  if (GV.length) { const g2 = new THREE.BufferGeometry(); g2.setAttribute('position', new THREE.Float32BufferAttribute(GV, 3));
    const ex = Math.hypot(C[0] - Dd[0], C[1] - Dd[1]); g2.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, ex / 4, 0, ex / 8, (GV[7] - GV[1]) / 2.5], 2)); g2.computeVertexNormals(); roofG.add(new THREE.Mesh(g2, gableM)); }
  for (const [p, q] of [[a, b], [b, c], [c, d], [d, a]]) { const len = Math.hypot(q[0] - p[0], q[1] - p[1]); const f = new THREE.Mesh(new THREE.BoxGeometry(len, 0.7, 0.25), fasciaM); f.position.set((p[0] + q[0]) / 2, y0 - 0.35, (p[1] + q[1]) / 2); f.rotation.y = Math.atan2(-(q[1] - p[1]), q[0] - p[0]); roofG.add(f); }
  const gg = new THREE.BufferGeometry(); gg.setAttribute('position', new THREE.Float32BufferAttribute(V, 3));
  const UV = []; for (let i = 0; i < V.length; i += 3) UV.push(V[i] / 8, (V[i + 2] + V[i + 1]) / 8); gg.setAttribute('uv', new THREE.Float32BufferAttribute(UV, 2)); gg.computeVertexNormals();
  const m = new THREE.Mesh(gg, roofM); m.castShadow = true; roofG.add(m);
}
// porches, deck, pool
const porch = (P, mat) => {
  root.add(prism(P.pts, P.y - 0.4, P.y, new THREE.MeshLambertMaterial({ color: 0xb9b2a4 })));
  for (const p of P.pts) { const post = new THREE.Mesh(new THREE.BoxGeometry(0.85, P.h, 0.85), new THREE.MeshLambertMaterial({ color: 0xf6f3ec })); post.position.set(p[0], P.y + P.h / 2, p[1]); post.castShadow = true; root.add(post); }
  if (P.screened) for (let i = 0; i < P.pts.length; i++) {
    const p = P.pts[i], q = P.pts[(i + 1) % P.pts.length], len = Math.hypot(q[0] - p[0], q[1] - p[1]);
    const w = new THREE.Mesh(new THREE.BoxGeometry(len, P.h - 1, 0.05), new THREE.MeshLambertMaterial({ color: 0x334, transparent: true, opacity: .25 }));
    w.position.set((p[0] + q[0]) / 2, P.y + (P.h - 1) / 2 + 0.5, (p[1] + q[1]) / 2); w.rotation.y = Math.atan2(-(q[1] - p[1]), q[0] - p[0]); root.add(w);
  }
  const roof = new THREE.Mesh(shapeGeo(P.pts), new THREE.MeshLambertMaterial({ color: 0x6b6f75, side: THREE.DoubleSide })); roof.position.y = P.y + P.h; roof.castShadow = true; roofG.add(roof);
};
porch(E.screen); porch(E.summer);
const siteOnly = m => { m.userData.site = true; return m; };
if (E.deck) root.add(siteOnly(prism(E.deck.pts, E.deck.y - 0.5, E.deck.y, new THREE.MeshLambertMaterial({ color: 0xd9d4c7 }))));
root.add(siteOnly(prism(E.pool.pts, E.pool.y - 0.3, E.pool.y, new THREE.MeshLambertMaterial({ color: 0xe6e1d6 }))));
{ const c = E.pool.pts.reduce((s, p) => [s[0] + p[0] / 4, s[1] + p[1] / 4], [0, 0]);
  const inner = E.pool.pts.map(p => { const dx = p[0] - c[0], dz = p[1] - c[1], k = 1 - 1.3 / Math.hypot(dx, dz); return [c[0] + dx * k, c[1] + dz * k]; });
  const w = siteOnly(new THREE.Mesh(shapeGeo(inner), new THREE.MeshPhongMaterial({ color: 0x3aa0d8, shininess: 90 }))); w.position.y = E.pool.y + 0.02; root.add(w); }
// trees, shrubs, cypress and flowering shrubs (instanced; positions from the planting plan in plot feet)
const plantG = new THREE.Group(); root.add(plantG);
{
  const P = D.plants || [], by = k => P.filter(p => p[2] === k), M4 = new THREE.Matrix4(), Q = new THREE.Quaternion(), V = new THREE.Vector3(), Sc = new THREE.Vector3(), col = new THREE.Color();
  let seed = 11; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const inst = (geo, mat, list, place, tint) => { if (!list.length) return; const m = new THREE.InstancedMesh(geo, mat, list.length);
    list.forEach((p, i) => { place(p, i); M4.compose(V, Q, Sc); m.setMatrixAt(i, M4); if (tint) { tint(col, p, i); m.setColorAt(i, col); } });
    m.castShadow = true; m.receiveShadow = true; plantG.add(m); };
  const ground = (p) => hAt(p[0], p[1]);
  const trunkM = new THREE.MeshLambertMaterial({ color: 0x3b2f25 }), leafM = new THREE.MeshLambertMaterial({ color: 0x9a9a9a, flatShading: true });
  const trees = by('oak').concat(by('pine'));
  inst(new THREE.CylinderGeometry(0.35, 0.6, 1, 6), trunkM, trees, p => { Q.setFromAxisAngle(V.set(0, 1, 0), 0); const h = p[2] === 'pine' ? p[3] * 0.4 : p[3] * 0.45; V.set(p[0], ground(p) + h / 2, p[1]); Sc.set(1 + p[3] / 60, h, 1 + p[3] / 60); });
  const oaks = by('oak'), blobs = []; oaks.forEach(p => { for (let k = 0; k < 3; k++) blobs.push([p, k]); });
  inst(new THREE.IcosahedronGeometry(1, 1), leafM, blobs, ([p, k]) => { const r = p[4] * (k ? 0.72 : 1); Q.setFromAxisAngle(V.set(0, 1, 0), rnd() * 6);
      V.set(p[0] + (k ? (rnd() - 0.5) * p[4] : 0), ground(p) + p[3] * (k ? 0.6 + rnd() * 0.25 : 0.68), p[1] + (k ? (rnd() - 0.5) * p[4] : 0)); Sc.set(r, r * 0.8, r); },
    (c, [p, k]) => c.setHSL(0.25 + rnd() * 0.07, 0.42 + rnd() * 0.15, 0.13 + rnd() * 0.07));
  const pines = by('pine'), cones = []; pines.forEach(p => { for (let k = 0; k < 3; k++) cones.push([p, k]); });
  inst(new THREE.ConeGeometry(1, 1, 7), leafM, cones, ([p, k]) => { Q.identity(); const h = p[3] * (0.42 - k * 0.08), r = p[4] * (1 - k * 0.25);
      V.set(p[0], ground(p) + p[3] * (0.42 + k * 0.17) + h / 2, p[1]); Sc.set(r, h, r); }, c => c.setHSL(0.36 + rnd() * 0.04, 0.35, 0.1 + rnd() * 0.04));
  inst(new THREE.ConeGeometry(1, 1, 8), leafM, by('cypress'), p => { Q.identity(); V.set(p[0], ground(p) + p[3] / 2 + 0.3, p[1]); Sc.set(p[4], p[3], p[4]); }, c => c.setHSL(0.3, 0.38, 0.17));
  inst(new THREE.IcosahedronGeometry(1, 1), leafM, by('bush').concat(by('flower')), p => { Q.setFromAxisAngle(V.set(0, 1, 0), rnd() * 6); V.set(p[0], ground(p) + p[3] * 0.4, p[1]); Sc.set(p[4], p[3] * 0.55, p[4]); },
    (c, p) => p[2] === 'flower' ? c.setHSL(0.74 + rnd() * 0.04, 0.45, 0.55) : c.setHSL(0.27 + rnd() * 0.05, 0.45, 0.16 + rnd() * 0.05));
}
// VR viewpoints: front lawn, then the main rooms of each floor (feet; y = floor under the viewer)
const cen = pts => [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length];
const fc = cen(fp), spots = [{ name: 'Front lawn', x: fc[0] - 10, z: fc[1] + 75, y: hAt(fc[0] - 10, fc[1] + 75), yaw: 0 }];
const want = ['Foyer', 'Great Room', 'Kitchen', 'Casual Dining', "Owner's Suite", 'Porch', 'Bonus Room', 'Bedroom 3', 'Hall'];
D.levels.forEach(L => want.forEach(n => { const r = L.rooms.find(q => q.name === n); if (r) { const c = cen(r.pts); spots.push({ name: n, x: c[0], z: c[1], y: L.base - (r.drop || 0), yaw: 0 }); } }));
if (E.pool) { const c = cen(E.pool.pts); spots.push({ name: 'Pool', x: c[0] + 4, z: c[1] + 16, y: E.pool.y, yaw: 0 }); }
return { root, terrain, levelGroups, roofG, ceilG, plantG, setGround, hAt, inside, spots };
}

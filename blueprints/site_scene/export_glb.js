// Export the lot scene to glTF binaries for AR (metres, Y up, origin at the house).
// Usage: node export_glb.js <lot-page.html> <out-dir>
//   writes obsidian-house.glb (both floors, roof, foundation, porches) and obsidian-site.glb (+ terrain, landscape, pool)
// Meshes are merged per material (instances expanded) so phones get a handful of draw calls.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => {
  const [page, out] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(page)); await p.waitForFunction('window.__ready', null, { timeout: 60000 }); await p.waitForTimeout(1500);
  for (const u of ['https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/exporters/GLTFExporter.js',
                   'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/utils/BufferGeometryUtils.js']) await p.addScriptTag({ url: u });
  for (const kind of ['house', 'site']) {
    const b64 = await p.evaluate(async kind => {
      const L = LOT, E = D.extras, roots = [];
      L.levelGroups.forEach(g => roots.push(g)); roots.push(L.roofG);
      L.root.children.forEach(c => { if (c !== L.terrain && c !== L.plantG && c !== L.ceilG && !L.levelGroups.includes(c) && c !== L.roofG) roots.push(c); });
      if (kind === 'site') { roots.push(L.terrain, L.plantG); }
      L.root.updateMatrixWorld(true);
      const groups = new Map(), M = new THREE.Matrix4(), C = new THREE.Color();
      const add = (mesh, geo, mat, color) => {
        let g = geo.index ? geo.toNonIndexed() : geo.clone();
        for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
        if (!g.attributes.normal) g.computeVertexNormals();
        if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
        const n = g.attributes.position.count, col = new Float32Array(n * 3); for (let i = 0; i < n; i++) col.set([color.r, color.g, color.b], i * 3);
        g.setAttribute('color', new THREE.BufferAttribute(col, 3));
        g.groups = [];
        const key = mat.uuid; if (!groups.has(key)) groups.set(key, { mat, geos: [] }); groups.get(key).geos.push(g);
      };
      const visit = o => {
        if (!o.visible || (kind === 'house' && o.userData.site)) return;
        if (o.isInstancedMesh) {
          for (let i = 0; i < o.count; i++) { o.getMatrixAt(i, M); M.premultiply(o.matrixWorld); const g = o.geometry.clone(); g.applyMatrix4(M);
            if (o.instanceColor) C.fromArray(o.instanceColor.array, i * 3); else C.set(0xffffff); add(o, g, o.material, C.clone()); }
        } else if (o.isMesh) { const g = o.geometry.clone(); g.applyMatrix4(o.matrixWorld); add(o, g, o.material, new THREE.Color(1, 1, 1)); }
        o.children.forEach(visit);
      };
      roots.forEach(r => { const v = r.visible; r.visible = true; visit(r); r.visible = v; });
      // origin: footprint centre at finished-grade, metres
      const fp = E.foundation.pts, cx = fp.reduce((s, q) => s + q[0], 0) / fp.length, cz = fp.reduce((s, q) => s + q[1], 0) / fp.length;
      const y0 = kind === 'house' ? E.foundation.bottom : L.hAt(cx, cz);
      const inner = new THREE.Group(); inner.position.set(-cx, -y0, -cz);
      const out = new THREE.Group(); out.add(inner); out.scale.setScalar(0.3048); out.rotation.y = D.fit.rot * Math.PI / 180;   // undo the lot rotation: plan axes, front toward +z
      let tris = 0;
      for (const { mat, geos } of groups.values()) {
        const merged = THREE.BufferGeometryUtils.mergeBufferGeometries(geos, false); if (!merged) continue;
        tris += merged.attributes.position.count / 3;
        const m = new THREE.MeshStandardMaterial({ color: mat.color ? mat.color.clone() : 0xffffff, map: mat.map || null, transparent: !!mat.transparent, opacity: mat.opacity ?? 1,
          side: mat.side, roughness: mat.roughness ?? 0.88, metalness: mat.metalness ?? 0, vertexColors: true });
        inner.add(new THREE.Mesh(merged, m));
      }
      const wrap = new THREE.Scene(); wrap.add(out);
      const buf = await new Promise(res => new THREE.GLTFExporter().parse(wrap, res, { binary: true, maxTextureSize: 2048 }));
      let s = ''; const u8 = new Uint8Array(buf); for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
      console.log(kind, 'materials', groups.size, 'triangles', Math.round(tris));
      return btoa(s);
    }, kind);
    const f = path.join(out, `obsidian-${kind}.glb`); fs.writeFileSync(f, Buffer.from(b64, 'base64'));
    console.log(f, (fs.statSync(f).size / 1e6).toFixed(1), 'MB');
  }
  if (errs.length) console.log('errors', errs);
  await b.close();
})();

/* Interior Studio "Site" layer: puts the lot (plot plan on contour terrain), foundation, the other floor,
   roofs, porches and pool around the floor being edited, so the full designer and the lot scene are one view.
   Data + builder come from build_lot_scene.py's site.js (window.LOT_SITE + buildLotScene), loaded on first use
   from SITE_DATA_URL next to the Studio page. Runs inside the Studio page: uses its globals
   (scene, WALLS, view, setView, groundMesh, persp, orbitGoal, toast). */
(function () {
  const SITE_DATA_URL = 'obsidian/lot2-site-data.js';
  let on = false, S = null, panel = null;
  const opt = { lot: true, other: true, roof: true };

  function levelIndex(D) {   // which surveyed level the Studio is showing (0 first, 1 second, -1 other plan)
    const mine = [WALLS.length].concat(WALLS.slice(0, 4).flatMap(w => [w.x1, w.z1, w.x2, w.z2]));
    return D.sig.findIndex(s => s.length === mine.length && s.every((v, i) => Math.abs(v - mine[i]) < 0.02));
  }
  function load() {
    return new Promise((res, rej) => {
      if (window.LOT_SITE) return res(window.LOT_SITE);
      const s = document.createElement('script'); s.src = SITE_DATA_URL;
      s.onload = () => res(window.LOT_SITE); s.onerror = () => rej(new Error('no site data')); document.head.append(s);
    });
  }
  function build(D) {
    const lv = levelIndex(D);
    if (lv < 0) return null;
    const L = buildLotScene(D), f = D.fit, sh = lv ? D.shift2 : [0, 0];
    L.levelGroups[lv].visible = false;             // the Studio draws this floor itself, furnished and editable
    L.ceilG.visible = false;
    // plot feet -> this plan's feet: inverse of the footprint fit (and the 2nd-floor registration shift)
    L.root.position.set(-(f.pc[0] + f.dx), 0, -(f.pc[1] + f.dy));
    const outer = new THREE.Group(); outer.add(L.root);
    outer.rotation.y = f.rot * Math.PI / 180;
    outer.position.set(f.mc[0] - sh[0], -D.levels[lv].base, f.mc[1] - sh[1]);
    outer.traverse(o => { if (o.isMesh) o.receiveShadow = true; });
    scene.add(outer);
    return { outer, L, lv };
  }
  function apply() {
    if (!S) return;
    const plan = view === 'plan';
    S.outer.visible = on;
    S.L.terrain.visible = opt.lot;
    S.L.levelGroups[1 - S.lv].visible = opt.other && !plan;
    S.L.roofG.visible = opt.roof && !plan;
    groundMesh.visible = on ? false : view === 'orbit';
    window.__maxDist = on ? 420 : 110;
    persp.far = on ? 3000 : 500; persp.updateProjectionMatrix();
    // room labels float above the roof: show them only when the roof is off
    const lb = document.getElementById('labels'); if (lb) lb.style.display = (view === 'walk' || !labelsOn || (on && opt.roof && !plan)) ? 'none' : '';
    if (panel) panel.style.display = on ? '' : 'none';
    const b = document.getElementById('tb-site'); if (b) b.classList.toggle('on', on);
  }
  function makePanel(D) {
    panel = document.createElement('div');
    panel.style.cssText = 'position:absolute;right:12px;bottom:12px;z-index:30;background:rgba(255,255,255,.95);border:1px solid #cbd5e1;border-radius:12px;padding:10px 12px;font:12px system-ui;color:#0f172a;max-width:270px;box-shadow:0 4px 16px rgba(0,0,0,.12)';
    const other = S.lv ? '1st floor' : '2nd floor';
    panel.innerHTML = `<b>Lot 2 site</b><div style="color:#64748b;margin:2px 0 6px">Plot plan on contour terrain (finished floor ${D.ffe}'). You are editing the ${S.lv ? '2nd' : '1st'} floor.</div>` +
      [['lot', 'Lot &amp; terrain'], ['other', other], ['roof', 'Roof &amp; porches']].map(([k, t]) =>
        `<label style="display:flex;gap:6px;align-items:center;margin:3px 0"><input type="checkbox" data-k="${k}" ${opt[k] ? 'checked' : ''}>${t}</label>`).join('') +
      `<button data-act="aerial" style="margin-top:6px;padding:4px 10px;border:1px solid #2a5b8a;border-radius:8px;color:#2a5b8a;background:#fff">Aerial view</button>`;
    panel.addEventListener('change', e => { const k = e.target.dataset.k; if (k) { opt[k] = e.target.checked; apply(); } });
    panel.querySelector('[data-act=aerial]').onclick = () => { if (view !== 'orbit') setView('orbit'); Object.assign(orbitGoal, { dist: 260, pitch: 0.6 }); };
    (document.getElementById('canvas-container') || document.body).append(panel);
  }
  window.toggleSite = async function () {
    if (!S) {
      let D; try { D = await load(); } catch (e) { toast('Site data not found next to this page'); return; }
      S = build(D);
      if (!S) { toast('The Site layer is for the Obsidian 1899F first and second floors'); return; }
      makePanel(D);
    }
    on = !on; apply();
    if (on) { if (view === 'walk') setView('orbit'); Object.assign(orbitGoal, { dist: 230, pitch: 0.6 }); toast('Site on: lot, terrain, roof and the other floor'); }
  };
  // VR: walk your furnished floor at true scale; with the site on, step outside onto the lot
  let XRH = null;
  function vrSpots() {
    const out = [];
    if (S && on) {
      const lot = S.L.spots, w = p => S.L.root.localToWorld(new THREE.Vector3(p.x, p.y, p.z));
      for (const p of [lot[0], lot[lot.length - 1]]) { const v = w(p); out.push({ name: p.name, x: v.x, y: v.y, z: v.z, yaw: p.yaw + S.outer.rotation.y }); }
    }
    for (const f of FOCUS) {
      const v = WALK_VIEWS[f.id]; if (!v || f.id === 'home') continue;
      out.push({ name: f.name, x: v.p[0], y: 0, z: v.p[1], yaw: Math.atan2(-(v.t[0] - v.p[0]), -(v.t[1] - v.p[1])) });
    }
    return out;
  }
  function floorAt(x, z) {
    if (typeof roomAt === 'function' && roomAt(x, z)) return 0;
    if (!S || !on) return null;
    const q = S.L.root.worldToLocal(new THREE.Vector3(x, 0, z));
    if (S.L.inside(q.x, q.z)) return null;
    return S.L.root.localToWorld(new THREE.Vector3(q.x, S.L.hAt(q.x, q.z), q.z)).y;
  }
  window.enterVR = function () {
    if (!XRH) {
      const b = document.getElementById('tb-vr');
      XRH = addXR({ renderer, scene, spots: vrSpots, floorAt: (x, z) => floorAt(x, z), button: b,
        onStart: () => { if (view !== 'walk') setView('walk'); if (S) { S.L.roofG.visible = opt.roof; } },
        onSpot: p => toast('VR: ' + p.name), compact: true,
        onUnsupported: () => toast('VR needs a headset browser: open this page in the Meta Quest Browser (or Chrome/Edge with a PC VR headset)') });
    }
  };
  addEventListener('load', () => { const b = document.getElementById('tb-vr'); if (b && typeof addXR === 'function') { window.enterVR(); } });
  const sv = window.setView;
  window.setView = function (v) { sv(v); apply(); };
  if (new URLSearchParams(location.search).get('site') === '1') addEventListener('load', () => setTimeout(window.toggleSite, 300));
})();

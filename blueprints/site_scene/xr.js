/* WebXR for the lot scene and Interior Studio: true-scale VR walkthrough (scene units are feet).
   addXR({ renderer, scene, spots, frame, onStart, onEnd, button }) adds an "Enter VR" button when the
   browser supports immersive-vr (Quest Browser, PC VR via Chrome/Edge). spots: [{name, x, y, z, yaw}] in feet
   (y = floor height under the viewer). Controls: left stick walks where you look, right stick snap-turns,
   trigger / pinch jumps to the next spot, grip jumps back. */
function addXR(o) {
  const { renderer, scene } = o, FT = 1 / 0.3048;
  const rig = new THREE.Group(), cam = new THREE.PerspectiveCamera(70, 1, 0.05, 6000);
  rig.add(cam); rig.scale.setScalar(FT); scene.add(rig);
  let session = null, spot = 0, turnLock = false, last = 0;
  const spots = () => (typeof o.spots === 'function' ? o.spots() : o.spots) || [];
  function go(i) { const s = spots(); if (!s.length) return; spot = (i + s.length) % s.length; const p = s[spot];
    rig.position.set(p.x, p.y, p.z); rig.rotation.set(0, p.yaw || 0, 0); if (o.onSpot) o.onSpot(p); }
  const btn = o.button || document.createElement('button');
  const label = (on) => o.compact ? (on ? 'Exit VR' : 'VR') : (on ? 'Exit VR' : 'Enter VR');
  let supported = false;
  btn.textContent = label(false); btn.title = 'Walk through at true scale in VR (Meta Quest Browser, or Chrome/Edge with a PC VR headset)';
  if (!o.button) { btn.style.cssText = 'position:absolute;right:12px;top:12px;z-index:40;padding:9px 14px;border-radius:10px;border:1px solid #2a5b8a;background:#2a5b8a;color:#fff;font:600 13px system-ui;cursor:pointer;opacity:.5'; document.body.append(btn); }
  const unsupported = () => { if (!o.compact) btn.textContent = 'VR: open on a headset'; btn.style.opacity = 0.55; };
  if (navigator.xr) navigator.xr.isSessionSupported('immersive-vr').then(ok => { supported = ok; if (ok) btn.style.opacity = 1; else unsupported(); }).catch(unsupported);
  else unsupported();
  btn.onclick = async () => {
    if (session) return session.end();
    if (!supported) { if (o.onUnsupported) o.onUnsupported(); return; }
    session = await navigator.xr.requestSession('immersive-vr', { optionalFeatures: ['local-floor', 'bounded-floor', 'hand-tracking'] });
    renderer.xr.enabled = true; renderer.xr.setReferenceSpaceType('local-floor'); await renderer.xr.setSession(session);
    btn.textContent = label(true); go(spot); if (o.onStart) o.onStart();
    session.addEventListener('select', () => go(spot + 1));
    session.addEventListener('squeeze', () => go(spot - 1));
    session.addEventListener('end', () => { session = null; btn.textContent = label(false); renderer.setAnimationLoop(null); renderer.xr.enabled = false; if (o.onEnd) o.onEnd(); });
    last = performance.now();
    renderer.setAnimationLoop((t, xf) => {
      const dt = Math.min(0.1, (t - last) / 1000); last = t;
      for (const src of session.inputSources) {
        const ax = src.gamepad && src.gamepad.axes; if (!ax || ax.length < 4) continue;
        const sx = ax[2], sy = ax[3];
        if (src.handedness === 'left' && Math.hypot(sx, sy) > 0.15) {   // walk where the head looks, 4.5 ft/s
          const xc = renderer.xr.getCamera(cam), d = new THREE.Vector3(); xc.getWorldDirection(d); d.y = 0; d.normalize();
          const r = new THREE.Vector3(-d.z, 0, d.x), v = 4.5 * dt;
          rig.position.addScaledVector(d, -sy * v).addScaledVector(r, sx * v);
          if (o.floorAt) { const y = o.floorAt(rig.position.x, rig.position.z, rig.position.y); if (y != null) rig.position.y = y; }
        }
        if (src.handedness === 'right') { if (Math.abs(sx) > 0.7 && !turnLock) { rig.rotation.y -= Math.sign(sx) * Math.PI / 6; turnLock = true; } else if (Math.abs(sx) < 0.3) turnLock = false; }
      }
      if (o.frame) o.frame(dt);
      renderer.render(scene, cam);
    });
  };
  return { rig, cam, go, button: btn };
}

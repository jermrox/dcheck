// Load generated .home.json files into the Interior Design Visualizer and check them in the real app.
// Usage: node test_in_visualizer.js <visualizer_url> <out_dir> <home.json> [...]
//   visualizer_url  e.g. http://localhost:8790/interactive_interior_visualizer.html (serve a local clone)
// Per home: console errors, starter furniture placed, furniture clashing with walls or other items (the app's own
// collisions() check), and screenshots of the 3D and walk views.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [url, out, ...files] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const results = [];
  for (const f of files) {
    const home = JSON.parse(fs.readFileSync(f, 'utf8')), plan = home.plan, id = plan.id;
    const ctx = await b.newContext({ viewport: { width: 1400, height: 880 } }), p = await ctx.newPage(), errs = [];
    p.on('pageerror', e => errs.push(String(e.message).slice(0, 200)));
    p.on('console', m => { if (m.type() === 'error' && !/favicon|ERR_|net::/.test(m.text())) errs.push(m.text().slice(0, 200)); });
    await p.goto(url); await p.waitForTimeout(1500);
    await p.evaluate(([plan, id]) => {
      localStorage.setItem('interior-studio-plan-' + id, JSON.stringify(plan));
      localStorage.setItem('interior-studio-projects-v1', JSON.stringify([{ id, name: plan.name, sub: plan.sub }]));
      localStorage.setItem('interior-studio-active-v1', JSON.stringify(id));
    }, [plan, id]);
    await p.reload(); await p.waitForTimeout(5000);
    const r = await p.evaluate(`(() => {
      const items = state.items || [];
      const clashes = items.map(it => ({ name: it.name, room: (typeof roomAt === 'function' ? roomAt(it.x, it.z) : null), hits: collisions(it) })).filter(x => x.hits.length);
      return { open: PLAN && PLAN.id, name: PLAN && PLAN.name, rooms: PLAN.rooms.length, walls: PLAN.walls.length, items: items.length,
               clashing: clashes.length, clashes: clashes.slice(0, 8).map(c => c.name + ' in ' + c.room + ' hits ' + c.hits.join(', ')) };
    })()`);
    const slug = path.basename(f).replace('.home.json', '');
    await p.screenshot({ path: path.join(out, slug + '-3d.png') });
    await p.evaluate(`setView('plan')`); await p.waitForTimeout(1200); await p.screenshot({ path: path.join(out, slug + '-plan.png') });
    await p.evaluate(`setView('walk')`); await p.waitForTimeout(1800); await p.screenshot({ path: path.join(out, slug + '-walk.png') });
    r.file = path.basename(f); r.errors = errs.slice(0, 5); results.push(r);
    await ctx.close();
  }
  fs.writeFileSync(path.join(out, 'app_check.json'), JSON.stringify(results, null, 1));
  console.log(JSON.stringify(results, null, 1));
  await b.close();
})();

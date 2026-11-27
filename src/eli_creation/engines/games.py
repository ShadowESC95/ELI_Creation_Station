"""Games: a design becomes a game you can play in a browser now, and (planned) in ELI VR.

The design's kinds are ELI v3's (eli/world/games.py: targets, catch, sort, order, hide, range), the
ones ELI VR already plays (scripts/eli/eli_play.gd there), so a design made here can later be set
in ELI's rooms unchanged. The browser export plays ``targets`` and ``catch`` today.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from eli_creation.engines.base import Engine, Progress
from eli_creation.library import slug
from eli_creation.provenance import manifest as manifests

if TYPE_CHECKING:
    from eli_creation.jobs import Job
    from eli_creation.services import Studio

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="ELI Creation Station"><title>{title}</title>
<style>html,body{{margin:0;height:100%;background:{bg};color:#fff;font:16px system-ui,sans-serif;overflow:hidden}}
canvas{{display:block;width:100vw;height:100vh;touch-action:none}}#hud{{position:fixed;top:12px;left:16px;right:16px;display:flex;justify-content:space-between}}
#msg{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;background:#0008}}
button{{font:inherit;padding:10px 22px;border-radius:8px;border:0;background:{accent};color:#111;cursor:pointer}}</style></head>
<body><canvas id="c"></canvas><div id="hud"><span id="score">0</span><span id="time"></span></div>
<div id="msg"><h1>{title}</h1><p>{goal}</p><button id="go">Play</button></div>
<script>
// A game made with ELI Creation Station. Kind: {kind}. Its design: {design_name}.
const SPEC = {spec};
const cv = document.getElementById('c'), cx = cv.getContext('2d');
let W, H, pieces = [], score = 0, misses = 0, left = 0, last = 0, running = false, px = 0.5;
const colours = (SPEC.palette && SPEC.palette.length) ? SPEC.palette : ['{accent}', '#ffffff', '#ffcc33'];
function size() {{ W = cv.width = innerWidth * devicePixelRatio; H = cv.height = innerHeight * devicePixelRatio; }}
addEventListener('resize', size); size();
function spawn() {{
  const r = Math.min(W, H) * 0.035;
  if (SPEC.kind === 'catch') pieces.push({{x: r + Math.random() * (W - 2 * r), y: -r, r, vy: H * (0.25 + Math.random() * 0.2), c: colours[pieces.length % colours.length]}});
  else pieces.push({{x: r + Math.random() * (W - 2 * r), y: r * 3 + Math.random() * (H - r * 6), r, life: 1.6, c: colours[pieces.length % colours.length]}});
}}
function hit(x, y) {{
  for (const p of pieces) if (Math.hypot(p.x - x, p.y - y) < p.r * 1.4) {{ p.dead = true; score++; return; }}
}}
cv.addEventListener('pointerdown', e => {{ if (running && SPEC.kind !== 'catch') hit(e.clientX * devicePixelRatio, e.clientY * devicePixelRatio); }});
cv.addEventListener('pointermove', e => {{ px = e.clientX / innerWidth; }});
addEventListener('keydown', e => {{ if (e.key === 'ArrowLeft') px = Math.max(0, px - 0.05); if (e.key === 'ArrowRight') px = Math.min(1, px + 0.05); }});
function frame(t) {{
  if (!running) return;
  const dt = Math.min(0.05, (t - last) / 1000 || 0); last = t; left -= dt;
  if (Math.random() < dt * (SPEC.pieces || 12) / 10) spawn();
  cx.clearRect(0, 0, W, H);
  const bw = W * 0.16, bx = px * (W - bw), by = H * 0.92;
  if (SPEC.kind === 'catch') {{ cx.fillStyle = '#fff'; cx.fillRect(bx, by, bw, H * 0.02); }}
  for (const p of pieces) {{
    if (SPEC.kind === 'catch') {{
      p.y += p.vy * dt;
      if (p.y > by - p.r && p.y < by + p.r && p.x > bx && p.x < bx + bw) {{ p.dead = true; score++; }}
      else if (p.y > H + p.r) {{ p.dead = true; misses++; }}
    }} else {{ p.life -= dt; if (p.life <= 0) {{ p.dead = true; misses++; }} }}
    cx.beginPath(); cx.arc(p.x, p.y, p.r, 0, Math.PI * 2); cx.fillStyle = p.c; cx.fill();
  }}
  pieces = pieces.filter(p => !p.dead);
  document.getElementById('score').textContent = 'Score ' + score + '   Missed ' + misses;
  document.getElementById('time').textContent = Math.max(0, Math.ceil(left)) + ' s';
  if (left <= 0) {{ running = false; const m = document.getElementById('msg'); m.style.display = 'flex';
    m.querySelector('p').textContent = 'You scored ' + score + '. Missed ' + misses + '.'; m.querySelector('button').textContent = 'Again'; return; }}
  requestAnimationFrame(frame);
}}
document.getElementById('go').onclick = () => {{ pieces = []; score = 0; misses = 0; left = SPEC.seconds || 45; running = true;
  document.getElementById('msg').style.display = 'none'; last = performance.now(); requestAnimationFrame(frame); }};
</script></body></html>
"""


class BrowserGame(Engine):
    id = "games.browser"
    tab = "games"
    title = "Play it in a browser"
    summary = "A design becomes one HTML file anyone can open and play: on a site, itch.io, or a phone."

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        r = job.request
        design_path = Path(str(r.get("design", "")))
        spec: dict[str, Any] = json.loads(design_path.read_text(encoding="utf-8"))
        kind = spec.get("kind") if spec.get("kind") in ("targets", "catch") else "catch"
        spec["kind"] = kind
        palette = [c for c in spec.get("palette", []) if isinstance(c, str) and c.startswith("#")] or ["#63ddff"]
        progress(0.5, "Building the page")
        page = _PAGE.format(
            title=_escape(str(spec.get("title", "A game"))), goal=_escape(str(spec.get("goal", ""))), kind=kind,
            spec=json.dumps({k: spec.get(k) for k in ("kind", "seconds", "pieces", "palette")}),
            bg="#10151e", accent=palette[0], design_name=_escape(design_path.name))
        folder = studio.library.folder("game", r.get("project", ""))
        target = folder / f"{slug(str(spec.get('title', 'game')))}-{job.id}.html"
        target.write_text(page, encoding="utf-8")
        man = manifests.build(kind="game", engine=self.id, models=[], request={"kind": kind},
                              digital_source_type=None, sources=[design_path.name], project=r.get("project", ""))
        job.assets.append(studio.library.add(target, manifest=man, title=str(spec.get("title", "game")), job=job.id))


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

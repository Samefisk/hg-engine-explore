"""Review page for a map: look, click a spot, record what looks wrong.

  python3 -B -m tools.maps.review --map 543 [--port 8765] [--vanilla]

Serves http://127.0.0.1:PORT/ (local only). The page shows the offline render
(tools.maps.render) of the whole map from the field camera's pitch, or from
above, with overlays: the judge's tile problems from the generate report
(style/edit.py analysis), the render's void check, report hotspots and open
lab defects. Clicking a spot shows the game's view standing there, the tile
inspection (`tools.maps.style inspect`) and the commands to inspect or
re-solve around it. "Record defect" appends to the lab's defects.jsonl (the
same as `tools.maps.style.lab defect add`). "Reload" re-reads data/maps/
after a generate or resolve.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import render

REPO = render.REPO


def _png(image: np.ndarray) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(image).save(buf, "PNG")
    return buf.getvalue()


class Review:
    """Everything the page shows for one map, rebuilt on reload."""

    def __init__(self, map_id: int, overrides: Path | None):
        self.map_id, self.overrides = map_id, overrides
        self.lock = threading.Lock()
        self.load()

    def load(self) -> None:
        """Build everything first and swap it in at once: a failed reload keeps the old page working."""
        scene = render.MapScene(self.map_id, self.overrides)
        views = {}
        for name, top in (("oblique", False), ("top", True)):
            image, cam, where = scene.overview(8, top=top, pick=True)
            views[name] = {"png": _png(image), "camera": cam, "where": where,
                           "size": [int(image.shape[1]), int(image.shape[0])]}
        voids = render.voids(scene)
        # The judge's view comes from the generate reports and data/maps (edit.py); a vanilla
        # render has no report to show.
        problems, hotspots = ({}, []) if self.overrides is None else self._problems(scene)
        self.scene, self.views, self.voids, self.problems, self.hotspots = scene, views, voids, problems, hotspots

    def _problems(self, scene) -> tuple[dict, list]:
        """{(x, z): marker} from each generate report's analysis, and hotspots in map tiles."""
        from .style import edit
        problems, hotspots, seen = {}, [], set()
        for cx, cz in scene.own_chunks():
            try:
                path, report, gx0, gz0 = edit.map_to_grid(self.map_id, cx * 32, cz * 32)
            except edit.EditError:
                continue
            _, a = edit._report_analysis(path, report, report.get("layout"))
            for lz in range(32):
                for lx in range(32):
                    marker = edit._marker(a, gx0 + lx, gz0 + lz)
                    if marker != ".":
                        problems[(cx * 32 + lx, cz * 32 + lz)] = marker
            if path not in seen:
                seen.add(path)
                ox, oz = cx * 32 - gx0, cz * 32 - gz0
                for h in report.get("hotspots", []):
                    hotspots.append({"x": [h["x"][0] + ox, h["x"][1] + ox], "z": [h["z"][0] + oz, h["z"][1] + oz],
                                     "problems": h["problems"]})
        return problems, hotspots

    def screen(self, view: str, x: int, z: int):
        return self.views[view]["camera"].screen_of(self.scene.tile_world(x, z))

    def state(self) -> dict:
        from .style import lab
        out = {"map": self.map_id, "vanilla": self.overrides is None, "views": {}}
        defects = [d for d in lab._read_jsonl(lab.DEFECTS) if d["map"] == self.map_id and d["status"] == "open"]
        for name, v in self.views.items():
            def at(x, z, name=name):
                p = self.screen(name, x, z)
                return None if p is None else [round(p[0], 1), round(p[1], 1)]
            out["views"][name] = {
                "size": v["size"],
                "problems": [[*at(x, z), m] for (x, z), m in sorted(self.problems.items()) if at(x, z)],
                "voidTop": [at(x, z) for x, z in self.voids["top"] if at(x, z)],
                "voidCamera": [at(x, z) for x, z in self.voids["camera"] if at(x, z)],
                "hotspots": [{"from": at(h["x"][0], h["z"][0]), "to": at(h["x"][1] + 1, h["z"][1] + 1),
                              "problems": h["problems"]} for h in self.hotspots],
                "defects": [{"at": at(d["x"], d["z"]), "id": d["id"], "note": d["note"]} for d in defects],
            }
        out["counts"] = {"problems": len(self.problems), "voidTop": len(self.voids["top"]),
                         "voidCamera": len(self.voids["camera"]), "openDefects": len(defects)}
        return out

    def pick(self, view: str, px: float, py: float) -> tuple[int, int] | None:
        where = self.views[view]["where"]
        h, w = where.shape[:2]
        x, y = int(px), int(py)
        # nearest drawn pixel within 5: a click on the void still finds the tile beside it
        y0, x0 = max(0, y - 5), max(0, x - 5)
        block = where[y0:min(h, y + 6), x0:min(w, x + 6)]
        ok = np.argwhere(~np.isnan(block[..., 0]))
        if not len(ok):
            return None
        iy, ix = min(ok, key=lambda p: (p[0] + y0 - y) ** 2 + (p[1] + x0 - x) ** 2)
        wx, wz = block[iy, ix]
        return int(wx // render.TILE), int(wz // render.TILE)

    def tile(self, x: int, z: int) -> dict:
        from .style import edit
        try:
            info = edit.inspect_tile(self.map_id, x, z, radius=2)
        except Exception as error:  # noqa: BLE001 - shown on the page
            info = {"error": str(error)}
        if self.overrides is None:
            info["note"] = "vanilla render; this inspection reads data/maps"
        info["renderVoid"] = {"top": (x, z) in set(self.voids["top"]),
                              "camera": (x, z) in set(self.voids["camera"])}
        x0, z0 = max(0, x - 4), max(0, z - 4)
        info["commands"] = [
            f"python3 -B -m tools.maps.style inspect --map {self.map_id} --x {x} --z {z} --radius 2",
            f"python3 -B -m tools.maps.style resolve --map {self.map_id} --region {x0} {z0} 8 8 --seeds 4",
            f"python3 -B -m tools.maps.render view --map {self.map_id} --at {x} {z}",
        ]
        return info


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Map review</title>
<style>
body{margin:0;font:13px system-ui,sans-serif;background:#1d1f23;color:#ddd;display:flex;height:100vh}
#left{flex:1;overflow:auto;position:relative}
#wrap{position:relative;display:inline-block;margin:8px}
#wrap img,#wrap canvas{position:absolute;left:0;top:0;image-rendering:pixelated}
#side{width:420px;overflow:auto;border-left:1px solid #333;padding:10px;box-sizing:border-box}
button,label{margin:2px 4px 2px 0}
pre{white-space:pre-wrap;background:#111;padding:6px;font-size:11px;max-height:340px;overflow:auto}
code{display:block;background:#111;padding:3px;margin:2px 0;font-size:11px;user-select:all}
textarea{width:100%;height:60px;background:#111;color:#ddd}
#game{width:384px;image-rendering:pixelated;border:1px solid #444;display:block}
.k{display:inline-block;width:10px;height:10px;margin-right:3px}
</style></head><body>
<div id="left"><div id="bar" style="padding:8px">
 <button data-v="oblique">Game angle</button><button data-v="top">From above</button>
 <label><input type="checkbox" id="lp" checked>judge problems</label>
 <label><input type="checkbox" id="lv" checked>render void</label>
 <label><input type="checkbox" id="lh" checked>hotspots</label>
 <label><input type="checkbox" id="ld" checked>defects</label>
 zoom <select id="zoom"><option>1</option><option selected>2</option><option>3</option></select>
 <button id="reload">Reload</button> <span id="counts"></span>
 <div style="margin-top:4px;font-size:11px">
 <span class="k" style="background:#f33"></span>route/overhang/hole/void
 <span class="k" style="background:#fd3"></span>bad join
 <span class="k" style="background:#f3f"></span>render: void visible
 <span class="k" style="background:#3cf"></span>hotspot
 <span class="k" style="background:#fff"></span>open defect</div></div>
 <div id="wrap"><img id="img"><canvas id="ov"></canvas></div></div>
<div id="side"><div id="hint">Click the map to inspect a spot.</div>
 <div id="tile" style="display:none">
  <h3 id="title"></h3><img id="game">
  <p>What looks wrong here?</p><textarea id="note"></textarea>
  <button id="save">Record defect</button> <span id="saved"></span>
  <h4>Commands</h4><div id="cmds"></div>
  <h4>Inspection</h4><pre id="info"></pre></div></div>
<script>
let state=null, view='oblique', sel=null;
const img=document.getElementById('img'), ov=document.getElementById('ov'), wrap=document.getElementById('wrap');
const z=()=>+document.getElementById('zoom').value;
async function load(){ state=await (await fetch('/api/state')).json(); show(); }
function show(){
  const v=state.views[view], k=z();
  img.src='/overview.png?view='+view+'&t='+Date.now();
  img.width=v.size[0]*k; img.height=v.size[1]*k; ov.width=v.size[0]*k; ov.height=v.size[1]*k;
  wrap.style.width=img.width+'px'; wrap.style.height=img.height+'px';
  const c=state.counts;
  document.getElementById('counts').textContent=`map ${state.map}${state.vanilla?' (vanilla)':''}: ${c.problems} judge problems, render void ${c.voidTop} from above / ${c.voidCamera} at game angle, ${c.openDefects} open defects`;
  draw();
}
function draw(){
  const v=state.views[view], k=z(), g=ov.getContext('2d'); g.clearRect(0,0,ov.width,ov.height);
  const dot=(p,col,r)=>{g.fillStyle=col;g.fillRect(p[0]*k-r,p[1]*k-r,2*r,2*r);};
  if(document.getElementById('lh').checked){g.strokeStyle='#3cf';g.lineWidth=2;
    for(const h of v.hotspots){ if(!h.from||!h.to)continue; g.strokeRect(h.from[0]*k,h.from[1]*k,(h.to[0]-h.from[0])*k,(h.to[1]-h.from[1])*k);} }
  if(document.getElementById('lp').checked) for(const p of v.problems) dot(p, p[2]=='S'?'rgba(255,220,50,.8)':'rgba(255,50,50,.9)', p[2]=='S'?1.5*k/2+1:2*k/2+1.5);
  if(document.getElementById('lv').checked){ for(const p of v.voidCamera) dot(p,'rgba(255,60,255,.85)',k+1); for(const p of v.voidTop) dot(p,'rgba(255,60,255,.85)',k+2); }
  if(document.getElementById('ld').checked){ g.strokeStyle='#fff'; g.fillStyle='#fff'; g.font='12px sans-serif';
    for(const d of v.defects){ if(!d.at)continue; g.beginPath(); g.arc(d.at[0]*k,d.at[1]*k,8,0,7); g.stroke(); g.fillText(d.id,d.at[0]*k+10,d.at[1]*k+4);} }
  if(sel&&sel.at){ g.strokeStyle='#0f0'; g.lineWidth=2; g.beginPath(); g.arc(sel.at[0]*k,sel.at[1]*k,6,0,7); g.stroke(); }
}
ov.addEventListener('click', async e=>{
  const r=ov.getBoundingClientRect(), k=z();
  const px=(e.clientX-r.left)/k, py=(e.clientY-r.top)/k;
  const t=await (await fetch(`/api/pick?view=${view}&px=${px}&py=${py}`)).json();
  if(!t.tile){ document.getElementById('hint').textContent='No map tile there.'; return; }
  sel={x:t.tile[0], z:t.tile[1], at:t.at}; draw();
  document.getElementById('tile').style.display='block'; document.getElementById('hint').textContent='';
  document.getElementById('title').textContent=`Map ${state.map}, tile (${sel.x}, ${sel.z})`;
  document.getElementById('game').src=`/view.png?x=${sel.x}&z=${sel.z}`;
  document.getElementById('info').textContent=JSON.stringify(t.info,null,1);
  document.getElementById('cmds').innerHTML=t.info.commands.map(c=>'<code></code>').join('');
  [...document.querySelectorAll('#cmds code')].forEach((el,i)=>el.textContent=t.info.commands[i]);
  document.getElementById('saved').textContent='';
});
document.getElementById('save').onclick=async()=>{
  const note=document.getElementById('note').value.trim(); if(!sel||!note) return;
  const res=await (await fetch('/api/defect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({x:sel.x,z:sel.z,note})})).json();
  document.getElementById('saved').textContent=res.id?('saved as '+res.id):('error: '+res.error);
  document.getElementById('note').value=''; await load();
};
document.getElementById('reload').onclick=async()=>{ document.getElementById('counts').textContent='reloading...'; await fetch('/api/reload',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); await load(); };
document.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>{view=b.dataset.v; sel=null; show();});
['lp','lv','lh','ld'].forEach(id=>document.getElementById(id).onchange=draw);
document.getElementById('zoom').onchange=show;
load();
</script></body></html>"""


MAX_BODY = 4096


def make_handler(review: Review):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _local(self) -> bool:
            """Only this page may call the API: another site open in the browser can reach
            127.0.0.1 too, but not with our Host and a JSON body (that needs a preflight)."""
            port = self.server.server_address[1]
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _send(self, body: bytes, kind: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, code: int = 200):
            self._send(json.dumps(data).encode(), "application/json", code)

        def do_GET(self):
            if not self._local():
                return self._json({"error": "bad host"}, 403)
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                with review.lock:
                    if url.path == "/":
                        return self._send(PAGE.encode(), "text/html; charset=utf-8")
                    if url.path == "/api/state":
                        return self._json(review.state())
                    if url.path == "/overview.png":
                        return self._send(review.views[q.get("view", "oblique")]["png"], "image/png")
                    if url.path == "/view.png":
                        image = review.scene.view(int(q["x"]), int(q["z"]), scale=2)
                        return self._send(_png(image), "image/png")
                    if url.path == "/api/pick":
                        view = q.get("view", "oblique")
                        tile = review.pick(view, float(q["px"]), float(q["py"]))
                        if tile is None:
                            return self._json({"tile": None})
                        at = review.screen(view, *tile)
                        return self._json({"tile": tile, "at": at, "info": review.tile(*tile)})
            except Exception as error:  # noqa: BLE001 - report to the page
                return self._json({"error": str(error)}, 500)
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            if (not self._local() or self.headers.get("Content-Type", "").split(";")[0] != "application/json"
                    or not 0 <= length <= MAX_BODY):
                return self._json({"error": "rejected"}, 403)
            url = urlparse(self.path)
            body = self.rfile.read(length)
            try:
                with review.lock:
                    if url.path == "/api/reload":
                        review.load()
                        return self._json({"ok": True})
                    if url.path == "/api/defect":
                        from .style import lab
                        data = json.loads(body)
                        note = str(data["note"]).strip()
                        if not note:
                            return self._json({"error": "empty note"}, 400)
                        return self._json(lab.defect_add(review.map_id, int(data["x"]), int(data["z"]),
                                                         f"review page: {note[:500]}"))
            except Exception as error:  # noqa: BLE001
                return self._json({"error": str(error)}, 500)
            self._json({"error": "not found"}, 404)

    return Handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.review", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", type=int, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--vanilla", action="store_true", help="ignore data/maps/ (no judge overlay)")
    args = parser.parse_args(argv)
    review = Review(args.map, None if args.vanilla else REPO / "data/maps")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(review))
    print(json.dumps({"url": f"http://127.0.0.1:{args.port}/", "map": args.map, **review.state()["counts"]}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

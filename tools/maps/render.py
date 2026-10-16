"""Offline map renderer: land models drawn with the area's textures and light.

  python3 -B -m tools.maps.render view --map 543 --at 16 44 [--at X Z ...]   # the game's camera
  python3 -B -m tools.maps.render overview --map 543 [--top] [--ppt 8]       # whole map, labelled
  python3 -B -m tools.maps.render sheet --map 543                            # 3x3 views + overview

No ROM build and no emulator: it reads the pristine rom.nds plus the
override tree data/maps/ (like every agent command), so a generate or
resolve can be looked at seconds later. Images go to build/map-render/.

What it reproduces (pokeheartgold src/field/field_camera.c, area_light.c,
GBATEK 3D): the field camera preset of the map header's cameraType (256x192,
perspective, W-buffer), the area light file's entry at noon, material
lighting/vertex colours, texture formats 1-7 with repeat/flip, culling, and
translucent polygons. What it does not: buildings/props (land.json
`buildings`), texture animation, fog, edge marking, overworld sprites.
The background is black, like the void the game shows where no polygon is.

Images are for the map-look review (AGENTS.md "Maps"); walking and warps
are still proven with memory reads in melonDS.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

from . import codecs, narc, nsbmd, world
from .style import bdhc_gen

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "build/map-render"
GRID, TILE, CHUNK = 32, 16, 512
SCREEN = (256, 192)

# gFieldCameraPresets (asm/field_camera_data.s): distance fx32, angle x/y/z u16,
# perspectiveType u16, perspectiveAngle u16 (half the vertical field of view),
# clip near/far fx32, look-at offset fx32 x3. 36 bytes each, 17 presets.
_CAMERA_PRESETS = bytes.fromhex(
    "c1ae2900" "62dd0000" "00000000" "0000c105" "00600900" "00004b00" "00000000" "00000000" "00000000"
    "5c461900" "83e30000" "00000000" "00008109" "00600800" "00004b00" "00000000" "00500200" "0010ffff"
    "c1ae2900" "c2e30000" "00000000" "0000c105" "00600900" "00004b00" "00000000" "00000000" "00000000"
    "c1ae2900" "42f20000" "00000000" "0000c105" "00600900" "00004b00" "00000000" "c5e90100" "373fffff"
    "9bb86100" "82dc0000" "00000000" "01008102" "00600900" "00706c00" "00000000" "00000000" "00000000"
    "f6191d00" "a2dd0000" "00000000" "00008108" "00600900" "00804800" "00000000" "00000000" "0080feff"
    "c1ae2900" "e2df0000" "00000000" "0000c105" "00600900" "00c05d00" "00000000" "00000000" "00000000"
    "c1ae2900" "e2e10000" "00000000" "0000c105" "00600900" "00004b00" "00000000" "5b7c0100" "e295feff"
    "4c372000" "22d90000" "00000000" "00007007" "00600900" "00403800" "00000000" "00000000" "00000000"
    "c1be2900" "82d50000" "00000000" "0000c105" "00600900" "00004b00" "00000000" "00000000" "00000000"
    "05c81300" "42df0000" "00000000" "0000810c" "00600900" "00406a00" "00000000" "f1c50000" "8ca3fdff"
    "295c2100" "c2e30000" "00000000" "00004107" "00600900" "00004b00" "00000000" "0080ffff" "00000000"
    "c1ae2900" "e2df0000" "00000000" "0000c105" "00600900" "00406a00" "00000000" "00000000" "0000feff"
    "c1ae2900" "42f20000" "00000000" "0000c105" "00600900" "00406a00" "00000000" "c5e90100" "371ffeff"
    "c1ae2900" "c2d40000" "00000000" "0000c105" "00600900" "00004b00" "00000000" "00000000" "00000000"
    "9bb86100" "82dc0000" "00000000" "01008102" "00600900" "00706c00" "00000000" "00000000" "0020fdff"
    "c1ae2900" "02d60000" "00000000" "0000c105" "00600900" "00403800" "00000000" "00000000" "00000000")

# gAreaLightFilePaths, indexed by AreaData lightType.
LIGHT_FILES = ["data/area00light.txt", "data/area01light.txt", "data/area02light.txt",
               "data/dun20_01light.txt", "data/dun20_02light.txt"]
NOON = 43200 // 2  # AreaLightManager keys entries by seconds since midnight / 2


def _angle(v: int) -> float:
    return (v & 0xFFFF) / 65536 * 2 * math.pi


def camera_preset(index: int) -> dict:
    off = 36 * index
    dist, ax, ay, az, _pad, ptype, pangle, near, far, ox, oy, oz = struct.unpack_from(
        "<i6Hii3i", _CAMERA_PRESETS, off)
    return {"distance": dist / 4096, "angle": (ax, ay, az), "orthographic": ptype == 1,
            "halfFovy": _angle(pangle), "near": near / 4096, "far": far / 4096,
            "offset": (ox / 4096, oy / 4096, oz / 4096)}


# --- Area light -----------------------------------------------------------------

def area_light(source, light_type: int, time2: int = NOON) -> dict:
    """The entry of an area light file active at time2 (seconds since midnight / 2)."""
    text = source.read(LIGHT_FILES[light_type]).decode("latin-1").replace("\n", "")
    lines = text.split("\r")
    entries, i = [], 0
    while i < len(lines) and not lines[i].startswith("EOF"):
        block = [[int(v) for v in line.split(",") if v.strip() != ""] for line in lines[i:i + 10]]
        lights = []
        for j in range(4):
            f = block[1 + j]
            if f and f[0] == 1:
                d = [max(-4095, min(4095, v)) / 4096 for v in f[4:7]]
                lights.append({"color": f[1:4], "dir": d})
        entries.append({"end": block[0][0], "lights": lights, "diffuse": block[5][:3],
                        "ambient": block[6][:3], "specular": block[7][:3], "emission": block[8][:3]})
        i += 10
    for entry in entries:
        if entry["end"] > time2:
            return entry
    return entries[0]


# --- Textures (GBATEK "DS 3D Texture Formats") ----------------------------------

def _bgr555(v):
    v = np.asarray(v, dtype=np.uint32)
    return np.stack([v & 31, (v >> 5) & 31, (v >> 10) & 31], axis=-1).astype(np.float32) / 31


class Textures:
    """Decode textures of a BTX0 file to RGBA float arrays (rows = t, columns = s)."""

    def __init__(self, nsbtx: bytes):
        d = self.data = nsbtx
        u16 = lambda o: struct.unpack_from("<H", d, o)[0]  # noqa: E731
        u32 = lambda o: struct.unpack_from("<I", d, o)[0]  # noqa: E731
        t0 = u32(16)
        self.tex_data = t0 + u32(t0 + 0x14)
        self.c4_data = t0 + u32(t0 + 0x24)
        self.c4_index = t0 + u32(t0 + 0x28)
        self.pltt_data = t0 + u32(t0 + 0x38)
        names, entries, _ = nsbmd.read_dict(d, t0 + u16(t0 + 0x0E))
        self.params = {n: struct.unpack_from("<I", e)[0] for n, e in zip(names, entries)}
        names, entries, _ = nsbmd.read_dict(d, t0 + u16(t0 + 0x34))
        self.palettes = {n: struct.unpack_from("<H", e)[0] << 3 for n, e in zip(names, entries)}
        self._cache: dict = {}

    def size(self, name: str) -> tuple[int, int]:
        p = self.params[name]
        return 8 << ((p >> 20) & 7), 8 << ((p >> 23) & 7)

    def _colors(self, palette: str | None, count: int) -> np.ndarray:
        if palette is None or palette not in self.palettes:
            return np.ones((count, 3), np.float32)
        start = self.pltt_data + self.palettes[palette]
        raw = np.frombuffer(self.data, "<u2", count, start) if start + 2 * count <= len(self.data) else \
            np.frombuffer(self.data[start:].ljust(2 * count, b"\0"), "<u2", count)
        return _bgr555(raw)

    def image(self, name: str, palette: str | None) -> np.ndarray:
        key = (name, palette)
        if key not in self._cache:
            self._cache[key] = self._decode(name, palette)
        return self._cache[key]

    def _decode(self, name: str, palette: str | None) -> np.ndarray:
        p = self.params[name]
        w, h = self.size(name)
        fmt, transparent0 = (p >> 26) & 7, bool(p >> 29 & 1)
        n = w * h
        if fmt == 5:
            return self._decode_4x4(p, w, h, palette)
        start = (self.tex_data + ((p & 0xFFFF) << 3))
        bits = {1: 8, 2: 2, 3: 4, 4: 8, 6: 8, 7: 16}[fmt]
        raw = np.frombuffer(self.data, np.uint8, n * bits // 8, start)
        alpha = np.ones(n, np.float32)
        if fmt == 7:
            v = raw.view("<u2").astype(np.uint32)
            rgb = _bgr555(v)
            alpha = (v >> 15).astype(np.float32)
        else:
            if bits == 8:
                idx = raw.astype(np.int64)
            else:
                per = 8 // bits
                idx = ((raw[:, None] >> (np.arange(per) * bits)) & ((1 << bits) - 1)).reshape(-1).astype(np.int64)
            if fmt == 1:
                alpha = (idx >> 5) * 4 + (idx >> 5) // 2
                alpha, idx = alpha.astype(np.float32) / 31, idx & 31
            elif fmt == 6:
                alpha, idx = (idx >> 3).astype(np.float32) / 31, idx & 7
            colors = self._colors(palette, {1: 32, 2: 4, 3: 16, 4: 256, 6: 8}[fmt])
            rgb = colors[idx]
            if transparent0 and fmt in (2, 3, 4):
                alpha = np.where(idx == 0, 0.0, 1.0).astype(np.float32)
        return np.concatenate([rgb, alpha[:, None]], axis=1).reshape(h, w, 4)

    def _decode_4x4(self, p: int, w: int, h: int, palette: str | None) -> np.ndarray:
        ofs = (p & 0xFFFF) << 3
        blocks = (w // 4) * (h // 4)
        texels = np.frombuffer(self.data, "<u4", blocks, self.c4_data + ofs)
        index = np.frombuffer(self.data, "<u2", blocks, self.c4_index + ofs // 2)
        base = self.pltt_data + (self.palettes.get(palette, 0) if palette else 0)
        out = np.zeros((h, w, 4), np.float32)
        for b in range(blocks):
            word, pi = int(texels[b]), int(index[b])
            mode, addr = pi >> 14, base + (pi & 0x3FFF) * 4
            raw = struct.unpack_from("<4H", self.data, addr) if addr + 8 <= len(self.data) else (0, 0, 0, 0)
            c = _bgr555(raw)
            pal = np.ones((4, 4), np.float32)
            pal[:, :3] = c
            if mode == 0:
                pal[3] = 0
            elif mode == 1:
                pal[2, :3] = (c[0] + c[1]) / 2
                pal[3] = 0
            elif mode == 3:
                pal[2, :3] = (c[0] * 5 + c[1] * 3) / 8
                pal[3, :3] = (c[0] * 3 + c[1] * 5) / 8
            bx, by = (b % (w // 4)) * 4, (b // (w // 4)) * 4
            for y in range(4):
                row = (word >> (8 * y)) & 0xFF
                for x in range(4):
                    out[by + y, bx + x] = pal[(row >> (2 * x)) & 3]
        return out


# --- Models to triangles --------------------------------------------------------

def _s(v: int, bits: int) -> int:
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def _normal(raw: int) -> tuple[float, float, float]:
    return tuple(_s(raw >> (10 * k), 10) / 512 for k in range(3))


def _vertices(commands):
    """Like nsbmd.dl_primitives, but remembers whether a COLOR or a NORMAL came last."""
    prims, current = [], None
    pos, uv, normal, color, last = [0, 0, 0], None, None, None, None
    for c in commands:
        op, p = c[0], c[1:]
        if op == 0x40:
            current = {"type": p[0] & 3, "vertices": []}
            prims.append(current)
        elif op == 0x41:
            current = None
        elif op == 0x22:
            uv = (_s(p[0], 16) / 16, _s(p[0] >> 16, 16) / 16)
        elif op == 0x21:
            normal, last = p[0], "normal"
        elif op == 0x20:
            color, last = p[0], "color"
        elif 0x23 <= op <= 0x28:
            if op == 0x23:
                pos = [_s(p[0], 16), _s(p[0] >> 16, 16), _s(p[1], 16)]
            elif op == 0x24:
                pos = [_s(p[0] >> s, 10) << 6 for s in (0, 10, 20)]
            elif op == 0x25:
                pos[0], pos[1] = _s(p[0], 16), _s(p[0] >> 16, 16)
            elif op == 0x26:
                pos[0], pos[2] = _s(p[0], 16), _s(p[0] >> 16, 16)
            elif op == 0x27:
                pos[1], pos[2] = _s(p[0], 16), _s(p[0] >> 16, 16)
            else:
                pos = [_s(pos[k] + _s(p[0] >> (10 * k), 10), 16) for k in range(3)]
            current["vertices"].append((tuple(pos), uv, normal, color, last))
    return prims


def _lit(material: dict, normal, light: dict) -> np.ndarray:
    """GBATEK lighting with the area light's material colours (5-bit units)."""
    out = np.array(light["emission"], np.float32)
    n = np.array(normal, np.float32)
    for i, lt in enumerate(light["lights"]):
        if not material["polyAttr"] >> i & 1:
            continue
        lc = np.array(lt["color"], np.float32)
        ld = np.array(lt["dir"], np.float32)
        diffuse = max(0.0, -float(ld @ n))
        half = (ld + np.array([0, 0, -1], np.float32)) / 2
        shine = max(0.0, -float(half @ n)) ** 2
        out += (np.array(light["specular"]) * lc * shine + np.array(light["diffuse"]) * lc * diffuse
                + np.array(light["ambient"]) * lc) / 31
    return np.minimum(out, 31) / 31


class Mesh:
    """Triangles of land models in world units, with per-vertex colour and texcoords."""

    def __init__(self):
        self.pos, self.uv, self.color, self.normal, self.mat = [], [], [], [], []
        self.materials: list[dict] = []

    def add_model(self, model_bytes: bytes, offset: tuple[float, float, float], textures: Textures,
                  light: dict) -> None:
        model = nsbmd.parse(model_bytes)["models"][0]
        scale = model["info"]["posScale"] / 4096 / 4096
        tr = [c / 4096 for c in model["nodes"][0].get("translation", (0, 0, 0))]
        tex_of = {i: t["name"] for t in model["textures"] for i in t["materials"]}
        pal_of = {i: p["name"] for p in model["palettes"] for i in p["materials"]}
        first = len(self.materials)
        for i, m in enumerate(model["materials"]):
            tex = tex_of.get(i)
            image = textures.image(tex, pal_of.get(i)) if tex in textures.params else None
            tip = m["texImageParam"]
            ts = m.get("texScale")
            fmt = (textures.params[tex] >> 26) & 7 if image is not None else 0
            self.materials.append({
                "name": m["name"], "polyAttr": m["polyAttr"], "image": image,
                "repeat": (tip >> 16 & 1, tip >> 17 & 1), "flip": (tip >> 18 & 1, tip >> 19 & 1),
                "scale": (ts[0] / 4096, ts[1] / 4096) if ts else (1.0, 1.0),
                "alpha": ((m["polyAttr"] >> 16) & 31) / 31,
                "translucent": ((m["polyAttr"] >> 16) & 31) < 31 or fmt in (1, 6),  # alpha textures blend
                "front": bool(m["polyAttr"] >> 7 & 1), "back": bool(m["polyAttr"] >> 6 & 1),
                "diffuse": _bgr555(m["diffAmb"] & 0x7FFF) if m["diffAmb"] & 0x8000 else np.ones(3, np.float32)})
        for mat, shp in nsbmd._shape_materials(model):
            material = self.materials[first + mat]
            for prim in _vertices(model["shapes"][shp]["dl"]):
                verts = prim["vertices"]
                for poly in nsbmd._polygons({"type": prim["type"], "vertices": verts}):
                    tris = [poly] if len(poly) == 3 else [[poly[0], poly[1], poly[2]], [poly[0], poly[2], poly[3]]]
                    for tri in tris:
                        p, uv, col, nrm = [], [], [], []
                        for (vp, vuv, vn, vc, last) in tri:
                            p.append([vp[k] * scale + tr[k] + offset[k] for k in range(3)])
                            uv.append(vuv or (0.0, 0.0))
                            if last == "normal" and vn is not None:  # no light enabled: emission only
                                col.append(_lit(material, _normal(vn), light))
                                nrm.append(_normal(vn))
                            elif last == "color" and vc is not None:
                                col.append(_bgr555(vc))
                                nrm.append((0.0, 1.0, 0.0))
                            else:
                                col.append(material["diffuse"])
                                nrm.append((0.0, 1.0, 0.0))
                        self.pos.append(p)
                        self.uv.append(uv)
                        self.color.append(col)
                        self.normal.append(nrm)
                        self.mat.append(first + mat)

    def arrays(self):
        return (np.array(self.pos, np.float64).reshape(-1, 3, 3), np.array(self.uv, np.float64).reshape(-1, 3, 2),
                np.array(self.color, np.float32).reshape(-1, 3, 3), np.array(self.mat, np.int64))


# --- Cameras and rasterizer ------------------------------------------------------

class Camera:
    def __init__(self, pos, target, size, half_fovy=None, ortho_height=None, near=1.0, far=1e9):
        self.pos, self.target = np.array(pos, float), np.array(target, float)
        f = self.target - self.pos
        self.forward = f / np.linalg.norm(f)
        up = np.array([0.0, 1.0, 0.0]) if abs(self.forward[1]) < 0.999 else np.array([0.0, 0.0, -1.0])
        r = np.cross(self.forward, up)
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.forward)
        self.size, self.near, self.far = size, near, far
        self.half_fovy, self.ortho_height = half_fovy, ortho_height

    @classmethod
    def field(cls, target, preset: dict, size=SCREEN):
        """The field camera looking at `target` (the player's feet), as Camera_Init_FromTargetDistanceAndAngle."""
        ax, ay, _ = (_angle(a) for a in preset["angle"])
        d = preset["distance"]
        t = np.array(target, float) + np.array(preset["offset"])
        pos = t + np.array([math.sin(ay) * d * math.cos(ax), math.sin(-ax) * d, math.cos(ay) * d * math.cos(ax)])
        if preset["orthographic"]:
            return cls(pos, t, size, ortho_height=2 * d * math.tan(preset["halfFovy"]),
                       near=preset["near"], far=preset["far"])
        return cls(pos, t, size, half_fovy=preset["halfFovy"], near=preset["near"], far=preset["far"])

    def view(self, p: np.ndarray) -> np.ndarray:
        q = p - self.pos
        return np.stack([q @ self.right, q @ self.up, q @ self.forward], axis=-1)

    def project(self, v: np.ndarray) -> np.ndarray:
        """View-space points -> screen x, y (pixels, y down)."""
        w, h = self.size
        if self.ortho_height is not None:
            k = h / self.ortho_height
            return np.stack([w / 2 + v[..., 0] * k, h / 2 - v[..., 1] * k], axis=-1)
        t = math.tan(self.half_fovy)
        return np.stack([w / 2 + v[..., 0] / (v[..., 2] * t * (w / h)) * (w / 2),
                         h / 2 - v[..., 1] / (v[..., 2] * t) * (h / 2)], axis=-1)

    def screen_of(self, point) -> tuple[float, float] | None:
        v = self.view(np.array(point, float))
        if self.ortho_height is None and v[2] <= self.near:
            return None
        x, y = self.project(v)
        return float(x), float(y)


def _clip_near(v, uv, col, near):
    """Clip one triangle (view space) against depth >= near: 0, 1 or 2 triangles."""
    inside = v[:, 2] >= near
    if inside.all():
        return [(v, uv, col)]
    if not inside.any():
        return []
    out = []
    for i in range(3):
        j = (i + 1) % 3
        if inside[i]:
            out.append((v[i], uv[i], col[i]))
        if inside[i] != inside[j]:
            t = (near - v[i, 2]) / (v[j, 2] - v[i, 2])
            out.append((v[i] + t * (v[j] - v[i]), uv[i] + t * (uv[j] - uv[i]), col[i] + t * (col[j] - col[i])))
    tris = []
    for k in range(1, len(out) - 1):
        tri = [out[0], out[k], out[k + 1]]
        tris.append((np.array([a for a, _, _ in tri]), np.array([b for _, b, _ in tri]),
                     np.array([c for _, _, c in tri])))
    return tris


def _sample(material: dict, s: np.ndarray, t: np.ndarray) -> np.ndarray:
    image = material["image"]
    h, w = image.shape[:2]
    s, t = s * material["scale"][0], t * material["scale"][1]
    coords = []
    for c, size, rep, flip in ((s, w, material["repeat"][0], material["flip"][0]),
                               (t, h, material["repeat"][1], material["flip"][1])):
        c = np.floor(c).astype(np.int64)
        if rep and flip:
            c = c % (2 * size)
            c = np.where(c >= size, 2 * size - 1 - c, c)
        elif rep:
            c = c % size
        else:
            c = np.clip(c, 0, size - 1)
        coords.append(c)
    return image[coords[1], coords[0]]


def rasterize(mesh: Mesh, camera: Camera, background=(0, 0, 0), pick: bool = False):
    """Draw the mesh; returns an RGB uint8 image. Opaque first (W-buffer), then translucent back to front.

    pick=True also returns an (H, W, 2) array of the world x, z drawn at each pixel (NaN: nothing, the
    black void), so a pixel maps back to a tile: floor(x / 16), floor(z / 16).
    """
    pos, uv, col, mat = mesh.arrays()
    w, h = camera.size
    color = np.zeros((h, w, 3), np.float32)
    color[:] = np.array(background, np.float32) / 255
    depth = np.full((h, w), np.inf)
    where = np.full((h, w, 2), np.nan) if pick else None
    if not len(pos):
        image = (color * 255).astype(np.uint8)
        return (image, where) if pick else image
    view = camera.view(pos)
    ortho = camera.ortho_height is not None
    # cull whole triangles behind the camera or outside the screen
    keep = view[:, :, 2].max(axis=1) >= camera.near
    translucent = []
    order = np.nonzero(keep)[0]
    for i in order:
        m = mesh.materials[mat[i]]
        if m["translucent"]:
            translucent.append(i)
            continue
        _draw(view[i], uv[i], col[i], m, camera, ortho, color, depth, where, blend=False)
    translucent.sort(key=lambda i: -view[i, :, 2].mean())
    for i in translucent:
        _draw(view[i], uv[i], col[i], mesh.materials[mat[i]], camera, ortho, color, depth, where, blend=True)
    image = (np.clip(color, 0, 1) * 255 + 0.5).astype(np.uint8)
    return (image, where) if pick else image


def _draw(v, uv, col, m, camera, ortho, color, depth, where, blend):
    w, h = camera.size
    pieces = [(v, uv, col)] if ortho else _clip_near(v, uv, col, camera.near)
    for v3, uv3, col3 in pieces:
        sxy = camera.project(v3)
        # Facing: front faces wind counter-clockwise on screen (y down), checked on vanilla chunks.
        area = ((sxy[1, 0] - sxy[0, 0]) * (sxy[2, 1] - sxy[0, 1])
                - (sxy[2, 0] - sxy[0, 0]) * (sxy[1, 1] - sxy[0, 1]))
        if area == 0 or (area < 0 and not m["front"]) or (area > 0 and not m["back"]):
            continue
        x0, x1 = max(0, int(math.floor(sxy[:, 0].min()))), min(w, int(math.ceil(sxy[:, 0].max())) + 1)
        y0, y1 = max(0, int(math.floor(sxy[:, 1].min()))), min(h, int(math.ceil(sxy[:, 1].max())) + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        px, py = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        b = []
        for a, c in ((1, 2), (2, 0), (0, 1)):
            b.append(((sxy[c, 0] - sxy[a, 0]) * (py - sxy[a, 1]) - (sxy[c, 1] - sxy[a, 1]) * (px - sxy[a, 0])) / area)
        b0, b1, b2 = b
        inside = (b0 >= -1e-9) & (b1 >= -1e-9) & (b2 >= -1e-9)
        if not inside.any():
            continue
        if ortho:
            wgt = np.stack([b0, b1, b2], -1)
            d = wgt @ v3[:, 2]
        else:
            inv = 1 / v3[:, 2]
            iw = b0 * inv[0] + b1 * inv[1] + b2 * inv[2]
            d = 1 / iw
            wgt = np.stack([b0 * inv[0], b1 * inv[1], b2 * inv[2]], -1) * d[..., None]
        region = depth[y0:y1, x0:x1]
        visible = inside & (d < region)
        if not ortho:
            visible &= (d >= camera.near) & (d <= camera.far)
        if not visible.any():
            continue
        rgb = wgt @ col3
        alpha = np.full(d.shape, m["alpha"], np.float32)
        if m["image"] is not None:
            st = wgt @ uv3
            texel = _sample(m, st[..., 0], st[..., 1])
            rgb = rgb * texel[..., :3]
            alpha = alpha * texel[..., 3]
        target = color[y0:y1, x0:x1]
        if not blend:
            solid = visible & (alpha >= 0.999)
            target[solid] = rgb[solid]
            region[solid] = d[solid]
            part = visible & (alpha > 0.001) & (alpha < 0.999)
        else:
            part = visible & (alpha > 0.001)
        if where is not None:
            drawn = solid | part if not blend else part
            if drawn.any():
                vp = wgt[drawn] @ v3
                wp = camera.pos + vp[:, :1] * camera.right + vp[:, 1:2] * camera.up + vp[:, 2:] * camera.forward
                where[y0:y1, x0:x1][drawn] = wp[:, [0, 2]]
        if part.any():
            a = alpha[part][:, None]
            target[part] = target[part] * (1 - a) + rgb[part] * a


# --- Maps -----------------------------------------------------------------------

class MapScene:
    """The edited world (rom.nds + data/maps/) around one map, ready to render."""

    def __init__(self, map_id: int, overrides: Path = REPO / "data/maps", rom: Path = REPO / "rom.nds"):
        self.source = world.RomSource(rom)
        base = world.load_base(self.source, repo=REPO)
        self.world = world.apply_overrides(base, overrides) if overrides else base
        self.map_id = map_id
        header = self.world.headers[map_id]
        self.area = self.world.member("area", header["areaDataBank"])
        self.camera_preset = camera_preset(header.get("cameraType", 0) % 17)
        self.light = area_light(self.source, self.area["lightType"] % len(LIGHT_FILES))
        self.textures = Textures(narc.members(self.source.read("a/0/4/4"))[self.area["mapTileset"]])
        self.matrix = self.world.matrix_for(map_id)
        self._meshes: dict = {}

    def own_chunks(self) -> list[tuple[int, int]]:
        m = self.matrix
        cells = [(cx, cz) for cz in range(m["height"]) for cx in range(m["width"])
                 if self.land_at(cx, cz) is not None]
        if m["headers"] is None:
            return cells
        own = [(cx, cz) for cx, cz in cells if m["headers"][cz][cx] == self.map_id]
        return own or [(cx, cz) for cx, cz in cells if m["headers"][cz][cx] == 0]

    def land_at(self, cx: int, cz: int) -> int | None:
        m = self.matrix
        if not (0 <= cx < m["width"] and 0 <= cz < m["height"]):
            return None
        land = m["landData"][cz][cx]
        return None if land == 0xFFFF or land >= len(self.world.raw["land"]) else land

    def mesh(self, chunks) -> Mesh:
        mesh = Mesh()
        for cx, cz in chunks:
            land = self.land_at(cx, cz)
            if land is None:
                continue
            model = codecs.decode_land_model(self.world.raw["land"][land])
            mesh.add_model(model, (cx * CHUNK + CHUNK / 2, 0.0, cz * CHUNK + CHUNK / 2), self.textures, self.light)
        return mesh

    def height(self, x: int, z: int) -> float:
        land = self.land_at(x // GRID, z // GRID)
        if land is None:
            return 0.0
        bdhc = self.world.member("land", land)["bdhc"]
        cx, cz = bdhc_gen.tile_center(x % GRID, z % GRID)
        y = bdhc_gen.height_at(bdhc, cx, cz)
        return 0.0 if y is None else y

    def tile_world(self, x: int, z: int) -> tuple[float, float, float]:
        return (x * TILE + TILE / 2, self.height(x, z), z * TILE + TILE / 2)

    def view(self, x: int, z: int, scale: int = 1, pick: bool = False):
        """The top screen with the player standing on tile (x, z)."""
        cx, cz = x // GRID, z // GRID
        mesh = self.mesh([(cx + dx, cz + dz) for dz in (-1, 0, 1) for dx in (-1, 0, 1)])
        cam = Camera.field(self.tile_world(x, z), self.camera_preset, (SCREEN[0] * scale, SCREEN[1] * scale))
        return rasterize(mesh, cam, pick=pick)

    def overview(self, ppt: int = 8, top: bool = False, chunks=None, pick: bool = False):
        """Whole map, orthographic; oblique from the field camera's pitch unless top.

        Returns (image, camera), or (image, camera, world x/z per pixel) with pick."""
        chunks = chunks or self.own_chunks()
        xs = [c[0] for c in chunks]
        zs = [c[1] for c in chunks]
        x0, x1 = min(xs) * CHUNK, (max(xs) + 1) * CHUNK
        z0, z1 = min(zs) * CHUNK, (max(zs) + 1) * CHUNK
        mesh = self.mesh(chunks)
        ys = np.array(mesh.pos).reshape(-1, 3)[:, 1] if mesh.pos else np.zeros(1)
        cx, cz, cy = (x0 + x1) / 2, (z0 + z1) / 2, float(np.median(ys))
        width = int((x1 - x0) / TILE * ppt)
        if top:
            cam = Camera((cx, cy + 4000, cz), (cx, cy, cz), (width, int((z1 - z0) / TILE * ppt)),
                         ortho_height=z1 - z0)
        else:
            ax = _angle(self.camera_preset["angle"][0])
            pitch = -ax  # downward angle
            d = 4000
            pos = np.array([cx, cy + math.sin(pitch) * d, cz + math.cos(pitch) * d])
            cam = Camera(pos, (cx, cy, cz), (width, 1), ortho_height=1)
            # Frame by the projected extent: tall terrain must not leave the image.
            up = cam.view(np.array(mesh.pos).reshape(-1, 3))[:, 1] if mesh.pos else np.zeros(1)
            shift = (float(up.max()) + float(up.min())) / 2
            span = float(up.max() - up.min()) + 2 * TILE
            cam = Camera(pos + shift * cam.up, np.array([cx, cy, cz]) + shift * cam.up,
                         (width, int(span / TILE * ppt)), ortho_height=span)
        cam.floor = cy  # median floor height: where void rays are traced
        if pick:
            image, where = rasterize(mesh, cam, pick=True)
            return image, cam, where
        return rasterize(mesh, cam), cam


def voids(scene: MapScene, ppt: int = 4) -> dict:
    """Tiles where the black void shows: a check the tile metrics cannot make.

    `top`: tiles not fully covered seen from straight above. `camera`: tiles
    whose ground (at the median floor height) is seen through void from the
    field camera's pitch, i.e. a missing wall face or floor edge. Only
    tiles beside ground reachable from the map's warps count (as lint's
    reachability), away from the map's edge, in
    chunks without buildings (generated chunks have none).
    """
    chunks = scene.own_chunks()
    x0, z0 = min(c[0] for c in chunks) * GRID, min(c[1] for c in chunks) * GRID
    x1, z1 = (max(c[0] for c in chunks) + 1) * GRID, (max(c[1] for c in chunks) + 1) * GRID
    owned = {(cx, cz) for cx, cz in chunks}
    _, _, where = scene.overview(ppt, top=True, pick=True)
    h, w = where.shape[:2]
    gaps = np.isnan(where[..., 0])[:h - h % ppt, :w - w % ppt]
    gaps = gaps.reshape(h // ppt, ppt, w // ppt, ppt).any(axis=(1, 3))
    top = sorted((x0 + int(x), z0 + int(z)) for z, x in zip(*np.nonzero(gaps))
                 if ((x0 + int(x)) // GRID, (z0 + int(z)) // GRID) in owned)
    _, cam, where = scene.overview(ppt, top=False, pick=True)
    ys, xs = np.nonzero(np.isnan(where[..., 0]))
    wv, hv = cam.size
    k = cam.ortho_height / hv
    origin = (cam.pos + ((xs + 0.5 - wv / 2) * k)[:, None] * cam.right
              + ((hv / 2 - ys - 0.5) * k)[:, None] * cam.up)
    floor = cam.floor
    t = (floor - origin[:, 1]) / cam.forward[1]
    hit = origin + t[:, None] * cam.forward
    tiles = {(int(px // TILE), int(pz // TILE)) for px, pz in hit[:, [0, 2]]}
    # Only void beside ground the player can reach counts (cave walls sit in void by design), and only
    # in chunks without buildings: their models are not drawn, and rooms are mostly buildings.
    near_land = set()
    for x, z in reachable(scene):
        near_land |= {(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
    checked = {(cx, cz) for cx, cz in chunks if not scene.world.member("land", scene.land_at(cx, cz))["buildings"]}
    header = scene.world.headers[scene.map_id]
    exits = {(w["x"] + dx, w["z"] + dz) for w in scene.world.member("events", header["eventsBank"])["warps"]
             for dx in range(-3, 4) for dz in range(-3, 4)}  # vanilla room exits open onto the void

    def counts(x, z):  # nor the void beyond the map's own edge
        return ((x, z) in near_land and (x // GRID, z // GRID) in checked and (x, z) not in exits
                and all(((x + dx) // GRID, (z + dz) // GRID) in owned for dx in (-2, 0, 2) for dz in (-2, 0, 2)))
    return {"top": [t for t in top if counts(*t)], "camera": sorted(t for t in tiles if counts(*t))}


# --- Annotation and output --------------------------------------------------------

def annotate_tiles(image: np.ndarray, scene: MapScene, cam: Camera, every: int = 8, marks=()):
    """Label every `every`-th tile centre with its map coordinates; draw `marks` [(x, z, text)] in red."""
    from PIL import Image, ImageDraw
    img = Image.fromarray(image)
    draw = ImageDraw.Draw(img)
    chunks = scene.own_chunks()
    for cx, cz in chunks:
        for lz in range(0, GRID, every):
            for lx in range(0, GRID, every):
                x, z = cx * GRID + lx, cz * GRID + lz
                at = cam.screen_of(scene.tile_world(x, z))
                if at:
                    draw.rectangle([at[0] - 1, at[1] - 1, at[0] + 1, at[1] + 1], fill=(255, 255, 0))
                    draw.text((at[0] + 3, at[1] - 5), f"{x},{z}", fill=(255, 255, 0))
    for x, z, text in marks:
        at = cam.screen_of(scene.tile_world(x, z))
        if at:
            draw.ellipse([at[0] - 5, at[1] - 5, at[0] + 5, at[1] + 5], outline=(255, 40, 40), width=2)
            draw.text((at[0] + 7, at[1] + 2), text, fill=(255, 40, 40))
    return np.asarray(img)


def save(image: np.ndarray, path: Path, scale: int = 1) -> Path:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(image)
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path)
    return path


def reachable(scene: MapScene) -> list[tuple[int, int]]:
    """Tiles of the map's own chunks the player can reach from its warps (tools.maps.reach, as lint)."""
    from . import reach
    header = scene.world.headers[scene.map_id]
    warps = scene.world.member("events", header["eventsBank"])["warps"]
    grid = reach.Grid(scene.world, header["matrixId"])
    seen = grid.reachable({(w["x"], w["z"]) for w in warps})
    owned = set(scene.own_chunks())
    return [(i % grid.width, i // grid.width) for i in range(len(seen))
            if seen[i] and ((i % grid.width) // GRID, (i // grid.width) // GRID) in owned]


def standable(scene: MapScene, floored: bool = False) -> list[tuple[int, int]]:
    """Open tiles of the map's chunks; with floored, only those with a BDHC plate under the centre
    (rooms leave the unused part of their chunk open but floorless)."""
    out = []
    for cx, cz in scene.own_chunks():
        land = scene.world.member("land", scene.land_at(cx, cz))
        query = bdhc_gen.Query(land["bdhc"]) if floored else None
        for lz in range(GRID):
            for lx in range(GRID):
                if land["tiles"]["collision"][lz][lx] == "#":
                    continue
                if query is not None and query.height(*bdhc_gen.tile_center(lx, lz), None, bdhc_gen.NEAREST) is None:
                    continue
                out.append((cx * GRID + lx, cz * GRID + lz))
    return out


def sheet_views(scene: MapScene) -> list[tuple[str, tuple[int, int]]]:
    """3 x 3 standable spots spread over the map, like showcase.shots."""
    land = standable(scene)
    chunks = scene.own_chunks()
    x0, x1 = min(c[0] for c in chunks) * GRID, (max(c[0] for c in chunks) + 1) * GRID
    z0, z1 = min(c[1] for c in chunks) * GRID, (max(c[1] for c in chunks) + 1) * GRID
    out = []
    for j, fz in enumerate((0.2, 0.5, 0.8)):
        for i, fx in enumerate((0.2, 0.5, 0.8)):
            tx, tz = x0 + int(fx * (x1 - x0)), z0 + int(fz * (z1 - z0))
            x, z = min(land, key=lambda p: (abs(p[0] - tx) + abs(p[1] - tz), p))
            out.append((f"{'nms'[j]}{'wce'[i]}-x{x:02d}-z{z:02d}", (x, z)))
    return out


def sheet(scene: MapScene, out_dir: Path) -> Path:
    from PIL import Image, ImageDraw
    views = sheet_views(scene)
    scale, label = 2, 14
    cell_w, cell_h = 256 * scale, (192 + label) * scale
    img = Image.new("RGB", (cell_w * 3, cell_h * 3), "white")
    draw = ImageDraw.Draw(img)
    for i, (name, (x, z)) in enumerate(views):
        shot = Image.fromarray(scene.view(x, z)).resize((256 * scale, 192 * scale), Image.NEAREST)
        x0, y0 = (i % 3) * cell_w, (i // 3) * cell_h
        img.paste(shot, (x0, y0 + label * scale))
        draw.text((x0 + 6, y0 + 6), f"{scene.map_id}-{name}", fill="black")
    path = out_dir / f"sheet-{scene.map_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.render", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overrides", type=Path, default=REPO / "data/maps")
    parser.add_argument("--vanilla", action="store_true", help="ignore data/maps/")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("view")
    v.add_argument("--map", type=int, required=True)
    v.add_argument("--at", type=int, nargs=2, action="append", required=True, metavar=("X", "Z"))
    v.add_argument("--scale", type=int, default=2)
    o = sub.add_parser("overview")
    o.add_argument("--map", type=int, required=True)
    o.add_argument("--top", action="store_true")
    o.add_argument("--ppt", type=int, default=8, help="pixels per tile")
    o.add_argument("--mark", nargs=3, action="append", default=[], metavar=("X", "Z", "TEXT"))
    s = sub.add_parser("sheet")
    s.add_argument("--map", type=int, required=True)
    args = parser.parse_args(argv)
    scene = MapScene(args.map, None if args.vanilla else args.overrides)
    written = []
    if args.command == "view":
        for x, z in args.at:
            written.append(save(scene.view(x, z), args.out / f"view-{args.map}-x{x}-z{z}.png", args.scale))
    elif args.command == "overview":
        image, cam = scene.overview(args.ppt, args.top)
        marks = [(int(x), int(z), text) for x, z, text in args.mark]
        image = annotate_tiles(image, scene, cam, marks=marks)
        written.append(save(image, args.out / f"overview-{args.map}{'-top' if args.top else ''}.png"))
    else:
        written.append(sheet(scene, args.out))
        image, cam = scene.overview(8, False)
        written.append(save(annotate_tiles(image, scene, cam), args.out / f"overview-{args.map}.png"))
    print(json.dumps({"written": [str(p) for p in written]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

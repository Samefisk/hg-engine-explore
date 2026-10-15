"""Lossless NSBMD (BMD0/MDL0) codec and a map-chunk model generator.

  python3 -B -m tools.maps.nsbmd roundtrip [--rom rom.nds]
  python3 -B -m tools.maps.nsbmd generate --area ID --spec grid.json --out chunk.nsbmd
  python3 -B -m tools.maps.nsbmd rebuild --land N --out chunk.nsbmd   # vanilla geometry
  python3 -B -m tools.maps.nsbmd info FILE.nsbmd

parse(b) -> plain JSON data; write(spec) -> bytes; write(parse(b)) == b for
every vanilla land_data model. Layout notes: documentation/map-system/nsbmd.md.
Only the texture-less, single-model files the map chunks use are supported
(no TEX0 section); a non-empty envelope-matrix block is kept as opaque hex.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

FX = 4096  # 1.0 in fx32 / fx16


class NsbmdError(ValueError):
    pass


def _u16(b, o): return struct.unpack_from("<H", b, o)[0]
def _u32(b, o): return struct.unpack_from("<I", b, o)[0]


def _pack(fmt, *values) -> bytes:
    try:
        return struct.pack(fmt, *values)
    except struct.error as error:
        raise NsbmdError(f"value out of range for {fmt}: {values} ({error})") from None


def _align4(buf: bytearray, pad: int = 0) -> None:
    while len(buf) % 4:
        buf.append(pad)


# --- Names and resource dictionaries ----------------------------------------

def _name_bytes(name: str) -> bytes:
    raw = name.encode("latin-1")
    if len(raw) > 16:
        raise NsbmdError(f"name {name!r} is longer than 16 bytes")
    return raw.ljust(16, b"\0")


def _name_str(raw: bytes) -> str:
    """Names are 16 bytes, NUL padded (a 16-character name has no NUL)."""
    text = raw.rstrip(b"\0")
    if b"\0" in text:
        raise NsbmdError(f"name {raw!r} has bytes after its terminator")
    return text.decode("latin-1")


def _bit(key: bytes, bit: int) -> int:
    return (key[bit >> 3] >> (bit & 7)) & 1


def patricia_tree(names: list[bytes]) -> list[tuple[int, int, int, int]]:
    """Return the NNS name-lookup tree as (refBit, left, right, entry) nodes.

    Node 0 is the root (refBit 127, all-zero key). Each insertion adds node
    i+1 for entry i, splitting at the highest bit where the new name differs
    from the name the search ends on. This reproduces the vanilla trees.
    """
    ref, left, right, entry = [127], [0], [0], [0]
    for index, key in enumerate(names):
        p, x = 0, left[0]
        while ref[p] > ref[x]:
            p, x = x, (right[x] if _bit(key, ref[x]) else left[x])
        other = names[entry[x]] if x else bytes(16)
        diff = next((b for b in range(127, -1, -1) if _bit(key, b) != _bit(other, b)), None)
        if diff is None:
            raise NsbmdError(f"duplicate dictionary name {key!r}")
        p, x = 0, left[0]
        while ref[p] > ref[x] and ref[x] > diff:
            p, x = x, (right[x] if _bit(key, ref[x]) else left[x])
        n = len(ref)
        ref.append(diff)
        entry.append(index)
        if _bit(key, diff):
            left.append(x)
            right.append(n)
        else:
            left.append(n)
            right.append(x)
        if p == 0:
            left[0] = n
        elif _bit(key, ref[p]):
            right[p] = n
        else:
            left[p] = n
    # The file stores nodes renumbered in pre-order (left subtree first).
    order = [0]

    def visit(n: int) -> None:
        order.append(n)
        for child in (left[n], right[n]):
            if ref[child] < ref[n]:
                visit(child)

    if len(ref) > 1:
        visit(left[0])
    new = {old: i for i, old in enumerate(order)}
    return [(ref[o], new[left[o]], new[right[o]], entry[o]) for o in order]


def dict_size(count: int, unit: int) -> int:
    return 8 + 4 * (count + 1) + 4 + count * (unit + 16)


def build_dict(names: list[str], entries: list[bytes], unit: int) -> bytes:
    raw = [_name_bytes(n) for n in names]
    if len(raw) > 255:
        raise NsbmdError("a dictionary holds at most 255 entries")
    out = bytearray(_pack("<BBH", 0, len(raw), dict_size(len(raw), unit)))
    out += _pack("<HH", 8, 8 + 4 * (len(raw) + 1))
    for node in patricia_tree(raw):
        out += bytes(node)
    out += _pack("<HH", unit, 4 + unit * len(raw))
    for e in entries:
        if len(e) != unit:
            raise NsbmdError("dictionary entry has the wrong size")
        out += e
    for r in raw:
        out += r
    return bytes(out)


def read_dict(data: bytes, off: int) -> tuple[list[str], list[bytes], int]:
    """Return (names, entry bytes, size) and check the tree is the canonical one."""
    revision, count, size = struct.unpack_from("<BBH", data, off)
    header, entries_off = struct.unpack_from("<HH", data, off + 4)
    if revision != 0 or header != 8 or entries_off != 8 + 4 * (count + 1):
        raise NsbmdError(f"unexpected dictionary header at {off:#x}")
    unit, names_off = struct.unpack_from("<HH", data, off + entries_off)
    base = off + entries_off
    entries = [data[base + 4 + i * unit: base + 4 + (i + 1) * unit] for i in range(count)]
    raw = [data[base + names_off + 16 * i: base + names_off + 16 * (i + 1)] for i in range(count)]
    names = [_name_str(r) for r in raw]
    blob = build_dict(names, entries, unit)
    if size != len(blob) or data[off:off + size] != blob:
        raise NsbmdError(f"dictionary at {off:#x} is not in canonical form")
    return names, entries, size


# --- Display lists (GX command stream, GBATEK "DS 3D Geometry Commands") -----

GX_PARAMS = {
    0x00: 0, 0x10: 1, 0x11: 0, 0x12: 1, 0x13: 1, 0x14: 1, 0x15: 0, 0x16: 16,
    0x17: 12, 0x18: 16, 0x19: 12, 0x1A: 9, 0x1B: 3, 0x1C: 3, 0x20: 1, 0x21: 1,
    0x22: 1, 0x23: 2, 0x24: 1, 0x25: 1, 0x26: 1, 0x27: 1, 0x28: 1, 0x29: 1,
    0x2A: 1, 0x2B: 1, 0x30: 1, 0x31: 1, 0x32: 1, 0x33: 1, 0x34: 32, 0x40: 1,
    0x41: 0, 0x50: 1, 0x60: 1, 0x70: 3, 0x71: 2, 0x72: 1,
}
GX_NAMES = {
    0x00: "NOP", 0x14: "RESTORE", 0x20: "COLOR", 0x21: "NORMAL", 0x22: "TEXCOORD",
    0x23: "VTX_16", 0x24: "VTX_10", 0x25: "VTX_XY", 0x26: "VTX_XZ", 0x27: "VTX_YZ",
    0x28: "VTX_DIFF", 0x40: "BEGIN_VTXS", 0x41: "END_VTXS",
}


def decode_dl(data: bytes) -> list[list[int]]:
    """Packed command words -> [[cmd, *params], ...] including NOP fillers.

    Each word holds four command bytes (low byte first) followed by the
    parameters of those commands in order. Every 4th entry starts a word.
    """
    if len(data) % 4:
        raise NsbmdError("display list size is not a multiple of 4")
    words = struct.unpack(f"<{len(data) // 4}I", data)
    out, i = [], 0
    while i < len(words):
        packed = words[i]
        i += 1
        for shift in (0, 8, 16, 24):
            cmd = (packed >> shift) & 0xFF
            if cmd not in GX_PARAMS:
                raise NsbmdError(f"unknown GX command {cmd:#x}")
            n = GX_PARAMS[cmd]
            if i + n > len(words):
                raise NsbmdError("display list ends inside a command's parameters")
            out.append([cmd, *words[i:i + n]])
            i += n
    return out


def encode_dl(commands: list[list[int]]) -> bytes:
    cmds = list(commands)
    while len(cmds) % 4:
        cmds.append([0])
    out = bytearray()
    for g in range(0, len(cmds), 4):
        group = cmds[g:g + 4]
        word = 0
        for k, c in enumerate(group):
            if c[0] not in GX_PARAMS or len(c) - 1 != GX_PARAMS[c[0]]:
                raise NsbmdError(f"GX command {c} has the wrong parameter count")
            word |= c[0] << (8 * k)
        out += _pack("<I", word)
        for c in group:
            out += _pack(f"<{len(c) - 1}I", *c[1:])
    return bytes(out)


def _s(v: int, bits: int) -> int:
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def dl_primitives(commands: list[list[int]]) -> list[dict]:
    """Run the vertex state machine; return primitives with fx16 positions.

    Each primitive: {"type": 0 tri | 1 quad | 2 tri strip | 3 quad strip,
    "vertices": [{"pos": (x,y,z), "uv": (s,t) | None, "normal": raw | None,
    "color": raw | None}]}. Positions are raw 4.12 model units before posScale.
    """
    prims, current = [], None
    pos, uv, normal, color = [0, 0, 0], None, None, None
    for c in commands:
        op, p = c[0], c[1:]
        if op == 0x40:
            current = {"type": p[0] & 3, "vertices": []}
            prims.append(current)
        elif op == 0x41:
            current = None
        elif op == 0x22:
            uv = (_s(p[0], 16), _s(p[0] >> 16, 16))
        elif op == 0x21:
            normal = p[0]
        elif op == 0x20:
            color = p[0]
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
            if current is None:
                raise NsbmdError("vertex outside BEGIN_VTXS")
            current["vertices"].append({"pos": tuple(pos), "uv": uv,
                                        "normal": normal, "color": color})
    return prims


def primitive_counts(prims: list[dict]) -> dict:
    """Vertex/polygon/triangle/quad totals as g3dcvtr counts them."""
    counts = {"numVertex": 0, "numPolygon": 0, "numTriangle": 0, "numQuad": 0}
    for prim in prims:
        n, kind = len(prim["vertices"]), prim["type"]
        counts["numVertex"] += n
        tris = n // 3 if kind == 0 else (max(n - 2, 0) if kind == 2 else 0)
        quads = n // 4 if kind == 1 else (max(n - 2, 0) // 2 if kind == 3 else 0)
        counts["numTriangle"] += tris
        counts["numQuad"] += quads
        counts["numPolygon"] += tris + quads
    return counts


# --- Render command list (SBC) ----------------------------------------------

def _sbc_size(data: bytes, pos: int) -> int:
    op = data[pos]
    base = op & 0x1F
    fixed = {0x00: 1, 0x01: 1, 0x02: 3, 0x03: 2, 0x04: 2, 0x05: 2, 0x0A: 9,
             0x0B: 1, 0x0C: 3, 0x0D: 3}
    if base in fixed:
        return fixed[base]
    if base in (0x06, 0x07, 0x08):
        return (4 if base == 0x06 else 2) + bool(op & 0x20) + bool(op & 0x40)
    if base == 0x09:
        return 3 + 3 * data[pos + 2]
    raise NsbmdError(f"unknown SBC opcode {op:#x} at {pos:#x}")


def decode_sbc(data: bytes) -> list[list[int]]:
    out, pos = [], 0
    while True:
        if pos >= len(data):
            raise NsbmdError("SBC has no RET")
        size = _sbc_size(data, pos)
        out.append(list(data[pos:pos + size]))
        pos += size
        if out[-1][0] == 0x01:
            break
    if any(data[pos:]) or len(data) - pos >= 4:
        raise NsbmdError("SBC padding after RET is not zero alignment padding")
    return out


def encode_sbc(commands: list[list[int]]) -> bytes:
    out = bytearray()
    for c in commands:
        out += bytes(c)
    _align4(out)
    return bytes(out)


# --- Nodes, materials, shapes -----------------------------------------------

def _decode_node(data: bytes, off: int) -> tuple[dict, int]:
    flag, m00 = struct.unpack_from("<Hh", data, off)
    node, pos = {"flag": flag, "m00": m00}, off + 4
    if not flag & 1:
        node["translation"] = list(struct.unpack_from("<3i", data, pos))
        pos += 12
    if not flag & 2:
        n = 2 if flag & 8 else 8
        node["rotation"] = list(struct.unpack_from(f"<{n}h", data, pos))
        pos += 2 * n
    if not flag & 4:
        node["scale"] = list(struct.unpack_from("<6i", data, pos))
        pos += 24
    return node, pos - off


def _encode_node(node: dict) -> bytes:
    flag = node["flag"]
    out = _pack("<Hh", flag, node["m00"])
    if not flag & 1:
        out += _pack("<3i", *node["translation"])
    if not flag & 2:
        out += _pack(f"<{2 if flag & 8 else 8}h", *node["rotation"])
    if not flag & 4:
        out += _pack("<6i", *node["scale"])
    return out


_MAT_FIELDS = ("diffAmb", "specEmi", "polyAttr", "polyAttrMask", "texImageParam",
               "texImageParamMask")
# Material flag bits (NNS_G3D_MATFLAG_*) that add optional trailing data.
MAT_TEXMTX_SCALEONE, MAT_TEXMTX_ROTZERO, MAT_TEXMTX_TRANSZERO = 0x2, 0x4, 0x8
MAT_EFFECTMTX = 0x2000


def _decode_material(data: bytes, off: int) -> dict:
    tag, size = struct.unpack_from("<HH", data, off)
    vals = struct.unpack_from("<6IHHHHii", data, off + 4)
    mat = dict(zip(_MAT_FIELDS, vals[:6]))
    mat.update(texPlttBase=vals[6], flag=vals[7], origWidth=vals[8], origHeight=vals[9],
               magW=vals[10], magH=vals[11])
    pos, flag = off + 0x2C, vals[7]
    if not flag & MAT_TEXMTX_SCALEONE:
        mat["texScale"] = list(struct.unpack_from("<2i", data, pos)); pos += 8
    if not flag & MAT_TEXMTX_ROTZERO:
        mat["texRotation"] = list(struct.unpack_from("<2h", data, pos)); pos += 4
    if not flag & MAT_TEXMTX_TRANSZERO:
        mat["texTranslation"] = list(struct.unpack_from("<2i", data, pos)); pos += 8
    if flag & MAT_EFFECTMTX:
        mat["effectMtx"] = list(struct.unpack_from("<16i", data, pos)); pos += 64
    if tag != 0 or size != pos - off:
        raise NsbmdError(f"material at {off:#x}: tag {tag} size {size} != parsed {pos - off}")
    return mat


def _encode_material(mat: dict) -> bytes:
    flag = mat["flag"]
    body = _pack("<6IHHHHii", *(mat[f] for f in _MAT_FIELDS), mat["texPlttBase"], flag,
                 mat["origWidth"], mat["origHeight"], mat["magW"], mat["magH"])
    if not flag & MAT_TEXMTX_SCALEONE:
        body += _pack("<2i", *mat["texScale"])
    if not flag & MAT_TEXMTX_ROTZERO:
        body += _pack("<2h", *mat["texRotation"])
    if not flag & MAT_TEXMTX_TRANSZERO:
        body += _pack("<2i", *mat["texTranslation"])
    if flag & MAT_EFFECTMTX:
        body += _pack("<16i", *mat["effectMtx"])
    return _pack("<HH", 0, 4 + len(body)) + body


def _decode_materials(data: bytes, base: int) -> dict:
    tex_ofs, pltt_ofs = struct.unpack_from("<HH", data, base)
    names, entries, size = read_dict(data, base + 4)
    if tex_ofs != 4 + size:
        raise NsbmdError("texture dictionary does not follow the material dictionary")
    out = {"materials": [], "textures": [], "palettes": []}
    for key, ofs in (("textures", tex_ofs), ("palettes", pltt_ofs)):
        tnames, tentries, tsize = read_dict(data, base + ofs)
        if key == "textures" and pltt_ofs != tex_ofs + tsize:
            raise NsbmdError("palette dictionary does not follow the texture dictionary")
        for name, e in zip(tnames, tentries):
            list_ofs, count, bound = struct.unpack("<HBB", e)
            out[key].append({"name": name, "bound": bound,
                             "materials": list(data[base + list_ofs:base + list_ofs + count])})
    for name, e in zip(names, entries):
        out["materials"].append({"name": name, **_decode_material(data, base + _u32(e, 0))})
    return out


def _encode_materials(block: dict) -> bytes:
    mats = block["materials"]
    mat_dict = dict_size(len(mats), 4)
    tex_dict = dict_size(len(block["textures"]), 4)
    pltt_dict = dict_size(len(block["palettes"]), 4)
    pos = 4 + mat_dict + tex_dict + pltt_dict
    lists, list_entries = bytearray(), {}
    for key in ("textures", "palettes"):
        list_entries[key] = []
        for t in block[key]:
            if not 0 < len(t["materials"]) < 256:
                raise NsbmdError(f"{key[:-1]} {t['name']} must be used by 1..255 materials")
            list_entries[key].append(_pack("<HBB", pos + len(lists), len(t["materials"]),
                                           t.get("bound", 0)))
            lists += bytes(t["materials"])
    _align4(lists)
    mat_pos, mat_entries, mat_blobs = pos + len(lists), [], bytearray()
    for m in mats:
        mat_entries.append(_pack("<I", mat_pos + len(mat_blobs)))
        mat_blobs += _encode_material(m)
    out = bytearray(_pack("<HH", 4 + mat_dict, 4 + mat_dict + tex_dict))
    out += build_dict([m["name"] for m in mats], mat_entries, 4)
    out += build_dict([t["name"] for t in block["textures"]], list_entries["textures"], 4)
    out += build_dict([t["name"] for t in block["palettes"]], list_entries["palettes"], 4)
    out += lists + mat_blobs
    return bytes(out)


def _decode_shapes(data: bytes, base: int) -> list[dict]:
    names, entries, _ = read_dict(data, base)
    shapes = []
    for name, e in zip(names, entries):
        hdr = base + _u32(e, 0)
        tag, hsize, flag, dl_ofs, dl_size = struct.unpack_from("<HHIII", data, hdr)
        if tag != 0 or hsize != 16:
            raise NsbmdError(f"shape {name}: unexpected header {tag}/{hsize}")
        dl = data[hdr + dl_ofs:hdr + dl_ofs + dl_size]
        shapes.append({"name": name, "flag": flag, "dl": decode_dl(dl)})
    return shapes


def _encode_shapes(shapes: list[dict]) -> bytes:
    head = dict_size(len(shapes), 4)
    dls = [encode_dl(s["dl"]) for s in shapes]
    hdr_pos = head
    dl_pos = head + 16 * len(shapes)
    entries, headers, blob = [], bytearray(), bytearray()
    for i, (s, dl) in enumerate(zip(shapes, dls)):
        here = hdr_pos + 16 * i
        entries.append(_pack("<I", here))
        headers += _pack("<HHIII", 0, 16, s["flag"], dl_pos + len(blob) - here, len(dl))
        blob += dl
    return build_dict([s["name"] for s in shapes], entries, 4) + bytes(headers) + bytes(blob)


# --- Model and file ---------------------------------------------------------

_INFO = ("sbcType", "scalingRule", "texMtxMode", "numNode", "numMat", "numShp",
         "firstUnusedMtxStackId", "dummy", "posScale", "invPosScale", "numVertex",
         "numPolygon", "numTriangle", "numQuad")
_INFO_FMT = "<8BiiHHHH"
_BOX_FMT = "<6hii"


def _decode_model(data: bytes, off: int, name: str) -> dict:
    size, sbc, mat, shp, evp = struct.unpack_from("<5I", data, off)
    info = dict(zip(_INFO, struct.unpack_from(_INFO_FMT, data, off + 0x14)))
    box = struct.unpack_from(_BOX_FMT, data, off + 0x2C)
    info["box"] = list(box[:6])
    info["boxPosScale"], info["boxInvPosScale"] = box[6], box[7]
    node_names, node_entries, node_dict = read_dict(data, off + 0x40)
    nodes, pos = [], 0x40 + node_dict
    for nname, e in zip(node_names, node_entries):
        if 0x40 + _u32(e, 0) != pos:
            raise NsbmdError(f"node {nname} data is not packed after the node dictionary")
        node, n = _decode_node(data, off + pos)
        nodes.append({"name": nname, **node})
        pos += n
    if sbc != pos:
        raise NsbmdError("SBC does not follow the node data")
    model = {"name": name, "info": info, "nodes": nodes,
             "sbc": decode_sbc(data[off + sbc:off + mat])}
    model.update(_decode_materials(data, off + mat))
    model["shapes"] = _decode_shapes(data, off + shp)
    model["envelopes"] = data[off + evp:off + size].hex()
    return model


def _encode_model(model: dict) -> bytes:
    info = model["info"]
    nodes = model["nodes"]
    node_blobs = [_encode_node(n) for n in nodes]
    node_dict = dict_size(len(nodes), 4)
    entries, pos = [], node_dict
    for blob in node_blobs:
        entries.append(_pack("<I", pos))
        pos += len(blob)
    nodes_part = build_dict([n["name"] for n in nodes], entries, 4) + b"".join(node_blobs)
    sbc = encode_sbc(model["sbc"])
    mats = _encode_materials(model)
    shapes = _encode_shapes(model["shapes"])
    evp_blob = bytes.fromhex(model.get("envelopes", ""))
    o_sbc = 0x40 + len(nodes_part)
    o_mat = o_sbc + len(sbc)
    o_shp = o_mat + len(mats)
    o_evp = o_shp + len(shapes)
    size = o_evp + len(evp_blob)
    head = _pack("<5I", size, o_sbc, o_mat, o_shp, o_evp)
    head += _pack(_INFO_FMT, *(info[k] for k in _INFO))
    head += _pack(_BOX_FMT, *info["box"], info["boxPosScale"], info["boxInvPosScale"])
    return head + nodes_part + sbc + mats + shapes + evp_blob


def parse(data: bytes) -> dict:
    magic, bom, version, size, hsize, nsec = struct.unpack_from("<4sHHIHH", data)
    if magic != b"BMD0" or bom != 0xFEFF or hsize != 16 or size != len(data):
        raise NsbmdError("not a BMD0 file (or its size field is wrong)")
    if nsec != 1:
        raise NsbmdError(f"{nsec} sections: only texture-less (MDL0-only) models are supported")
    mdl = _u32(data, 16)
    if data[mdl:mdl + 4] != b"MDL0" or mdl != 20 or _u32(data, mdl + 4) != len(data) - mdl:
        raise NsbmdError("MDL0 section must directly follow the header and fill the file")
    names, entries, dsize = read_dict(data, mdl + 8)
    models, pos = [], mdl + 8 + dsize
    for name, e in zip(names, entries):
        if mdl + _u32(e, 0) != pos:
            raise NsbmdError("models are not packed after the MDL0 dictionary")
        models.append(_decode_model(data, pos, name))
        pos += _u32(data, pos)
    if pos != len(data):
        raise NsbmdError(f"{len(data) - pos} trailing bytes after the last model")
    return {"version": version, "models": models}


def write(spec: dict) -> bytes:
    blobs = [_encode_model(m) for m in spec["models"]]
    mdl_dict = dict_size(len(blobs), 4)
    entries, pos = [], 8 + mdl_dict
    for b in blobs:
        entries.append(_pack("<I", pos))
        pos += len(b)
    section = build_dict([m["name"] for m in spec["models"]], entries, 4) + b"".join(blobs)
    section = b"MDL0" + _pack("<I", 8 + len(section)) + section
    total = 20 + len(section)
    return _pack("<4sHHIHHI", b"BMD0", 0xFEFF, spec.get("version", 2), total, 16, 1, 20) + section


# --- Area texture sets (NSBTX, a/0/4/4) -------------------------------------

def texture_set(nsbtx: bytes) -> dict:
    """Texture names with sizes, and palette names, from a BTX0/TEX0 file."""
    if nsbtx[:4] != b"BTX0":
        raise NsbmdError("not a BTX0 file")
    tex0 = _u32(nsbtx, 16)
    if nsbtx[tex0:tex0 + 4] != b"TEX0":
        raise NsbmdError("BTX0 has no TEX0 section")
    names, entries, _ = read_dict(nsbtx, tex0 + _u16(nsbtx, tex0 + 0x0E))
    textures = {}
    for name, e in zip(names, entries):
        param = _u32(e, 0)
        textures[name] = {"width": 8 << ((param >> 20) & 7), "height": 8 << ((param >> 23) & 7),
                          "format": (param >> 26) & 7}
    palettes, _, _ = read_dict(nsbtx, tex0 + _u32(nsbtx, tex0 + 0x34))
    return {"textures": textures, "palettes": palettes}


# --- Generic static-model builder -------------------------------------------

# Hardware caps per frame (GBATEK RAM_COUNT) and the largest vanilla chunk.
DS_MAX_POLYGONS, DS_MAX_VERTICES = 2048, 6144
VANILLA_MAX = {"numPolygon": 1706, "numVertex": 4854, "bytes": 61420}

# Most common vanilla ground material: light 0, modulate, front faces, fog,
# alpha 31; diffuse 0x6739 (+set vertex color), ambient 0x7FFF; repeat S/T.
NODE_FLAG = 0xF807  # identity translation/rotation/scale, as vanilla chunks
MAT_FLAG = 0x1FCE   # no texture matrix; diffuse/ambient/... and pltt base present


def make_material(name: str, texture: str | None = None, palette: str | None = None,
                  width: int = 0, height: int = 0, lit: bool = True, alpha: int = 31,
                  double_sided: bool = False, repeat=(True, True), flip=(False, False)) -> dict:
    if not 1 <= alpha <= 31:
        raise NsbmdError(f"material {name}: alpha must be 1..31 (0 is wireframe)")
    if bool(texture) != bool(palette):
        raise NsbmdError(f"material {name}: give both texture and palette, or neither")
    poly = (1 if lit else 0) | 0x80 | (0x40 if double_sided else 0) | 0x8000 | (alpha << 16)
    tip = 0
    if texture:
        tip = (repeat[0] << 16) | (repeat[1] << 17) | (flip[0] << 18) | (flip[1] << 19)
    return {"name": name, "diffAmb": 0x7FFFE739, "specEmi": 0, "polyAttr": poly,
            "polyAttrMask": 0x3F1FF8FF, "texImageParam": tip, "texImageParamMask": 0xFFFFFFFF,
            "texPlttBase": 0, "flag": MAT_FLAG, "origWidth": width if texture else 0,
            "origHeight": height if texture else 0, "magW": FX, "magH": FX,
            "texture": texture, "palette": palette}


def _pow2_scale(max_abs: float) -> int:
    """Smallest fx32 scale 1.0 * 2^k (k >= 0) so max_abs fits a 4.12 fx16."""
    k = 0
    while max_abs * FX * FX / (FX << k) > 32767:
        k += 1
    return FX << k


def _raw_pos(v: float, scale: int) -> int:
    return round(v * FX * FX / scale)


def _pack_normal(n) -> int:
    length = math.sqrt(sum(c * c for c in n)) or 1.0
    q = [max(-512, min(511, round(c / length * 512))) for c in n]
    return (q[0] & 0x3FF) | ((q[1] & 0x3FF) << 10) | ((q[2] & 0x3FF) << 20)


def _pack_uv(uv) -> int:
    s, t = (round(c * 16) for c in uv)
    if not (-32768 <= s <= 32767 and -32768 <= t <= 32767):
        raise NsbmdError(f"texture coordinate {uv} exceeds the 12.4 range (+-2048 texels)")
    return (s & 0xFFFF) | ((t & 0xFFFF) << 16)


def _vertex_cmds(v: dict, scale: int, state: dict) -> list[list[int]]:
    out = []
    if v.get("uv") is not None:
        raw = _pack_uv(v["uv"])
        if state.get("uv") != raw:
            out.append([0x22, raw]); state["uv"] = raw
    normal = v.get("normalRaw", _pack_normal(v["normal"]) if v.get("normal") is not None else None)
    if normal is not None and state.get("normal") != normal:
        out.append([0x21, normal]); state["normal"] = normal
    color = v.get("colorRaw")
    if color is None and v.get("color") is not None:
        r, g, b = v["color"]
        color = r | (g << 5) | (b << 10)
    if color is not None and state.get("color") != color:
        out.append([0x20, color]); state["color"] = color
    x, y, z = (_raw_pos(c, scale) for c in v["pos"])
    if any(not -32768 <= c <= 32767 for c in (x, y, z)):
        raise NsbmdError(f"vertex {v['pos']} does not fit the position scale")
    if all(c % 64 == 0 and -32768 <= c <= 32704 for c in (x, y, z)):
        out.append([0x24, ((x >> 6) & 0x3FF) | (((y >> 6) & 0x3FF) << 10) | (((z >> 6) & 0x3FF) << 20)])
    else:
        out.append([0x23, (x & 0xFFFF) | ((y & 0xFFFF) << 16), z & 0xFFFF])
    return out


def _mesh_dl(mesh: dict, scale: int) -> tuple[list[list[int]], int]:
    cmds, flag = [], 0
    for kind, key, size in ((1, "quads", 4), (0, "triangles", 3)):
        polys = mesh.get(key) or []
        if not polys:
            continue
        cmds.append([0x40, kind])
        state: dict = {}
        for poly in polys:
            if len(poly) != size:
                raise NsbmdError(f"{key} entries need {size} vertices")
            for v in poly:
                flag |= (1 if v.get("normal") is not None or "normalRaw" in v else 0)
                flag |= (2 if v.get("color") is not None or "colorRaw" in v else 0)
                flag |= (4 if v.get("uv") is not None else 0)
                cmds += _vertex_cmds(v, scale, state)
        cmds.append([0x41])
    while len(cmds) % 4:
        cmds.append([0])
    cmds += [[0]] * 4  # vanilla display lists end with one all-NOP word
    return cmds, flag


def build_model(name: str, materials: list[dict], meshes: list[dict],
                pos_scale: int | None = None, node_name: str = "chunk") -> dict:
    """Return a parse()-shaped spec for one static single-node model.

    materials: make_material() dicts (keys "texture"/"palette" name the area
    NSBTX entries). meshes: [{"material": index, "quads": [[v]*4],
    "triangles": [[v]*3]}], vertex = {"pos": (x, y, z) world units,
    "uv": (s, t) texels, "normal": (x, y, z) or "color": (r, g, b) 0..31}.
    One shape per mesh, drawn in order. Quad winding: counter-clockwise seen
    from the front (vanilla upward faces: (b-a) x (c-a) points +y).
    """
    if not materials or not meshes:
        raise NsbmdError("a model needs at least one material and one mesh")
    coords = [c for m in meshes for key in ("quads", "triangles") for p in m.get(key) or []
              for v in p for c in v["pos"]]
    if pos_scale is None:
        pos_scale = _pow2_scale(max(abs(c) for c in coords))
    shapes = []
    for i, mesh in enumerate(meshes):
        if not 0 <= mesh["material"] < len(materials):
            raise NsbmdError(f"mesh {i} references material {mesh['material']}")
        dl, flag = _mesh_dl(mesh, pos_scale)
        shapes.append({"name": f"polygon{i}", "flag": flag, "dl": dl})
    prims = [p for s in shapes for p in dl_primitives(s["dl"])]
    counts = primitive_counts(prims)
    world = [[c * pos_scale / FX / FX for c in v["pos"]] for p in prims for v in p["vertices"]]
    lo = [min(w[k] for w in world) for k in range(3)]
    hi = [max(w[k] for w in world) for k in range(3)]
    k = 0
    while True:
        bps = FX << k
        box_min = [math.floor(v * FX * FX / bps) for v in lo]
        box_size = [math.ceil(hi[j] * FX * FX / bps) - box_min[j] for j in range(3)]
        if all(-32768 <= v <= 32767 for v in box_min + box_size):
            break
        k += 1
    info = {"sbcType": 0, "scalingRule": 0, "texMtxMode": 0, "numNode": 1,
            "numMat": len(materials), "numShp": len(shapes), "firstUnusedMtxStackId": 1,
            "dummy": 0, "posScale": pos_scale, "invPosScale": FX * FX // pos_scale, **counts,
            "box": box_min + box_size, "boxPosScale": bps, "boxInvPosScale": FX * FX // bps}
    sbc = [[0x26, 0, 0, 0, 0], [0x02, 0, 1], [0x0B]]
    for i, mesh in enumerate(meshes):
        sbc += [[0x04, mesh["material"]], [0x05, i]]
    sbc += [[0x2B], [0x01]]
    mats, textures, palettes = [], {}, {}
    for i, m in enumerate(materials):
        mats.append({k: v for k, v in m.items() if k not in ("texture", "palette")})
        if m.get("texture"):
            textures.setdefault(m["texture"], []).append(i)
            palettes.setdefault(m["palette"], []).append(i)
    model = {"name": name, "info": info,
             "nodes": [{"name": node_name, "flag": NODE_FLAG, "m00": FX}], "sbc": sbc,
             "materials": mats,
             "textures": [{"name": n, "bound": 0, "materials": v} for n, v in sorted(textures.items())],
             "palettes": [{"name": n, "bound": 0, "materials": v} for n, v in sorted(palettes.items())],
             "shapes": shapes, "envelopes": ""}
    return {"version": 2, "models": [model]}


# --- Validation -------------------------------------------------------------

def validate(data: bytes, texset: dict | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a single-model NSBMD."""
    errors, warnings = [], []
    try:
        spec = parse(data)
    except NsbmdError as error:
        return [f"does not parse: {error}"], []
    if write(spec) != data:
        errors.append("parse/write is not byte-identical")
    for model in spec["models"]:
        info = model["info"]
        if info["numMat"] != len(model["materials"]) or info["numShp"] != len(model["shapes"]):
            errors.append("numMat/numShp do not match the dictionaries")
        if info["numNode"] != len(model["nodes"]):
            errors.append("numNode does not match the node dictionary")
        for c in model["sbc"]:
            base = c[0] & 0x1F
            if base == 0x04 and c[1] >= len(model["materials"]):
                errors.append(f"SBC MAT {c[1]} out of range")
            if base == 0x05 and c[1] >= len(model["shapes"]):
                errors.append(f"SBC SHP {c[1]} out of range")
        prims = []
        for s in model["shapes"]:
            depth = 0
            for c in s["dl"]:
                depth += c[0] == 0x40
                depth -= c[0] == 0x41
                if depth not in (0, 1):
                    errors.append(f"shape {s['name']}: unbalanced BEGIN_VTXS/END_VTXS")
                    break
            try:
                ps = dl_primitives(s["dl"])
            except NsbmdError as error:
                errors.append(f"shape {s['name']}: {error}")
                continue
            for p in ps:
                n, kind = len(p["vertices"]), p["type"]
                if (kind == 0 and n % 3) or (kind == 1 and n % 4) or (kind == 2 and n < 3) \
                        or (kind == 3 and (n < 4 or n % 2)):
                    errors.append(f"shape {s['name']}: primitive type {kind} has {n} vertices")
            prims += ps
        counts = primitive_counts(prims)
        for key, value in counts.items():
            if info[key] != value:
                errors.append(f"info {key}={info[key]} but display lists hold {value}")
        if counts["numPolygon"] > DS_MAX_POLYGONS or counts["numVertex"] > DS_MAX_VERTICES:
            errors.append(f"{counts} exceeds one frame's hardware capacity")
        if counts["numPolygon"] > VANILLA_MAX["numPolygon"]:
            warnings.append(f"{counts['numPolygon']} polygons > vanilla max {VANILLA_MAX['numPolygon']}")
        if counts["numVertex"] > VANILLA_MAX["numVertex"]:
            warnings.append(f"{counts['numVertex']} vertices > vanilla max {VANILLA_MAX['numVertex']}")
        if texset is not None:
            for t in model["textures"]:
                if t["name"] not in texset["textures"]:
                    errors.append(f"texture {t['name']} is not in the area NSBTX")
            for p in model["palettes"]:
                if p["name"] not in texset["palettes"]:
                    errors.append(f"palette {p['name']} is not in the area NSBTX")
    if len(data) > VANILLA_MAX["bytes"]:
        warnings.append(f"{len(data)} bytes > largest vanilla chunk model ({VANILLA_MAX['bytes']})")
    return errors, warnings


# --- Grid generator ---------------------------------------------------------

GRID, TILE, HALF = 32, 16, 256


def _material_for(key: str, spec: dict, texset: dict | None) -> dict:
    m = spec["materials"][key]
    width = height = 0
    if m.get("texture"):
        if texset is not None:
            if m["texture"] not in texset["textures"]:
                raise NsbmdError(f"material {key}: texture {m['texture']!r} is not in the area NSBTX")
            if m["palette"] not in texset["palettes"]:
                raise NsbmdError(f"material {key}: palette {m['palette']!r} is not in the area NSBTX")
            width = texset["textures"][m["texture"]]["width"]
            height = texset["textures"][m["texture"]]["height"]
        else:
            width, height = m["size"]
    return make_material(key, m.get("texture"), m.get("palette"), width, height,
                         lit=m.get("lit", True), alpha=m.get("alpha", 31),
                         double_sided=m.get("doubleSided", False))


def _rects(keys, heights, fixed, max_span):
    """Greedy-merge flat, same-material, same-height tiles into rectangles."""
    used = [[False] * GRID for _ in range(GRID)]
    out = []
    for z in range(GRID):
        for x in range(GRID):
            if used[z][x] or keys[z][x] is None or (x, z) in fixed:
                continue
            h = heights[z][x]
            flat = h == heights[z][x + 1] == heights[z + 1][x] == heights[z + 1][x + 1]

            def ok(tx, tz):
                return (not used[tz][tx] and (tx, tz) not in fixed and keys[tz][tx] == keys[z][x]
                        and heights[tz][tx] == h == heights[tz][tx + 1] == heights[tz + 1][tx]
                        == heights[tz + 1][tx + 1])

            w = d = 1
            if flat:
                mx, mz = max_span[keys[z][x]]
                while x + w < GRID and w < mx and ok(x + w, z):
                    w += 1
                while z + d < GRID and d < mz and all(ok(tx, z + d) for tx in range(x, x + w)):
                    d += 1
            for tz in range(z, z + d):
                for tx in range(x, x + w):
                    used[tz][tx] = True
            out.append((x, z, w, d))
    return out


def grid_spec_to_model(spec: dict, texset: dict | None) -> dict:
    """Build a model spec from the grid description (see nsbmd.md)."""
    keys = spec.get("tiles")
    if keys is None:
        keys = [[spec.get("fill")] * GRID for _ in range(GRID)]
    if len(keys) != GRID or any(len(row) != GRID for row in keys):
        raise NsbmdError("tiles must be 32 rows of 32 material keys (null = no floor)")
    keys = [[k or None for k in row] for row in keys]
    base = spec.get("height", 0)
    heights = spec.get("heights") or [[base] * (GRID + 1) for _ in range(GRID + 1)]
    if len(heights) != GRID + 1 or any(len(r) != GRID + 1 for r in heights):
        raise NsbmdError("heights must be 33 rows of 33 corner heights")
    order = sorted(spec["materials"])
    index = {k: i for i, k in enumerate(order)}
    materials = [_material_for(k, spec, texset) for k in order]
    reps = {}
    for k in order:
        r = spec["materials"][k].get("tilesPerRepeat", 1)
        reps[k] = (r, r) if isinstance(r, int) else tuple(r)
    for row in keys:
        for k in row:
            if k is not None and k not in index:
                raise NsbmdError(f"tile material {k!r} is not defined")

    def span(k):
        m = materials[index[k]]
        out = []
        for size, rep in ((m["origWidth"], reps[k][0]), (m["origHeight"], reps[k][1])):
            if not size:
                out.append(GRID)
                continue
            # texel span of rep-aligned merged run must stay below 2048
            out.append(max(1, (2047 * rep) // size - (rep - 1)))
        return tuple(out)

    max_span = {k: span(k) for k in order}
    meshes = {k: [] for k in order}

    def vertex(k, cx, cz, h, ux, uz, normal):
        m = materials[index[k]]
        v = {"pos": (-HALF + TILE * cx, h, -HALF + TILE * cz)}
        if m["origWidth"]:
            v["uv"] = ((cx - ux) / reps[k][0] * m["origWidth"], (cz - uz) / reps[k][1] * m["origHeight"])
        if spec["materials"][k].get("lit", True):
            v["normal"] = normal
        else:
            v["color"] = tuple(spec["materials"][k].get("color", (31, 31, 31)))
        return v

    def quad(k, corners, uv_origin, explicit_uv=None):
        # corners: [(cx, cz, h)] in order nw, sw, se, ne (front faces up)
        p = [(-HALF + TILE * cx, h, -HALF + TILE * cz) for cx, cz, h in corners]
        d1 = [p[2][i] - p[0][i] for i in range(3)]
        d2 = [p[3][i] - p[1][i] for i in range(3)]
        normal = (d1[1] * d2[2] - d1[2] * d2[1], d1[2] * d2[0] - d1[0] * d2[2],
                  d1[0] * d2[1] - d1[1] * d2[0])
        if normal[1] < 0:
            normal = tuple(-c for c in normal)
        vs = [vertex(k, cx, cz, h, *uv_origin, normal) for cx, cz, h in corners]
        if explicit_uv is not None:
            for v, uv in zip(vs, explicit_uv):
                v["uv"] = tuple(uv)
        meshes[k].append(vs)

    fixed = {}
    for q in spec.get("quads", []):
        if q["material"] not in index:
            raise NsbmdError(f"quad material {q['material']!r} is not defined")
        fixed[(q["x"], q["z"])] = q
    merge = spec.get("merge", True)
    rects = _rects(keys, heights, set(fixed), max_span if merge else {k: (1, 1) for k in order})
    for x, z, w, d in rects:
        k = keys[z][x]
        ux, uz = x - x % reps[k][0], z - z % reps[k][1]
        quad(k, [(x, z, heights[z][x]), (x, z + d, heights[z + d][x]),
                 (x + w, z + d, heights[z + d][x + w]), (x + w, z, heights[z][x + w])], (ux, uz))
    for (x, z), q in sorted(fixed.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        k = q["material"]
        nw, ne, se, sw = q.get("heights", [heights[z][x], heights[z][x + 1],
                                           heights[z + 1][x + 1], heights[z + 1][x]])
        ux, uz = x - x % reps[k][0], z - z % reps[k][1]
        uv = q.get("uv")  # [nw, ne, se, sw] texels
        quad(k, [(x, z, nw), (x, z + 1, sw), (x + 1, z + 1, se), (x + 1, z, ne)], (ux, uz),
             None if uv is None else [uv[0], uv[3], uv[2], uv[1]])
    mesh_list = [{"material": index[k], "quads": meshes[k]} for k in order if meshes[k]]
    return build_model(spec.get("name", "gen_chunk"), materials, mesh_list)


# --- Rebuilding vanilla geometry through the builder ------------------------

def _polygons(prim: dict) -> list[list[dict]]:
    vs, kind = prim["vertices"], prim["type"]
    if kind == 0:
        return [vs[i:i + 3] for i in range(0, len(vs) - 2, 3)]
    if kind == 1:
        return [vs[i:i + 4] for i in range(0, len(vs) - 3, 4)]
    if kind == 2:
        return [[vs[i], vs[i + 1], vs[i + 2]] if i % 2 == 0 else [vs[i + 1], vs[i], vs[i + 2]]
                for i in range(len(vs) - 2)]
    return [[vs[i], vs[i + 1], vs[i + 3], vs[i + 2]] for i in range(0, len(vs) - 3, 2)]


def _shape_materials(model: dict) -> list[tuple[int, int]]:
    out, mat = [], None
    for c in model["sbc"]:
        if c[0] & 0x1F == 0x04:
            mat = c[1]
        elif c[0] == 0x05:
            out.append((mat, c[1]))
    return out


def geometry(model: dict) -> dict:
    """{material name: sorted polygons}, positions in world units."""
    scale = model["info"]["posScale"]
    out = {}
    for mat, shp in _shape_materials(model):
        name = model["materials"][mat]["name"]
        for prim in dl_primitives(model["shapes"][shp]["dl"]):
            for poly in _polygons(prim):
                out.setdefault(name, []).append(tuple(
                    (tuple(c * scale / FX / FX for c in v["pos"]), v["uv"], v["normal"], v["color"])
                    for v in poly))
    return {k: sorted(v, key=repr) for k, v in out.items()}


def rebuild_vanilla(model: dict) -> dict:
    """Feed a parsed vanilla model's polygons and materials through build_model."""
    tex_of = {i: t["name"] for t in model["textures"] for i in t["materials"]}
    pal_of = {i: p["name"] for p in model["palettes"] for i in p["materials"]}
    materials = [{**m, "texture": tex_of.get(i), "palette": pal_of.get(i)}
                 for i, m in enumerate(model["materials"])]
    scale = model["info"]["posScale"]
    meshes = []
    for mat, shp in _shape_materials(model):
        mesh = {"material": mat, "quads": [], "triangles": []}
        for prim in dl_primitives(model["shapes"][shp]["dl"]):
            for poly in _polygons(prim):
                vs = []
                for v in poly:
                    nv = {"pos": tuple(c * scale / FX / FX for c in v["pos"]), "uv": None}
                    if v["uv"] is not None:
                        nv["uv"] = (v["uv"][0] / 16, v["uv"][1] / 16)
                    if v["normal"] is not None:
                        nv["normalRaw"] = v["normal"]
                    if v["color"] is not None:
                        nv["colorRaw"] = v["color"]
                    vs.append(nv)
                mesh["quads" if len(vs) == 4 else "triangles"].append(vs)
        meshes.append(mesh)
    return build_model(model["name"], materials, meshes, pos_scale=scale,
                       node_name=model["nodes"][0]["name"])


# --- Command line -----------------------------------------------------------

def _rom(path: str):
    from .world import RomSource
    return RomSource(Path(path))


def _land_models(src) -> list[bytes]:
    from . import codecs, narc
    return [codecs.decode_land_model(m) for m in narc.members(src.read("a/0/6/5"))]


def _area_texset(src, area: int) -> dict:
    from . import codecs, narc
    areas = narc.members(src.read("a/0/4/2"))
    tileset = codecs.decode_area(areas[area])["mapTileset"]
    return texture_set(narc.members(src.read("a/0/4/4"))[tileset])


def cmd_roundtrip(args) -> int:
    models = _land_models(_rom(args.rom))
    failures = []
    for i, data in enumerate(models):
        try:
            spec = json.loads(json.dumps(parse(data)))
            if write(spec) != data:
                failures.append((i, "bytes differ"))
        except NsbmdError as error:
            failures.append((i, str(error)))
    print(f"nsbmd round-trip: {len(models) - len(failures)}/{len(models)} land_data models identical")
    for i, why in failures:
        print(f"  land {i}: {why}")
    return 1 if failures else 0


def cmd_generate(args) -> int:
    src = _rom(args.rom)
    texset = _area_texset(src, args.area)
    spec = json.loads(Path(args.spec).read_text())
    data = write(grid_spec_to_model(spec, texset))
    errors, warnings = validate(data, texset)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    if errors:
        return 1
    Path(args.out).write_bytes(data)
    info = parse(data)["models"][0]["info"]
    print(f"wrote {args.out}: {len(data)} bytes, {info['numPolygon']} polygons, "
          f"{info['numVertex']} vertices, {info['numMat']} materials")
    return 0


def cmd_rebuild(args) -> int:
    data = _land_models(_rom(args.rom))[args.land]
    model = parse(data)["models"][0]
    rebuilt = write(rebuild_vanilla(model))
    same = geometry(parse(rebuilt)["models"][0]) == geometry(model)
    print(f"land {args.land}: vanilla {len(data)} bytes, rebuilt {len(rebuilt)} bytes, "
          f"geometry {'identical' if same else 'DIFFERENT'}")
    if args.out:
        Path(args.out).write_bytes(rebuilt)
    return 0 if same else 1


def cmd_info(args) -> int:
    data = Path(args.file).read_bytes()
    spec = parse(data)
    for m in spec["models"]:
        print(json.dumps({"name": m["name"], "info": m["info"],
                          "materials": [x["name"] for x in m["materials"]],
                          "textures": [x["name"] for x in m["textures"]],
                          "palettes": [x["name"] for x in m["palettes"]],
                          "shapes": len(m["shapes"])}, indent=1))
    errors, warnings = validate(data, _area_texset(_rom(args.rom), args.area)
                                if args.area is not None else None)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    return 1 if errors else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -B -m tools.maps.nsbmd", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", default=str(Path(__file__).resolve().parents[2] / "rom.nds"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("roundtrip").set_defaults(func=cmd_roundtrip)
    g = sub.add_parser("generate")
    g.add_argument("--area", type=int, required=True, help="area data id (a/0/4/2 member)")
    g.add_argument("--spec", required=True)
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_generate)
    r = sub.add_parser("rebuild")
    r.add_argument("--land", type=int, required=True)
    r.add_argument("--out")
    r.set_defaults(func=cmd_rebuild)
    i = sub.add_parser("info")
    i.add_argument("file")
    i.add_argument("--area", type=int)
    i.set_defaults(func=cmd_info)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

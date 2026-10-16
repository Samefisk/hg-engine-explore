"""Tests for the offline renderer and the review page.

  python3 -B -m unittest tools.maps.test_render

Synthetic tests always run; ROM-backed ones need rom.nds in the repo root.
"""

from __future__ import annotations

import json
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import numpy as np

from . import render

ROM = render.REPO / "rom.nds"


def _material(front=True, back=False, alpha=1.0, image=None, translucent=None):
    return {"name": "m", "polyAttr": 0, "image": image, "repeat": (1, 1), "flip": (0, 0),
            "scale": (1.0, 1.0), "alpha": alpha, "front": front, "back": back,
            "translucent": alpha < 1 if translucent is None else translucent,
            "diffuse": np.ones(3, np.float32)}


def _mesh(tris, front=True, back=False, alpha=1.0, color=(1.0, 1.0, 1.0)):
    mesh = render.Mesh()
    mesh.materials.append(_material(front, back, alpha))
    for tri in tris:
        mesh.pos.append(tri)
        mesh.uv.append([(0, 0)] * 3)
        mesh.color.append([color] * 3)
        mesh.normal.append([(0, 1, 0)] * 3)
        mesh.mat.append(0)
    return mesh


def _top_camera(size=(32, 32)):
    return render.Camera((0, 100, 0), (0, 0, 0), size, ortho_height=32)


class CameraTest(unittest.TestCase):
    def test_default_field_preset(self):
        p = render.camera_preset(0)  # gFieldCameraPresets[0]
        self.assertAlmostEqual(p["distance"], 0x29AEC1 / 4096)
        self.assertEqual(p["angle"], (0xDD62, 0, 0))
        self.assertAlmostEqual(p["near"], 150)
        self.assertAlmostEqual(p["far"], 1200)
        self.assertFalse(p["orthographic"])

    def test_field_camera_looks_north_and_down(self):
        cam = render.Camera.field((0, 0, 0), render.camera_preset(0))
        self.assertGreater(cam.pos[1], 0)  # above
        self.assertGreater(cam.pos[2], 0)  # south of the target
        self.assertGreater(cam.right[0], 0.99)  # east is to the right
        x, y = cam.screen_of((0, 0, 0))
        self.assertAlmostEqual(x, 128)
        self.assertAlmostEqual(y, 96)


class RasterTest(unittest.TestCase):
    # From above, north (-z) is the top of the image; this winding is
    # counter-clockwise on screen: a front face, as vanilla ground is.
    FRONT = [[-8, 0, -8], [-8, 0, 8], [8, 0, -8]]

    def test_front_face_drawn_back_face_culled(self):
        image = render.rasterize(_mesh([self.FRONT]), _top_camera())
        self.assertTrue(image.any())
        back = [self.FRONT[0], self.FRONT[2], self.FRONT[1]]
        self.assertFalse(render.rasterize(_mesh([back]), _top_camera()).any())
        self.assertTrue(render.rasterize(_mesh([back], back=True), _top_camera()).any())

    def test_depth_keeps_the_nearer_triangle(self):
        low = [[x, 0, z] for x, _, z in self.FRONT]
        high = [[x, 5, z] for x, _, z in self.FRONT]
        mesh = _mesh([high, low])
        mesh.color[1] = [(1.0, 0.0, 0.0)] * 3  # low is red, drawn last
        image = render.rasterize(mesh, _top_camera())
        self.assertEqual(tuple(image[8, 8]), (255, 255, 255))

    def test_pick_returns_world_position_and_void(self):
        image, where = render.rasterize(_mesh([self.FRONT]), _top_camera(), pick=True)
        self.assertTrue(np.isnan(where[31, 31, 0]))  # outside the triangle: void
        x, z = where[10, 10]  # pixel centre 10.5 of 32 over -16..16
        self.assertAlmostEqual(x, -5.5, places=3)
        self.assertAlmostEqual(z, -5.5, places=3)

    def test_alpha_texels_blend_over_later_far_polygons(self):
        # A3I5/A5I3 materials go to the translucent pass (after all opaque ones).
        near = [[x, 5, z] for x, _, z in self.FRONT]
        mesh = _mesh([near, self.FRONT])
        half = np.ones((8, 8, 4), np.float32)
        half[..., 3] = 0.5
        mesh.materials.append(_material(image=half, translucent=True))
        mesh.mat[0] = 1
        mesh.color[1] = [(1.0, 0.0, 0.0)] * 3  # far, opaque red, listed last
        image = render.rasterize(mesh, _top_camera())
        self.assertEqual(image[10, 10, 0], 255)
        self.assertTrue(120 <= image[10, 10, 1] <= 135)

    def test_translucent_blends(self):
        image = render.rasterize(_mesh([self.FRONT], alpha=0.5), _top_camera())
        self.assertTrue(120 <= image[10, 10, 0] <= 135)


class TextureTest(unittest.TestCase):
    @staticmethod
    def _btx(fmt: int, texel: bytes, palette: list[int], w=8, h=8, c4=b"", c4idx=b"", transparent0=False):
        from . import nsbmd
        param = (0 << 0) | ((w.bit_length() - 4) << 20) | ((h.bit_length() - 4) << 23) | (fmt << 26) | (transparent0 << 29)
        tex_dict = nsbmd.build_dict(["t"], [struct.pack("<II", param, 0)], 8)
        pal_dict = nsbmd.build_dict(["p"], [struct.pack("<HH", 0, 0)], 4)
        pltt = b"".join(struct.pack("<H", c) for c in palette)
        head = 0x3C
        tex_ofs = head
        pal_dict_ofs = tex_ofs + len(tex_dict)
        data_ofs = pal_dict_ofs + len(pal_dict)
        c4_ofs = data_ofs + len(texel)
        c4i_ofs = c4_ofs + len(c4)
        pltt_ofs = c4i_ofs + len(c4idx)
        tex0 = bytearray(head)
        tex0[0:4] = b"TEX0"
        struct.pack_into("<H", tex0, 0x0E, tex_ofs)
        struct.pack_into("<I", tex0, 0x14, data_ofs)
        struct.pack_into("<I", tex0, 0x24, c4_ofs)
        struct.pack_into("<I", tex0, 0x28, c4i_ofs)
        struct.pack_into("<H", tex0, 0x34, pal_dict_ofs)
        struct.pack_into("<I", tex0, 0x38, pltt_ofs)
        body = bytes(tex0) + tex_dict + pal_dict + texel + c4 + c4idx + pltt
        return b"BTX0" + bytes(12) + struct.pack("<I", 20) + body

    def test_16_colour_with_transparent_zero(self):
        texel = bytes([0x10] * 32)  # 4bpp: low nibble first -> 0, 1, 0, 1, ...
        t = render.Textures(self._btx(3, texel, [0x7FFF, 0x001F] + [0] * 14, transparent0=True))
        img = t.image("t", "p")
        self.assertEqual(img.shape, (8, 8, 4))
        np.testing.assert_allclose(img[0, 0], [1, 1, 1, 0])
        np.testing.assert_allclose(img[0, 1], [1, 0, 0, 1])

    def test_a3i5(self):
        texel = bytes([(7 << 5) | 1] * 64)
        img = render.Textures(self._btx(1, texel, [0, 0x03E0] + [0] * 30)).image("t", "p")
        np.testing.assert_allclose(img[3, 3], [0, 1, 0, 1])

    def test_4x4_compressed_mode_3(self):
        texel = struct.pack("<I", 0b11100100 * 0x01010101) * 4  # row: 0, 1, 2, 3
        index = struct.pack("<H", 3 << 14) * 4
        img = render.Textures(self._btx(5, b"", [0x001F, 0x7C00, 0, 0], c4=texel, c4idx=index)).image("t", "p")
        np.testing.assert_allclose(img[0, 0, :3], [1, 0, 0])
        np.testing.assert_allclose(img[0, 1, :3], [0, 0, 1])
        np.testing.assert_allclose(img[0, 2, :3], [5 / 8, 0, 3 / 8])


@unittest.skipUnless(ROM.exists(), "needs rom.nds")
class VanillaTest(unittest.TestCase):
    def test_route_29_view_and_no_void(self):
        scene = render.MapScene(33, None)
        image = scene.view(624, 400)
        self.assertEqual(image.shape, (192, 256, 3))
        self.assertLess((image.sum(axis=2) == 0).mean(), 0.01)  # nothing black in a route
        self.assertEqual(render.voids(scene), {"top": [], "camera": []})

    def test_union_cave_has_no_void_beside_reachable_floor(self):
        self.assertEqual(render.voids(render.MapScene(107, None)), {"top": [], "camera": []})


@unittest.skipUnless(ROM.exists(), "needs rom.nds")
class ReviewTest(unittest.TestCase):
    def test_pages_and_defect_recording(self):
        from http.server import ThreadingHTTPServer
        from . import review
        from .style import lab
        page = review.Review(107, None)
        server = ThreadingHTTPServer(("127.0.0.1", 0), review.make_handler(page))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with tempfile.TemporaryDirectory() as tmp, mock.patch.object(lab, "DEFECTS", Path(tmp) / "d.jsonl"):
                state = json.load(urllib.request.urlopen(url + "/api/state"))
                self.assertEqual(state["counts"]["voidCamera"], 0)
                w, h = state["views"]["top"]["size"]
                picked = json.load(urllib.request.urlopen(f"{url}/api/pick?view=top&px={w / 2}&py={h / 2}"))
                self.assertIsNotNone(picked["tile"])
                self.assertIn("commands", picked["info"])
                bad = urllib.request.Request(url + "/api/defect", method="POST", data=b'{"x":1,"z":1,"note":"n"}',
                                             headers={"Content-Type": "text/plain"})
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(bad)
                req = urllib.request.Request(url + "/api/defect", method="POST",
                                             data=json.dumps({"x": 3, "z": 4, "note": "test"}).encode(),
                                             headers={"Content-Type": "application/json"})
                entry = json.load(urllib.request.urlopen(req))
                self.assertEqual((entry["map"], entry["x"], entry["z"]), (107, 3, 4))
                self.assertEqual(len(lab._read_jsonl(lab.DEFECTS)), 1)
                png = urllib.request.urlopen(url + "/view.png?x=8&z=8").read()
                self.assertTrue(png.startswith(b"\x89PNG"))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

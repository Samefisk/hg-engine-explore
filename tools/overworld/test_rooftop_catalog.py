"""Native-derived roof-mask regression controls; no live game acceptance.

The expected nodes were preserved from an independent plane-normal/edge ray
survey before the generator edit. They include missing roofs, concave holes,
low wall shelves, overhead signs/ornaments and a cross-block house placement.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import generate_overworld_wild_roof_catalog as g
from tools.narc_reader import NarcArchive

FIXTURES = ROOT / 'tools/overworld/fixtures/goldenrod_native_roofs.json'


def group_nodes(report, group):
    """Decode actual packed rows into world tile/height values for one prop."""
    name = group['name'].split('_')
    bx, by = int(name[1][1:]), int(name[2][1:])
    output = {}
    for row in report['instances']:
        if row['logical_group'] != group['id']:
            continue
        ox, oy = (bx-row['anchor_block_dx'])*32, (by-row['anchor_block_dy'])*32
        for y in range(row['min_y'], row['min_y']+row['height']):
            for x in range(row['min_x'], row['min_x']+row['width']):
                point = ox+x, oy+y
                if point in output and output[point] != row['height_fx32']:
                    raise AssertionError('overlapping roof heights differ')
                output[point] = row['height_fx32']
    return output


class RooftopCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((ROOT/'data/generated/overworld_wild_roof_catalog.json').read_text())
        cls.manifest = json.loads((ROOT/'data/overworld_wild_roof_catalog_manifest.json').read_text())
        cls.fixtures = json.loads(FIXTURES.read_text())['fixtures']
        cls.models = NarcArchive.from_file(ROOT/'base/root/a/0/4/0')
        cls.land = NarcArchive.from_file(ROOT/'base/root/a/0/6/5')

    def test_all_eleven_native_roofs_have_exact_nodes_heights_and_holes(self):
        self.assertEqual({row['modelId'] for row in self.fixtures}, {35,75,76,77,79,80,86,87,88,89,101})
        for row in self.fixtures:
            with self.subTest(model=row['modelId'], land=row['land'], obj=row['objectIndex']):
                group = next(item for item in self.report['logical_groups']
                    if item.get('source_land_data_id') == row['land']
                    and item.get('source_object_index') == row['objectIndex'])
                actual = group_nodes(self.report, group)
                self.assertEqual(actual, {(x,y):h for x,y,h in row['nodes']})
                self.assertTrue(all(tuple(point) not in actual for point in row['negatives']))
                self.assertEqual(group['mesh_fallback_node_count'], 0)
                if 'nativeMemberSha256' in row:
                    self.assertEqual(hashlib.sha256(self.models.files[row['modelId']]).hexdigest(), row['nativeMemberSha256'])
        # This roof belongs to land39 but lies in the next block (land41).
        house = next(row for row in self.fixtures if row['land']==39 and row['objectIndex']==11)
        self.assertTrue(all(352 <= y <= 354 for _x,y,_h in house['nodes']))
        # The valid upper GTS roof cap uses a height page above zero.
        gts = next(row for row in self.fixtures if row['modelId']==89)
        self.assertIn([316,345,0x116D00], gts['nodes'])

    def test_complex_generator_matches_independent_exact_native_oracle(self):
        for row in self.fixtures:
            raw = next(item for item in self.manifest['models'] if item['model_id']==row['modelId'])
            if raw['generation'] != 'mesh_faces':
                continue
            with self.subTest(model=row['modelId']):
                spec = g.verify_model_template(self.models, raw)
                placement = g.read_land_objects(self.land,row['land'])[row['objectIndex']]
                actual, _occluded = g.sample_native_roof_nodes_q4(self.models,spec,placement)
                group = next(item for item in self.report['logical_groups']
                    if item.get('source_land_data_id')==row['land'] and item.get('source_object_index')==row['objectIndex'])
                name = group['name'].split('_'); bx,by=int(name[1][1:]),int(name[2][1:])
                expected = {(x-bx*32,y-by*32):h//16 for x,y,h in row['nodes']}
                self.assertEqual(actual, expected)

    def test_named_model_template_is_reused_outside_goldenrod(self):
        row = next(item for item in self.fixtures if item['modelId']==87)
        original = next(item for item in self.report['logical_groups']
                        if item.get('model_id')==87 and item.get('source_land_data_id')==39)
        reused = next(item for item in self.report['logical_groups']
                      if item.get('model_id')==87 and item.get('source_land_data_id')==156)
        a, b = group_nodes(self.report, original), group_nodes(self.report, reused)
        # Both native prop phases are equal. Compare normalized shape and height,
        # not map-specific coordinates or generated group IDs.
        def normalized(nodes, placement_y):
            ox=min(x for x,_y in nodes); oy=min(y for _x,y in nodes)
            return {(x-ox,y-oy):h-placement_y for (x,y),h in nodes.items()}
        pa = g.read_land_objects(self.land,39)[12]
        pb = g.read_land_objects(self.land,156)[8]
        self.assertEqual(normalized(a,pa.y_fx32), normalized(b,pb.y_fx32))
        self.assertEqual(len(b), len(row['nodes']))

    def test_changed_native_selection_fails_closed(self):
        original = next(row for row in self.manifest['models'] if row['model_id']==89)
        cases = [dict(expected_face_count=1), dict(native_face_indices=[9999]),
                 dict(native_face_indices=[17,17]), dict(expected_material_names=['wrong']),
                 dict(require_topmost_mesh=False)]
        for changed in cases:
            with self.subTest(change=changed), self.assertRaises(RuntimeError):
                g.verify_model_template(self.models, dict(deepcopy(original), **changed))
        # Native vertical facade has no X/Z area and cannot be selected as roof.
        _name,_scale,faces=g.model_all_faces(self.models,89)
        vertical=next(i for i,(face,mat) in enumerate(faces)
                      if not g.face_has_projected_area(face) and 'kage' not in mat.lower())
        with self.assertRaisesRegex(RuntimeError, 'vertical or excluded'):
            g.verify_model_template(self.models, dict(original,native_face_indices=[vertical]))


if __name__ == '__main__':
    unittest.main()

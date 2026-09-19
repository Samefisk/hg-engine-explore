"""Host-only evidence storage integrity and size controls."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.devtools_evidence_stream import open_observations, load_observations


class EvidenceStreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_roundtrip_append_plain_and_gzip(self):
        rows = [{"frame": 1, "text": "æ雪", "samples": [1, 2]}, {"phase": "cleanup", "closed": True}]
        for suffix in (".jsonl", ".jsonl.gz"):
            with self.subTest(suffix=suffix):
                path = self.root / ("observations" + suffix)
                with open_observations(path, "xt") as stream:
                    stream.write(json.dumps(rows[0], ensure_ascii=False) + "\n")
                    stream.flush()
                with self.assertRaises(FileExistsError):
                    with open_observations(path, "xt"): pass
                with open_observations(path, "at") as stream:
                    stream.write(json.dumps(rows[1]) + "\n")
                self.assertEqual(load_observations(path), rows)
                with open_observations(path) as stream:
                    self.assertEqual([json.loads(line) for line in stream], rows)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_corruption_truncation_and_trailing_junk_rejected(self):
        good = gzip.compress(b'{"frame":1}\n', compresslevel=1)
        for name, content in (("empty-file", b""), ("crc", good[:-8] + bytes([good[-8] ^ 1]) + good[-7:]),
                ("truncated", good[:-1]), ("trailing", good + b"junk"),
                ("second-member", good + gzip.compress(b'{}\n')[:-2])):
            with self.subTest(name=name):
                path = self.root / "bad.jsonl.gz"; path.write_bytes(content)
                with self.assertRaisesRegex(ValueError, "invalid observation stream"):
                    load_observations(path)

    def test_invalid_text_json_and_nonobject_rejected(self):
        for raw in (b'\xff\n', b'{bad}\n', b'{} junk\n', b'[]\n', b'\n', b'{"x":NaN}\n'):
            for suffix in (".jsonl", ".jsonl.gz"):
                with self.subTest(raw=raw,suffix=suffix):
                    path = self.root / ("bad" + suffix)
                    path.write_bytes(gzip.compress(raw) if suffix.endswith("gz") else raw)
                    with self.assertRaises(ValueError): load_observations(path)

    def test_limits_are_decompressed_utf8_bytes_and_rows(self):
        path = self.root / "bounded.jsonl.gz"
        raw = '{"x":"雪"}\n'.encode("utf-8")
        path.write_bytes(gzip.compress(raw))
        with patch("tools.overworld.devtools_evidence_stream.MAX_LINE_BYTES", len(raw)):
            self.assertEqual(load_observations(path), [{"x":"雪"}])
        with patch("tools.overworld.devtools_evidence_stream.MAX_LINE_BYTES", len(raw)-1):
            with self.assertRaisesRegex(ValueError,"byte limit"): load_observations(path)
        path.write_bytes(gzip.compress(b'{}\n{}\n'))
        with patch("tools.overworld.devtools_evidence_stream.MAX_ROWS", 1):
            with self.assertRaisesRegex(ValueError,"row count"): load_observations(path)
        path.write_bytes(gzip.compress(b'x'*4096))
        with patch("tools.overworld.devtools_evidence_stream.MAX_LINE_BYTES", 32):
            with self.assertRaisesRegex(ValueError,"byte limit"): load_observations(path)

    def test_unknown_suffix_or_mode_rejected(self):
        with self.assertRaises(ValueError): load_observations(self.root / "x.gz")
        with self.assertRaises(ValueError):
            with open_observations(self.root / "x.jsonl.gz", "wt"): pass


if __name__ == "__main__": unittest.main()

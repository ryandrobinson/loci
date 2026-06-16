import tempfile
import unittest
from pathlib import Path

from loci.memory.okf import Bundle, Concept, OKFError, parse_frontmatter, dump_frontmatter


class FrontmatterTest(unittest.TestCase):
    def test_roundtrip_scalars_and_list(self):
        meta = {"type": "fact", "title": "A thing", "tags": ["x", "y"]}
        text = dump_frontmatter(meta) + "\n\nbody here\n"
        parsed, body = parse_frontmatter(text)
        self.assertEqual(parsed["type"], "fact")
        self.assertEqual(parsed["title"], "A thing")
        self.assertEqual(parsed["tags"], ["x", "y"])
        self.assertEqual(body.strip(), "body here")

    def test_no_frontmatter(self):
        meta, body = parse_frontmatter("just text")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just text")

    def test_value_with_colon_quoted_and_recovered(self):
        meta = {"type": "fact", "description": "uses http://example.com now"}
        parsed, _ = parse_frontmatter(dump_frontmatter(meta) + "\n\n")
        self.assertEqual(parsed["description"], "uses http://example.com now")


class ConceptTest(unittest.TestCase):
    def test_type_is_required(self):
        with self.assertRaises(OKFError):
            Concept(concept_id="x", type="").to_text()
        with self.assertRaises(OKFError):
            Concept.from_text("x", "---\ntitle: no type\n---\nbody")

    def test_concept_roundtrip(self):
        c = Concept(concept_id="people/sam", type="person", title="Sam",
                    description="A teammate", tags=["eng"], body="Likes Rust.")
        back = Concept.from_text("people/sam", c.to_text())
        self.assertEqual(back.type, "person")
        self.assertEqual(back.title, "Sam")
        self.assertEqual(back.tags, ["eng"])
        self.assertIn("Likes Rust.", back.body)

    def test_unknown_keys_preserved(self):
        text = "---\ntype: fact\ncustom_key: kept\n---\n\nbody\n"
        c = Concept.from_text("f", text)
        self.assertEqual(c.extra.get("custom_key"), "kept")
        self.assertIn("custom_key: kept", c.to_text())


class BundleTest(unittest.TestCase):
    def test_write_read_roundtrip_and_index(self):
        root = Path(tempfile.mkdtemp()) / ".loci"
        bundle = Bundle(root)
        c = Concept(concept_id="projects/loci", type="project",
                    title="loci", description="ambient agent", body="Public repo.")
        bundle.write_concept(c, timestamp="2026-06-16T00:00:00")

        got = bundle.read_concept("projects/loci")
        self.assertEqual(got.title, "loci")
        self.assertEqual(got.timestamp, "2026-06-16T00:00:00")

        self.assertIn("projects/loci", bundle.list_concepts())

        # Reserved files exist and are not treated as concepts.
        self.assertTrue((root / "index.md").exists())
        self.assertTrue((root / "log.md").exists())
        self.assertNotIn("index", bundle.list_concepts())
        index = bundle.read_index()
        self.assertIn("loci", index)
        self.assertIn("/projects/loci", index)

    def test_dotdot_concept_id_rejected(self):
        bundle = Bundle(Path(tempfile.mkdtemp()))
        with self.assertRaises(OKFError):
            bundle.read_concept("../escape")


if __name__ == "__main__":
    unittest.main()

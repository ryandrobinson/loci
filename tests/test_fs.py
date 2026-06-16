import io
import tempfile
import unittest
from pathlib import Path

from loci.memory.okf import Bundle
from loci.safety import ReadCache
from loci.sandbox import Sandbox
from loci.tools import fs
from loci.tools.base import ToolContext, ToolError
from loci.ui import UI


def make_ctx(root: Path, dry_run=False) -> ToolContext:
    return ToolContext(
        sandbox=Sandbox(root),
        read_cache=ReadCache(),
        ui=UI(stream=io.StringIO(), color=False),
        local_bundle=Bundle(root / ".loci"),
        global_bundle=Bundle(root / "_global"),
        now=lambda: "2026-06-16T00:00:00",
        dry_run=dry_run,
    )


class DeleteTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()

    def test_delete_removes_file(self):
        (self.root / "x.txt").write_text("bye")
        ctx = make_ctx(self.root)
        out = fs.delete_file(ctx, "x.txt")
        self.assertIn("deleted", out)
        self.assertFalse((self.root / "x.txt").exists())

    def test_delete_missing_errors(self):
        with self.assertRaises(ToolError):
            fs.delete_file(make_ctx(self.root), "nope.txt")

    def test_delete_directory_refused(self):
        (self.root / "d").mkdir()
        with self.assertRaises(ToolError):
            fs.delete_file(make_ctx(self.root), "d")

    def test_delete_dry_run_keeps_file(self):
        (self.root / "x.txt").write_text("stay")
        out = fs.delete_file(make_ctx(self.root, dry_run=True), "x.txt")
        self.assertIn("[dry-run]", out)
        self.assertTrue((self.root / "x.txt").exists())

    def test_delete_escape_rejected(self):
        with self.assertRaises(ToolError):
            fs.delete_file(make_ctx(self.root), "../escape.txt")


class EditTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.f = self.root / "f.txt"

    def test_requires_read_first(self):
        self.f.write_text("hello world")
        ctx = make_ctx(self.root)
        with self.assertRaises(ToolError) as cm:
            fs.edit_file(ctx, "f.txt", "world", "there")
        self.assertIn("read-before-write", str(cm.exception))

    def test_edit_after_read(self):
        self.f.write_text("hello world")
        ctx = make_ctx(self.root)
        ctx.read_cache.mark_read(self.f.resolve())
        out = fs.edit_file(ctx, "f.txt", "world", "there")
        self.assertIn("1 replacement", out)
        self.assertEqual(self.f.read_text(), "hello there")

    def test_ambiguous_requires_replace_all(self):
        self.f.write_text("a a a")
        ctx = make_ctx(self.root)
        ctx.read_cache.mark_read(self.f.resolve())
        with self.assertRaises(ToolError):
            fs.edit_file(ctx, "f.txt", "a", "b")
        out = fs.edit_file(ctx, "f.txt", "a", "b", replace_all=True)
        self.assertEqual(self.f.read_text(), "b b b")

    def test_old_not_found(self):
        self.f.write_text("hello")
        ctx = make_ctx(self.root)
        ctx.read_cache.mark_read(self.f.resolve())
        with self.assertRaises(ToolError):
            fs.edit_file(ctx, "f.txt", "absent", "x")

    def test_dry_run_no_change(self):
        self.f.write_text("hello world")
        ctx = make_ctx(self.root, dry_run=True)
        ctx.read_cache.mark_read(self.f.resolve())
        out = fs.edit_file(ctx, "f.txt", "world", "there")
        self.assertIn("[dry-run]", out)
        self.assertEqual(self.f.read_text(), "hello world")


class SearchFindTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        (self.root / "a.py").write_text("import os\nTODO: fix this\n")
        (self.root / "b.txt").write_text("nothing here\n")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "c.py").write_text("# TODO later\nx = 1\n")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "hidden.py").write_text("TODO ignored\n")

    def test_search_finds_matches(self):
        out = fs.search_text(make_ctx(self.root), "TODO")
        self.assertIn("a.py:2:", out)
        self.assertIn("sub/c.py:1:", out)

    def test_search_skips_noise_dirs(self):
        out = fs.search_text(make_ctx(self.root), "TODO")
        self.assertNotIn(".git", out)

    def test_search_glob_filter(self):
        out = fs.search_text(make_ctx(self.root), "TODO", glob="*.py")
        self.assertIn("a.py", out)
        out2 = fs.search_text(make_ctx(self.root), "nothing", glob="*.py")
        self.assertIn("no matches", out2)

    def test_search_invalid_regex(self):
        with self.assertRaises(ToolError):
            fs.search_text(make_ctx(self.root), "(unclosed")

    def test_find_by_glob(self):
        out = fs.find_files(make_ctx(self.root), "*.py")
        self.assertIn("a.py", out)
        self.assertIn("sub/c.py", out)
        self.assertNotIn("b.txt", out)
        self.assertNotIn(".git", out)


if __name__ == "__main__":
    unittest.main()

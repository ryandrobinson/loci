import os
import tempfile
import unittest
from pathlib import Path

from loci.sandbox import Sandbox, SandboxError


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp).resolve()
        self.sb = Sandbox(self.root)

    def test_inside_paths_resolve(self):
        self.assertEqual(self.sb.resolve("a/b.txt"), self.root / "a" / "b.txt")
        self.assertEqual(self.sb.resolve("."), self.root)

    def test_dotdot_traversal_rejected(self):
        with self.assertRaises(SandboxError):
            self.sb.resolve("../escape")
        with self.assertRaises(SandboxError):
            self.sb.resolve("a/../../escape")

    def test_absolute_path_rejected(self):
        with self.assertRaises(SandboxError):
            self.sb.resolve("/etc/passwd")

    def test_empty_path_rejected(self):
        with self.assertRaises(SandboxError):
            self.sb.resolve("")

    def test_symlink_escape_rejected(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        link = self.root / "link"
        os.symlink(outside, link)
        with self.assertRaises(SandboxError):
            self.sb.resolve("link/secret.txt")

    def test_allow_outside_bypasses(self):
        sb = Sandbox(self.root, allow_outside=True)
        self.assertEqual(sb.resolve("/etc/hostname"), Path(os.path.realpath("/etc/hostname")))
        # .. is permitted when explicitly allowed
        sb.resolve("../sibling")


if __name__ == "__main__":
    unittest.main()

import io
import tempfile
import unittest
from pathlib import Path

from loci import safety
from loci.agent import Agent
from loci.memory.session import Session
from loci.sandbox import Sandbox
from loci.ui import UI


class ConfirmTest(unittest.TestCase):
    def test_yes_variants_true(self):
        self.assertTrue(safety.confirm("", reader=lambda: "y"))
        self.assertTrue(safety.confirm("", reader=lambda: "  YES \n"))

    def test_no_and_anything_else_false(self):
        self.assertFalse(safety.confirm("", reader=lambda: "n"))
        self.assertFalse(safety.confirm("", reader=lambda: "maybe"))
        self.assertFalse(safety.confirm("", reader=lambda: ""))

    def test_eof_fails_safe(self):
        def boom():
            raise EOFError
        self.assertFalse(safety.confirm("", reader=boom))


class PlanTest(unittest.TestCase):
    def test_render_plan(self):
        text = safety.render_plan([
            ("rename", "a.txt", "b.txt"),
            ("write", "c.txt", None),
        ])
        self.assertIn("a.txt  ->  b.txt", text)
        self.assertIn("write", text)


class GatingTest(unittest.TestCase):
    """The plan/confirm gating around real (write) tools."""

    def _agent(self, confirm):
        tmp = Path(tempfile.mkdtemp()).resolve()
        ui = UI(stream=io.StringIO(), color=False)
        sb = Sandbox(tmp)
        ses = Session(key="test", budget=9999)
        agent = Agent({"run_shell_enabled": False}, ui, sb, ses, confirm=confirm)
        return agent, tmp

    def _write_use(self, i, path, content="hi"):
        return {"type": "tool_use", "id": f"t{i}", "name": "write_file",
                "input": {"path": path, "content": content}}

    def test_single_write_declined_writes_nothing(self):
        agent, tmp = self._agent(confirm=lambda: False)
        results = agent._run_tools([self._write_use(1, "new.txt")])
        self.assertTrue(results[0]["is_error"])
        self.assertFalse((tmp / "new.txt").exists())

    def test_single_write_confirmed_writes(self):
        agent, tmp = self._agent(confirm=lambda: True)
        results = agent._run_tools([self._write_use(1, "new.txt", "hello")])
        self.assertFalse(results[0]["is_error"])
        self.assertEqual((tmp / "new.txt").read_text(), "hello")

    def test_batch_single_confirm_applies_all(self):
        agent, tmp = self._agent(confirm=lambda: True)
        results = agent._run_tools([
            self._write_use(1, "a.txt", "A"),
            self._write_use(2, "b.txt", "B"),
        ])
        self.assertFalse(any(r["is_error"] for r in results))
        self.assertEqual((tmp / "a.txt").read_text(), "A")
        self.assertEqual((tmp / "b.txt").read_text(), "B")

    def test_batch_declined_applies_none(self):
        agent, tmp = self._agent(confirm=lambda: False)
        results = agent._run_tools([
            self._write_use(1, "a.txt"),
            self._write_use(2, "b.txt"),
        ])
        self.assertTrue(all(r["is_error"] for r in results))
        self.assertFalse((tmp / "a.txt").exists())
        self.assertFalse((tmp / "b.txt").exists())

    def test_read_before_write_enforced(self):
        agent, tmp = self._agent(confirm=lambda: True)
        (tmp / "exists.txt").write_text("old")
        results = agent._run_tools([self._write_use(1, "exists.txt", "new")])
        self.assertTrue(results[0]["is_error"])
        self.assertIn("read-before-write", results[0]["content"])
        self.assertEqual((tmp / "exists.txt").read_text(), "old")


if __name__ == "__main__":
    unittest.main()

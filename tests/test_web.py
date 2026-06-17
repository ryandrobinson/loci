import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

from loci.tools import schemas
from loci.tools.base import ToolError
from loci.tools.web import web_fetch


def _proc(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class WebFetchTest(unittest.TestCase):
    """web_fetch shells out to w3m; the handler itself never confirms or gates —
    that lives in the agent loop. Here we cover scheme safety and w3m plumbing."""

    def test_returns_rendered_text(self):
        with mock.patch("loci.tools.web.subprocess.run",
                        return_value=_proc(stdout="Hello page\nbody")) as run:
            out = web_fetch(None, url="https://example.com")
        self.assertEqual(out, "Hello page\nbody")
        # Invoked w3m with -dump and the URL, as a list (no shell=True).
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], "w3m")
        self.assertIn("-dump", argv)
        self.assertIn("https://example.com", argv)

    def test_rejects_non_http_scheme(self):
        # file:// would let w3m read local files and bypass the cwd boundary.
        for bad in ("file:///etc/passwd", "ftp://x", "/etc/passwd", "data:text/plain,x"):
            with self.assertRaises(ToolError):
                web_fetch(None, url=bad)

    def test_empty_url(self):
        with self.assertRaises(ToolError):
            web_fetch(None, url="   ")

    def test_missing_w3m_is_a_tool_error(self):
        with mock.patch("loci.tools.web.subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaises(ToolError) as cm:
                web_fetch(None, url="https://example.com")
        self.assertIn("w3m", str(cm.exception))

    def test_timeout_is_a_tool_error(self):
        with mock.patch("loci.tools.web.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="w3m", timeout=30)):
            with self.assertRaises(ToolError):
                web_fetch(None, url="https://example.com")

    def test_empty_output_is_a_tool_error(self):
        with mock.patch("loci.tools.web.subprocess.run",
                        return_value=_proc(stdout="   ", stderr="404", returncode=1)):
            with self.assertRaises(ToolError):
                web_fetch(None, url="https://example.com/missing")

    def test_output_is_truncated(self):
        from loci.tools.web import OUTPUT_LIMIT
        big = "x" * (OUTPUT_LIMIT + 500)
        with mock.patch("loci.tools.web.subprocess.run", return_value=_proc(stdout=big)):
            out = web_fetch(None, url="https://example.com")
        self.assertLess(len(out), len(big))
        self.assertIn("truncated", out)


class WebFetchGatingTest(unittest.TestCase):
    """web_fetch is advertised to the API only when web_fetch_enabled is set."""

    def _names(self, **kw):
        return [s["name"] for s in schemas(**kw)]

    def test_hidden_when_disabled(self):
        self.assertNotIn("web_fetch", self._names(run_shell_enabled=False, web_fetch_enabled=False))

    def test_shown_when_enabled(self):
        self.assertIn("web_fetch", self._names(run_shell_enabled=False, web_fetch_enabled=True))

    def test_default_is_hidden(self):
        # The flag defaults to off, mirroring run_shell.
        self.assertNotIn("web_fetch", [s["name"] for s in schemas(False)])


if __name__ == "__main__":
    unittest.main()

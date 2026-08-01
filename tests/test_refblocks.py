"""Unit tests for scripts/refblocks.py — ref-pinned config-block reading (the v3 gate-config
rule: blocks come from origin/main BLOBS at a fetched, recorded pin SHA, never from any working
tree). Real git against the tests/support/gitsandbox.py origin+clone pair; no gh, no shim —
mirrors tests/test_workspace.py's sandbox posture.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

import refblocks  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import gitsandbox  # noqa: E402


def _git(args, cwd):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, encoding="utf-8", check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("git %s (cwd=%s) failed: %s" % (" ".join(args), cwd, result.stderr))
    return result.stdout.strip()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _commit_push(clone_path, message):
    _git(["add", "-A"], clone_path)
    _git(["commit", "-m", message], clone_path)
    _git(["push", "origin", "HEAD:main"], clone_path)


BLOCK = "<!-- issue-resolver-test-target -->\n- `run the suite`\n<!-- /issue-resolver-test-target -->\n"


class RefblocksSandboxTestCase(unittest.TestCase):
    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path


class FetchPinTests(RefblocksSandboxTestCase):
    def test_pin_is_the_origin_main_tip_sha(self):
        pin = refblocks.fetch_pin(self.root)
        self.assertEqual(pin, _git(["rev-parse", "origin/main"], self.root))
        self.assertEqual(len(pin), 40)

    def test_pin_tracks_origin_not_the_local_branch(self):
        # An unpushed LOCAL commit on the clone's main must not move the pin.
        _write(Path(self.root) / "local-only.txt", "unpushed\n")
        _git(["add", "local-only.txt"], self.root)
        _git(["commit", "-m", "local only"], self.root)
        pin = refblocks.fetch_pin(self.root)
        self.assertEqual(pin, _git(["rev-parse", "origin/main"], self.root))
        self.assertNotEqual(pin, _git(["rev-parse", "HEAD"], self.root))


class ReadBlockAtRefTests(RefblocksSandboxTestCase):
    def test_reads_the_block_from_the_pinned_blob(self):
        _write(Path(self.root) / "COMMANDS.md", BLOCK)
        _commit_push(self.root, "add gate block")
        pin = refblocks.fetch_pin(self.root)
        present, interior, source = refblocks.read_block_at_ref(
            self.root, pin, "issue-resolver-test-target"
        )
        self.assertTrue(present)
        self.assertEqual(interior, ["- `run the suite`"])
        self.assertEqual(source, "%s:COMMANDS.md" % pin[:7])

    def test_working_tree_mutation_is_invisible_at_the_pin(self):
        _write(Path(self.root) / "COMMANDS.md", BLOCK)
        _commit_push(self.root, "add gate block")
        pin = refblocks.fetch_pin(self.root)
        # The TOCTOU the v2 shape carried: mutate the working-tree file AFTER the pin — the
        # at-ref read must still return the committed content.
        _write(
            Path(self.root) / "COMMANDS.md",
            "<!-- issue-resolver-test-target -->\n- `weakened gate`\n<!-- /issue-resolver-test-target -->\n",
        )
        present, interior, _source = refblocks.read_block_at_ref(
            self.root, pin, "issue-resolver-test-target"
        )
        self.assertTrue(present)
        self.assertEqual(interior, ["- `run the suite`"])

    def test_unpushed_local_commit_is_invisible_at_the_pin(self):
        _write(Path(self.root) / "COMMANDS.md", BLOCK)
        _commit_push(self.root, "add gate block")
        pin = refblocks.fetch_pin(self.root)
        _write(
            Path(self.root) / "COMMANDS.md",
            "<!-- issue-resolver-test-target -->\n- `weakened gate`\n<!-- /issue-resolver-test-target -->\n",
        )
        _git(["add", "COMMANDS.md"], self.root)
        _git(["commit", "-m", "weaken locally, never pushed"], self.root)
        present, interior, _source = refblocks.read_block_at_ref(
            self.root, pin, "issue-resolver-test-target"
        )
        self.assertTrue(present)
        self.assertEqual(interior, ["- `run the suite`"])

    def test_commands_md_wins_over_claude_md(self):
        _write(
            Path(self.root) / "COMMANDS.md",
            "<!-- m -->\n- `from commands`\n<!-- /m -->\n",
        )
        _write(Path(self.root) / "CLAUDE.md", "<!-- m -->\n- `from claude`\n<!-- /m -->\n")
        _commit_push(self.root, "both candidates")
        pin = refblocks.fetch_pin(self.root)
        present, interior, source = refblocks.read_block_at_ref(self.root, pin, "m")
        self.assertTrue(present)
        self.assertEqual(interior, ["- `from commands`"])
        self.assertIn("COMMANDS.md", source)

    def test_malformed_block_in_one_candidate_falls_through_to_the_next(self):
        # Unterminated in COMMANDS.md, well-formed in CLAUDE.md — malformed == absent there.
        _write(Path(self.root) / "COMMANDS.md", "<!-- m -->\n- `broken`\n")
        _write(Path(self.root) / "CLAUDE.md", "<!-- m -->\n- `good`\n<!-- /m -->\n")
        _commit_push(self.root, "malformed first candidate")
        pin = refblocks.fetch_pin(self.root)
        present, interior, source = refblocks.read_block_at_ref(self.root, pin, "m")
        self.assertTrue(present)
        self.assertEqual(interior, ["- `good`"])
        self.assertIn("CLAUDE.md", source)

    def test_at_ref_include_resolution_one_level(self):
        _write(Path(self.root) / "CLAUDE.md", "See @docs/OPS.md for commands.\n")
        (Path(self.root) / "docs").mkdir(exist_ok=True)
        _write(Path(self.root) / "docs" / "OPS.md", "<!-- m -->\n- `from include`\n<!-- /m -->\n")
        _commit_push(self.root, "include-carried block")
        pin = refblocks.fetch_pin(self.root)
        present, interior, source = refblocks.read_block_at_ref(self.root, pin, "m")
        self.assertTrue(present)
        self.assertEqual(interior, ["- `from include`"])
        self.assertIn("docs/OPS.md", source)

    def test_absent_everywhere_reports_not_present(self):
        pin = refblocks.fetch_pin(self.root)
        present, interior, source = refblocks.read_block_at_ref(self.root, pin, "no-such-marker")
        self.assertFalse(present)
        self.assertEqual(interior, [])
        self.assertIsNone(source)

    def test_read_lines_at_ref_distinguishes_absent_from_empty(self):
        _write(Path(self.root) / "EMPTY.md", "")
        _commit_push(self.root, "empty file")
        pin = refblocks.fetch_pin(self.root)
        self.assertEqual(refblocks.read_lines_at_ref(self.root, pin, "EMPTY.md"), [])
        self.assertIsNone(refblocks.read_lines_at_ref(self.root, pin, "MISSING.md"))


if __name__ == "__main__":
    unittest.main()

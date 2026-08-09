from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_repo_tree import check_repo_tree, part_command


class RepoTreeTests(unittest.TestCase):
    def test_current_repo_has_one_place_for_every_file(self) -> None:
        result = check_repo_tree(REPO_ROOT)

        self.assertTrue(result["ok"], result["problems"])
        self.assertGreater(result["files"], 200)
        self.assertEqual(result["end_parts"], 15)
        self.assertEqual(result["records"], 21)
        self.assertEqual(result["product_end_parts"], 22)
        self.assertEqual(result["code_parts"], 5)

    def test_work_has_owned_doors_and_one_local_check(self) -> None:
        command = part_command(REPO_ROOT, "work")

        self.assertEqual(command[1:3], ["-S", str(REPO_ROOT / "scripts/verification_profiles.py")])
        self.assertIn("tests.test_agent_advance", command)
        self.assertIn("tests.test_work_ideas", command)
        self.assertNotIn("tests.test_linear_adapter", command)

    def test_code_door_must_belong_to_its_part(self) -> None:
        tree = json.loads(
            (REPO_ROOT / "docs" / "agent" / "repo-tree.json").read_text(
                encoding="utf-8"
            )
        )
        app = next(part for part in tree["parts"] if part["name"] == "app")
        code = next(part for part in app["parts"] if part["name"] == "code")
        work = next(part for part in code["parts"] if part["name"] == "work")
        work["door"][0] = "src/palari_company_os/cli.py"

        result = self._check(tree, [])

        self.assertIn(
            "code part door is not owned: work (src/palari_company_os/cli.py)",
            result["problems"],
        )

    def test_gap_fails(self) -> None:
        result = self._check(_tree(["known.txt"]), ["known.txt", "lost.txt"])

        self.assertFalse(result["ok"])
        self.assertIn("file has no part: lost.txt", result["problems"])

    def test_overlap_fails(self) -> None:
        tree = _tree(["known.txt"])
        tree["parts"][1]["files"] = ["known.txt"]
        result = self._check(tree, ["known.txt"])

        self.assertFalse(result["ok"])
        self.assertTrue(any("more than one part" in item for item in result["problems"]))

    def test_two_child_parts_fail(self) -> None:
        tree = _tree(["known.txt"])
        tree["parts"] = tree["parts"][:2]
        result = self._check(tree, ["known.txt"])

        self.assertFalse(result["ok"])
        self.assertIn("part needs three to five child parts: repo", result["problems"])

    def test_hard_new_name_fails(self) -> None:
        tree = _tree(["known.txt"])
        tree["parts"][0]["name"] = "orchestration"
        result = self._check(tree, ["known.txt"])

        self.assertFalse(result["ok"])
        self.assertIn("part needs one approved plain word: repo", result["problems"])

    def _check(self, tree: dict[str, object], files: list[str]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            target = root / "docs" / "agent" / "repo-tree.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(tree), encoding="utf-8")
            for name in files:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name, encoding="utf-8")
            return check_repo_tree(root)


def _tree(first_files: list[str]) -> dict[str, object]:
    return {
        "name": "repo",
        "parts": [
            {"name": "app", "files": first_files},
            {"name": "tests", "files": ["tests/"]},
            {"name": "docs", "files": ["docs/"]},
        ],
    }


if __name__ == "__main__":
    unittest.main()

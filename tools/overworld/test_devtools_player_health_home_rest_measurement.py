"""Negative controls for the home Rest result boundary."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_player_health_home_rest_measurement import check_home_rest


SOURCE = {"romSha256": "r" * 64, "overlaySha256": "o" * 64}
RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/draft-recipes/player-hp.home-rest.json"
RAM_REST_RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/test-recipes/player-hp.ram-rest.json"


def row(frame, hp, checkpoint, party_hp):
    context = {"mapId": 63, "fieldEpoch": 1, "mapGeneration": 2}
    snapshot = {
        "frame": frame, "nativeCycle": frame * 2,
        "romSha256": SOURCE["romSha256"], "fieldAvailable": True,
        "observationBoundary": "main-task-queue-completion",
        "context": context, "fieldControl": {"taskPointer": 0},
        "dialogue": {"known": True, "state": "idle"},
        "player": {"x": 6, "y": 8},
        "partyObservation": {"frame": frame, "boundary": "main-task-queue-completion"},
        "party": [{"species": 155, "form": 0, "level": 5,
                   "personality": 123, "maxHp": 20, "hp": party_hp,
                   "status": 0}],
    }
    receipt = {"schemaVersion": 1,
               "identity": {"descriptorVersion": 1, "overlayId": 161,
                            "overlaySha256": SOURCE["overlaySha256"],
                            "romSha256": SOURCE["romSha256"]},
               "frame": frame, "nativeCycle": frame * 2,
               "observationBoundary": "main-task-queue-completion",
               "context": context, "maxHp": 100, "hp": hp,
               "savedHp": hp, "checkpointSpawn": checkpoint,
               "recoveryPending": False,
               "lastDamage": 33, "acceptedHits": 1}
    return {"command": "player-health.observe", "snapshot": snapshot,
            "receipt": {"playerHealth": receipt}}


class HomeRestBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.before = row(100, 67, 2, 1)
        self.after = row(300, 100, 1, 20)

    def test_completed_rest_changes_all_three_owners(self):
        result = check_home_rest(self.before, self.after, SOURCE)
        self.assertEqual(result["playerHp"], [67, 100])
        self.assertEqual(result["partyHp"], [1, 20])
        self.assertEqual(result["checkpointSpawn"], [2, 1])

    def test_draft_reaches_rest_with_two_down_edges(self):
        recipe = json.loads(RECIPE.read_text())
        setup = {row["id"]: row for row in recipe["setup"]}
        ram_rest = json.loads(RAM_REST_RECIPE.read_text())
        ram_setup = {row["id"]: row for row in ram_rest["setup"]}
        for action in ("ram-tile", "spawn-onix", "bind-onix"):
            self.assertEqual(setup[action]["args"], ram_setup[action]["args"])
        self.assertEqual((setup["spawn-onix"]["args"]["x"],
                          setup["spawn-onix"]["args"]["z"]), (585, 412))
        self.assertEqual(setup["allow-natural-ram"]["args"],
                         ram_rest["actions"][1]["args"])
        actions = [row["id"] for row in recipe["actions"]]
        self.assertEqual(actions[:2], ["mom-idle", "before-rest"])
        start, end = actions.index("menu-settle"), actions.index("choose-rest")
        self.assertEqual(actions[start:end + 1], [
            "menu-settle", "menu-down-1", "menu-release-1",
            "menu-down-2", "menu-release-2", "choose-rest"])
        by_id = {row["id"]: row for row in recipe["actions"]}
        self.assertEqual([by_id[f"menu-down-{n}"]["args"]["keys"]
                          for n in (1, 2)], [["DOWN"], ["DOWN"]])
        self.assertEqual(by_id["choose-rest"]["args"]["keys"], ["A"])

    def test_wrong_checkpoint_or_party_or_field_fails(self):
        for owner, path, value in (
            ("before", ("receipt", "playerHealth", "checkpointSpawn"), 1),
            ("after", ("receipt", "playerHealth", "checkpointSpawn"), 2),
            ("after", ("snapshot", "party", 0, "hp"), 19),
            ("after", ("snapshot", "party", 0, "personality"), 456),
            ("after", ("snapshot", "fieldControl", "taskPointer"), 42),
        ):
            with self.subTest(path=path):
                before, after = deepcopy(self.before), deepcopy(self.after)
                current = before if owner == "before" else after
                for key in path[:-1]:
                    current = current[key]
                current[path[-1]] = value
                with self.assertRaises(ValueError):
                    check_home_rest(before, after, SOURCE)


if __name__ == "__main__":
    unittest.main()

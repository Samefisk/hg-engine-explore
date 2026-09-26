"""Machine checks for the PB0 profile-building-blocks target manifest."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO / "data/overworld_behavior_profiles.json"
MANIFEST_PATH = (
    REPO
    / "tools/overworld/fixtures/profile_building_blocks_target_v1.json"
)


class ManifestError(ValueError):
    """The PB0 manifest or catalog does not match a supported state."""


TARGET_CONTRACT_DIGESTS = {
    "pools": "e8b04f22243b287d29f9d6617f1a06af70f263b2ba46eff5b6191df22fbecb14",
    "memberships": "060416a2a48bbe0d0ccdafdd162b5eeec4411d6e31342b7483be700f7b56ae3b",
    "profile-fields": "99dc0ff2b3fcfa03cdf0c14a7f90a825608602e1019d565b9f3080f1f09cd8b6",
    "application-targets": "13a36b6b2638cbc4dc2c5359065d1e7b86ef54f23051d896bc793207dfe67a91",
    "conditions": "666e4d1ebadd193052d9512ee14509f525bfb3ab4124da356b1b2a3a6fd17e17",
    "runtime-bindings": "9905bf77a44f40d55aa6e2d99ab012147055164c87c8b271daadaafc624718e6",
}


def _target_contract_parts(catalog: dict) -> dict:
    conditional_profiles = [
        profile for profile in catalog["profiles"] if profile.get("conditions")
    ]
    return {
        "pools": catalog["pools"],
        "memberships": {
            "namedPools": [
                {"id": pool["id"], "members": pool["members"]}
                for pool in catalog["pools"]
            ],
            "applications": [
                {
                    "id": application["id"],
                    "hasTarget": "target" in application,
                    "target": application.get("target"),
                }
                for application in catalog["applications"]
            ],
            "conditions": [
                {
                    "profile": profile["id"],
                    "subjects": [
                        condition["subjects"] for condition in profile["conditions"]
                    ],
                }
                for profile in conditional_profiles
            ],
        },
        "profile-fields": [
            {"id": profile["id"], "fields": profile["fields"]}
            for profile in catalog["profiles"]
        ],
        "application-targets": [
            {
                "id": application["id"],
                "profile": application["profile"],
                "hasTarget": "target" in application,
                "target": application.get("target"),
            }
            for application in catalog["applications"]
        ],
        "conditions": [
            {"profile": profile["id"], "conditions": profile["conditions"]}
            for profile in conditional_profiles
        ],
        "runtime-bindings": catalog["runtimeBindings"],
    }


def _contract_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_target_contract(catalog: dict) -> None:
    try:
        parts = _target_contract_parts(catalog)
    except (KeyError, TypeError) as error:
        raise ManifestError("target pools contract drift") from error
    for label, expected_digest in TARGET_CONTRACT_DIGESTS.items():
        if _contract_digest(parts[label]) != expected_digest:
            raise ManifestError(f"target {label} contract drift")


def _validate_exact_profile_contracts(catalog: dict, manifest: dict) -> None:
    profiles = {profile["id"]: profile for profile in catalog["profiles"]}
    contracts = manifest["target"].get("exactProfileContracts", {})
    for profile_id, contract in contracts.items():
        profile = profiles.get(profile_id)
        if profile is None:
            raise ManifestError(
                f"target exact profile contract drift: {profile_id}"
            )
        condition = profile.get("conditions", [])
        expected_condition = contract["condition"]
        actual_condition = {
            key: condition[0][key]
            for key in ("id", "when", "activation", "target")
        } if len(condition) == 1 else None
        if (
            profile.get("kind") != contract["kind"]
            or profile.get("classification") != contract["classification"]
            or profile.get("fields") != contract["fields"]
            or actual_condition != expected_condition
            or any(
                retired_id in profiles
                for retired_id in contract["retiredProfileIds"]
            )
        ):
            raise ManifestError(
                f"target exact profile contract drift: {profile_id}"
            )


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _require_unique(values: list[str], label: str) -> None:
    duplicates = _duplicates(values)
    if duplicates:
        raise ManifestError(f"duplicate {label}: {', '.join(duplicates)}")


def _validate_precedence(manifest: dict) -> None:
    target = manifest["target"]
    applications = target["applications"]
    positions = {
        application["id"]: index for index, application in enumerate(applications)
    }
    condition_order = target["conditionOrder"]

    for constraint in manifest["precedenceConstraints"]:
        kind = constraint["kind"]
        if kind == "application-before":
            before = constraint["before"]
            after = constraint["after"]
            if before not in positions or after not in positions:
                raise ManifestError(f"precedence references unknown application: {constraint}")
            if positions[before] >= positions[after]:
                raise ManifestError(f"precedence violation: {before} must precede {after}")
        elif kind in {"application-before-all", "application-after-all"}:
            application = constraint["application"]
            others = constraint["others"]
            if application not in positions or any(other not in positions for other in others):
                raise ManifestError(f"precedence references unknown application: {constraint}")
            if kind == "application-before-all":
                valid = all(positions[application] < positions[other] for other in others)
                relation = "precede"
            else:
                valid = all(positions[application] > positions[other] for other in others)
                relation = "follow"
            if not valid:
                raise ManifestError(
                    f"precedence violation: {application} must {relation} {others}"
                )
        elif kind == "condition-last":
            profile_id = constraint["profile"]
            condition_id = constraint["condition"]
            conditions = condition_order.get(profile_id)
            if not conditions or conditions[-1] != condition_id:
                raise ManifestError(
                    f"precedence violation: {condition_id} must be last in {profile_id}"
                )
        else:
            raise ManifestError(f"unknown precedence constraint kind: {kind}")


def validate_manifest(manifest: dict) -> None:
    source = manifest["source"]
    target = manifest["target"]

    expected_source_counts = {
        "profileCount": (32, len(source["profiles"])),
        "applicationCount": (27, len(source["applications"])),
        "classBindingCount": (5, len(source["classBindings"])),
    }
    for key, (required, actual) in expected_source_counts.items():
        if source[key] != required or actual != required:
            raise ManifestError(
                f"source {key} must be {required}; declared {source[key]}, recorded {actual}"
            )

    source_profile_ids = [profile["id"] for profile in source["profiles"]]
    source_application_ids = [item["id"] for item in source["applications"]]
    source_class_symbols = [item["symbol"] for item in source["classBindings"]]
    _require_unique(source_profile_ids, "source profile")
    _require_unique(source_application_ids, "source application")
    _require_unique(source_class_symbols, "source class binding")

    applications = target["applications"]
    if target["applicationCount"] != len(applications):
        raise ManifestError(
            "target applicationCount does not match the recorded applications"
        )
    if len(applications) > target["maximumApplicationCount"] or len(applications) > 32:
        raise ManifestError(
            f"target has {len(applications)} applications; maximum is 32"
        )
    if [item["order"] for item in applications] != list(
        range(1, len(applications) + 1)
    ):
        raise ManifestError("target application order must be consecutive from 1")

    application_ids = [item["id"] for item in applications]
    destination_profiles = [item["profile"] for item in applications]
    destination_names = [item["name"] for item in applications]
    _require_unique(application_ids, "target application")
    _require_unique(destination_profiles, "target destination profile")
    _require_unique(destination_names, "target destination name")

    classification_order = target["classificationOrder"]
    _require_unique(classification_order, "classification")
    classification_rank = {
        classification: index
        for index, classification in enumerate(classification_order)
    }
    previous_rank = -1
    for application in applications:
        classification = application["classification"]
        if classification not in classification_rank:
            raise ManifestError(
                f"unknown target classification: {classification}"
            )
        current_rank = classification_rank[classification]
        if current_rank < previous_rank:
            raise ManifestError(
                f"group-order violation at target application {application['id']}"
            )
        previous_rank = current_rank

    named_pools = target["namedPools"]
    pool_ids = [pool["id"] for pool in named_pools]
    _require_unique(pool_ids, "named pool")
    for pool in named_pools:
        if not pool["members"]:
            raise ManifestError(f"named pool is empty: {pool['id']}")
        _require_unique(pool["members"], f"member in named pool {pool['id']}")

    membership_sets = target["membershipSets"]
    for set_id, members in membership_sets.items():
        if not members:
            raise ManifestError(f"membership set is empty: {set_id}")
        _require_unique(members, f"member in membership set {set_id}")

    target_profile_ids = set(destination_profiles)
    exact_profile_contracts = target.get("exactProfileContracts", {})
    unknown_contracts = set(exact_profile_contracts) - target_profile_ids
    if unknown_contracts:
        raise ManifestError(
            f"exact profile contract references unknown target profiles: "
            f"{sorted(unknown_contracts)}"
        )
    composition_ids = [item["id"] for item in target["compositions"]]
    _require_unique(composition_ids, "composition")
    for composition in target["compositions"]:
        membership = composition["membership"]
        if "set" in membership and membership["set"] not in membership_sets:
            raise ManifestError(
                f"composition {composition['id']} references unknown membership set"
            )
        if "pool" in membership and membership["pool"] not in pool_ids:
            raise ManifestError(
                f"composition {composition['id']} references unknown named pool"
            )
        unknown_profiles = set(composition["profiles"]) - target_profile_ids
        if unknown_profiles:
            raise ManifestError(
                f"composition {composition['id']} references unknown target profiles: "
                f"{sorted(unknown_profiles)}"
            )

    migrations = manifest["migration"]["profiles"]
    migration_sources = [item["source"] for item in migrations]
    _require_unique(migration_sources, "migration source")
    if set(migration_sources) != set(source_profile_ids):
        missing = sorted(set(source_profile_ids) - set(migration_sources))
        unknown = sorted(set(migration_sources) - set(source_profile_ids))
        raise ManifestError(
            f"migration source mismatch; missing={missing}, unknown={unknown}"
        )

    root_id = target["rootProfile"]["id"]
    internal_states = set(target["internalStates"])
    for migration in migrations:
        if not migration["destinations"]:
            raise ManifestError(
                f"migration has no destination: {migration['source']}"
            )
        for destination in migration["destinations"]:
            destination_type = destination["type"]
            destination_id = destination["id"]
            valid = (
                (destination_type == "root" and destination_id == root_id)
                or (
                    destination_type == "profile"
                    and destination_id in target_profile_ids
                )
                or (destination_type == "named-pool" and destination_id in pool_ids)
                or (
                    destination_type == "internal-state"
                    and destination_id in internal_states
                )
            )
            if not valid:
                raise ManifestError(
                    f"unknown migration destination: {destination_type}:{destination_id}"
                )

    retired = manifest["migration"]["retiredSourceProfileIds"]
    deleted = manifest["migration"]["deletedWithoutProfileReplacement"]
    _require_unique(retired, "retired source profile")
    _require_unique(deleted, "deleted source profile")
    if not set(retired).issubset(source_profile_ids) or not set(deleted).issubset(
        source_profile_ids
    ):
        raise ManifestError("deleted profile list references an unknown source profile")

    target_class_symbols = {
        item["symbol"] for item in target["classBindings"]
    }
    expected_deleted_symbols = set(source_class_symbols) - target_class_symbols
    actual_deleted_symbols = set(manifest["migration"]["deletedClassBindings"])
    if actual_deleted_symbols != expected_deleted_symbols:
        raise ManifestError(
            "deleted class bindings do not match the source-to-target class change"
        )

    _validate_precedence(manifest)


def _catalog_profile_inventory(catalog: dict) -> list[dict]:
    return [
        {
            "id": profile["id"],
            "name": profile["name"],
            "classification": profile.get("classification"),
        }
        for profile in catalog["profiles"]
    ]


def _catalog_application_inventory(catalog: dict) -> list[dict]:
    return [
        {"id": application["id"], "profile": application["profile"]}
        for application in catalog["applications"]
    ]


def _validate_source_memberships(catalog: dict, manifest: dict) -> None:
    applications = {
        application["id"]: application for application in catalog["applications"]
    }
    target = manifest["target"]
    membership_sets = target["membershipSets"]
    named_pools = {pool["id"]: pool["members"] for pool in target["namedPools"]}

    direct_checks = {
        "apply-teleport-stalker-override": membership_sets["teleport-stalker"],
        "apply-bird": membership_sets["birds"],
        "apply-flying-insect": membership_sets["flying-insects"],
        "apply-playful": named_pools["playful-pokemon"],
        "apply-baby-pokemon": named_pools["baby-pokemon"],
        "apply-ambush-plant": membership_sets["plant-idle-ambush-rest"],
    }
    for application_id, expected_members in direct_checks.items():
        actual_members = applications[application_id]["target"]["members"]
        if actual_members != expected_members:
            raise ManifestError(
                f"source membership drift for {application_id}"
            )

    swaying_members = applications["apply-swaying-plant"]["target"]["members"]
    expected_swaying = (
        membership_sets["plant-meander-waddle-startled"]
        + membership_sets["plant-hop-around-startled"]
    )
    if set(swaying_members) != set(expected_swaying):
        raise ManifestError("source plant split does not preserve Swaying Plant members")


def validate_catalog_state(catalog: dict, manifest: dict) -> str:
    """Return ``source-v4`` or ``target``; reject every partial state."""

    validate_manifest(manifest)
    source = manifest["source"]
    target = manifest["target"]

    actual_profiles = _catalog_profile_inventory(catalog)
    actual_applications = _catalog_application_inventory(catalog)
    actual_class_bindings = catalog["runtimeBindings"]["classOrder"]

    actual_profile_ids = [item["id"] for item in actual_profiles]
    source_profile_ids = [item["id"] for item in source["profiles"]]
    actual_application_ids = [item["id"] for item in actual_applications]
    source_application_ids = [item["id"] for item in source["applications"]]

    if (
        actual_profile_ids == source_profile_ids
        and actual_application_ids == source_application_ids
    ):
        if catalog.get("catalogVersion") != source["catalogVersion"]:
            raise ManifestError("source catalog version drift")
        if actual_profiles != source["profiles"]:
            raise ManifestError("source profile inventory drift")
        if actual_applications != source["applications"]:
            raise ManifestError("source application inventory drift")
        if actual_class_bindings != source["classBindings"]:
            raise ManifestError("source class binding inventory drift")
        _validate_source_memberships(catalog, manifest)
        return "source-v4"

    target_applications = target["applications"]
    target_application_ids = [item["id"] for item in target_applications]
    target_profile_ids = [target["rootProfile"]["id"]] + [
        item["profile"] for item in target_applications
    ]
    if (
        actual_profile_ids == target_profile_ids
        and actual_application_ids == target_application_ids
    ):
        expected_applications = [
            {"id": item["id"], "profile": item["profile"]}
            for item in target_applications
        ]
        if actual_applications != expected_applications:
            raise ManifestError("target application inventory drift")
        if actual_class_bindings != target["classBindings"]:
            raise ManifestError("target class binding inventory drift")

        actual_by_id = {profile["id"]: profile for profile in catalog["profiles"]}
        root = target["rootProfile"]
        if actual_by_id[root["id"]]["name"] != root["name"]:
            raise ManifestError("target root profile name drift")
        for expected in target_applications:
            profile = actual_by_id[expected["profile"]]
            if profile["name"] != expected["name"]:
                raise ManifestError(
                    f"target profile name drift: {expected['profile']}"
                )
            if profile.get("classification") != expected["classification"]:
                raise ManifestError(
                    f"target profile classification drift: {expected['profile']}"
                )

        for profile_id, expected_conditions in target["conditionOrder"].items():
            actual_conditions = [
                condition["id"]
                for condition in actual_by_id[profile_id].get("conditions", [])
            ]
            if actual_conditions != expected_conditions:
                raise ManifestError(
                    f"target condition order drift: {profile_id}"
                )
        _validate_target_contract(catalog)
        _validate_exact_profile_contracts(catalog, manifest)
        return "target"

    missing_source_profiles = sorted(set(source_profile_ids) - set(actual_profile_ids))
    unknown_source_profiles = sorted(set(actual_profile_ids) - set(source_profile_ids))
    details = []
    if missing_source_profiles:
        details.append(f"missing source profile={missing_source_profiles}")
    if unknown_source_profiles:
        details.append(f"unknown source profile={unknown_source_profiles}")
    if not details:
        details.append("application inventory is neither source nor target")
    raise ManifestError("partial or unknown catalog state: " + "; ".join(details))


class ProfileBuildingBlocksManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG_PATH.read_text())
        cls.manifest = json.loads(MANIFEST_PATH.read_text())

    def test_checked_in_catalog_matches_the_frozen_target(self) -> None:
        self.assertEqual(
            validate_catalog_state(self.catalog, self.manifest),
            "target",
        )

    def test_hollow_target_inventory_is_rejected(self) -> None:
        target = self.manifest["target"]
        profiles = [
            {
                "id": target["rootProfile"]["id"],
                "name": target["rootProfile"]["name"],
                "fields": {},
            }
        ]
        for application in target["applications"]:
            profile = {
                "id": application["profile"],
                "name": application["name"],
                "classification": application["classification"],
                "fields": {},
            }
            if application["profile"] in target["conditionOrder"]:
                profile["conditions"] = [
                    {"id": condition_id}
                    for condition_id in target["conditionOrder"][
                        application["profile"]
                    ]
                ]
            profiles.append(profile)
        catalog = {
            "catalogVersion": 5,
            "profiles": profiles,
            "applications": [
                {"id": item["id"], "profile": item["profile"]}
                for item in target["applications"]
            ],
            "runtimeBindings": {"classOrder": target["classBindings"]},
        }
        with self.assertRaisesRegex(ManifestError, "target pools contract drift"):
            validate_catalog_state(catalog, self.manifest)

    def test_target_pool_membership_drift_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["pools"][0]["members"].pop()
        with self.assertRaisesRegex(ManifestError, "target pools contract drift"):
            validate_catalog_state(catalog, self.manifest)

    def test_target_direct_membership_drift_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        application = next(
            item for item in catalog["applications"] if "target" in item
        )
        application["target"]["members"].pop()
        with self.assertRaisesRegex(ManifestError, "target memberships contract drift"):
            validate_catalog_state(catalog, self.manifest)

    def test_target_profile_field_drift_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["profiles"][0]["fields"]["walkSwayWidth"]["value"] = 99
        with self.assertRaisesRegex(ManifestError, "target profile-fields contract drift"):
            validate_catalog_state(catalog, self.manifest)

    def test_ram_contract_is_exact_and_base_profiles_are_retired(self) -> None:
        profiles = {profile["id"]: profile for profile in self.catalog["profiles"]}
        contract = self.manifest["target"]["exactProfileContracts"]["ram"]
        ram = profiles["ram"]
        condition = ram["conditions"]

        self.assertEqual(ram["kind"], contract["kind"])
        self.assertEqual(ram["classification"], contract["classification"])
        self.assertEqual(ram["fields"], contract["fields"])
        self.assertEqual(len(condition), 1)
        self.assertEqual(
            {key: condition[0][key] for key in ("id", "when", "activation", "target")},
            contract["condition"],
        )
        self.assertTrue(
            set(contract["retiredProfileIds"]).isdisjoint(profiles)
        )

    def test_ram_target_acceleration_and_speed_drift_fail(self) -> None:
        mutations = {
            "target": ("chillTarget", "OW_WILD_BEHAVIOR_TARGET_NONE"),
            "acceleration": ("ramAccelerationSteps", 0),
            "max-speed": ("ramMaxSpeed", 0),
        }
        for label, (field, value) in mutations.items():
            with self.subTest(label=label):
                catalog = copy.deepcopy(self.catalog)
                ram = next(
                    profile for profile in catalog["profiles"]
                    if profile["id"] == "ram"
                )
                ram["fields"][field]["value"] = value
                with self.assertRaisesRegex(
                    ManifestError,
                    "target exact profile contract drift: ram",
                ):
                    _validate_exact_profile_contracts(catalog, self.manifest)

    def test_target_application_targetlessness_drift_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        application = next(
            item for item in catalog["applications"] if "target" not in item
        )
        application["target"] = copy.deepcopy(
            next(
                item["target"]
                for item in catalog["applications"]
                if "target" in item
            )
        )
        with self.assertRaisesRegex(ManifestError, "target memberships contract drift"):
            validate_catalog_state(catalog, self.manifest)

    def test_target_condition_subject_drift_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        profile = next(item for item in catalog["profiles"] if item.get("conditions"))
        profile["conditions"][0]["subjects"] = copy.deepcopy(
            profile["conditions"][-1]["subjects"]
        )
        if len(profile["conditions"]) == 1:
            profile["conditions"][0]["subjects"]["members"].pop()
        with self.assertRaisesRegex(ManifestError, "target memberships contract drift"):
            validate_catalog_state(catalog, self.manifest)

    def test_target_condition_activation_target_and_vision_drift_fail(self) -> None:
        mutations = {
            "activation": lambda condition: condition["activation"].update(
                {"durationFrames": condition["activation"]["durationFrames"] + 1}
            ),
            "target": lambda condition: condition["target"].update({"kind": "none"}),
            "Vision": lambda condition: condition["when"].update(
                {"vision": {"mode": "custom", "range": 9,
                            "cone": "forward-90", "adjacentAwareness": False}}
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                catalog = copy.deepcopy(self.catalog)
                profile = next(
                    item for item in catalog["profiles"]
                    if item.get("conditions")
                    and "vision" in item["conditions"][0]["when"]
                )
                mutate(profile["conditions"][0])
                with self.assertRaisesRegex(
                    ManifestError,
                    "target conditions contract drift",
                ):
                    validate_catalog_state(catalog, self.manifest)

    def test_target_runtime_binding_drift_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["runtimeBindings"]["speciesSelectors"].reverse()
        with self.assertRaisesRegex(ManifestError, "target runtime-bindings contract drift"):
            validate_catalog_state(catalog, self.manifest)

    def test_missing_source_profile_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["profiles"].pop()
        with self.assertRaisesRegex(ManifestError, "missing source profile"):
            validate_catalog_state(catalog, self.manifest)

    def test_unknown_source_profile_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["profiles"].append(
            {"id": "unknown-profile", "name": "Unknown", "fields": {}}
        )
        with self.assertRaisesRegex(ManifestError, "unknown source profile"):
            validate_catalog_state(catalog, self.manifest)

    def test_duplicate_target_application_fails(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["target"]["applications"][1]["id"] = (
            manifest["target"]["applications"][0]["id"]
        )
        with self.assertRaisesRegex(ManifestError, "duplicate target application"):
            validate_manifest(manifest)

    def test_duplicate_target_destination_fails(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["target"]["applications"][1]["profile"] = (
            manifest["target"]["applications"][0]["profile"]
        )
        with self.assertRaisesRegex(
            ManifestError, "duplicate target destination profile"
        ):
            validate_manifest(manifest)

    def test_group_order_violation_fails(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["target"]["applications"][0]["classification"] = "placement"
        with self.assertRaisesRegex(ManifestError, "group-order violation"):
            validate_manifest(manifest)

    def test_precedence_violation_fails(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        applications = manifest["target"]["applications"]
        startled = next(
            i for i, item in enumerate(applications)
            if item["id"] == "apply-startled"
        )
        skittish = next(
            i for i, item in enumerate(applications)
            if item["id"] == "apply-skittish"
        )
        applications[startled], applications[skittish] = (
            applications[skittish],
            applications[startled],
        )
        for order, application in enumerate(applications, 1):
            application["order"] = order
        with self.assertRaisesRegex(ManifestError, "precedence violation"):
            validate_manifest(manifest)

    def test_condition_precedence_violation_fails(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["target"]["conditionOrder"]["playful"].reverse()
        with self.assertRaisesRegex(ManifestError, "precedence violation"):
            validate_manifest(manifest)

    def test_more_than_32_applications_fails(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        applications = manifest["target"]["applications"]
        for number in range(28, 34):
            applications.append(
                {
                    "order": number,
                    "id": f"apply-overflow-{number}",
                    "profile": f"overflow-{number}",
                    "name": f"Overflow {number}",
                    "classification": "modifier",
                    "badges": [],
                }
            )
        manifest["target"]["applicationCount"] = len(applications)
        with self.assertRaisesRegex(ManifestError, "maximum is 32"):
            validate_manifest(manifest)

    def test_partial_migration_fails(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["applications"][0]["id"] = "apply-teleport"
        with self.assertRaisesRegex(ManifestError, "partial or unknown catalog state"):
            validate_catalog_state(catalog, self.manifest)


if __name__ == "__main__":
    unittest.main()

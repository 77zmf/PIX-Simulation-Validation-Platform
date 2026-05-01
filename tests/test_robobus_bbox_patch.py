from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RobobusBboxPatchTest(unittest.TestCase):
    def test_patch_targets_carla_actor_dispatcher(self) -> None:
        patch_path = (
            REPO_ROOT
            / "assets"
            / "vehicles"
            / "robobus117th"
            / "patches"
            / "carla_0_9_15_robobus_bbox_override.patch"
        )
        payload = patch_path.read_text(encoding="utf-8")

        self.assertIn("Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Actor/ActorDispatcher.cpp", payload)
        self.assertIn('TEXT("vehicle.pixmoving.robobus")', payload)
        self.assertIn("FVector ExtentCm(191.0f, 95.5f, 110.45f)", payload)
        self.assertIn("RegisterActor(*Result.Actor", payload)

    def test_editor_commandlet_guard_patch_excludes_shipping_build(self) -> None:
        patch_path = (
            REPO_ROOT
            / "assets"
            / "vehicles"
            / "robobus117th"
            / "patches"
            / "carla_0_9_15_robobus_editor_commandlet_guard.patch"
        )
        payload = patch_path.read_text(encoding="utf-8")

        self.assertIn("RobobusVisualAuthorCommandlet.cpp", payload)
        self.assertIn("#if WITH_EDITOR", payload)
        self.assertIn("commandlet is editor-only", payload)

    def test_apply_script_points_at_patch(self) -> None:
        script_path = (
            REPO_ROOT
            / "assets"
            / "vehicles"
            / "robobus117th"
            / "scripts"
            / "apply_robobus_bbox_override_to_carla.sh"
        )
        payload = script_path.read_text(encoding="utf-8")

        self.assertIn("carla_0_9_15_robobus_bbox_override.patch", payload)
        self.assertIn("carla_0_9_15_robobus_editor_commandlet_guard.patch", payload)
        self.assertIn("--dry-run", payload)
        self.assertIn("--reverse", payload)


if __name__ == "__main__":
    unittest.main()

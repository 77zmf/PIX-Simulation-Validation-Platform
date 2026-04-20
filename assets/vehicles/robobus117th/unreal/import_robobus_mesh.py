"""UE4.26 editor helper for importing the robobus117th visual mesh.

Run from UE4 Editor Python after opening CARLA 0.9.15's CarlaUE4.uproject.
This imports mesh inputs only; vehicle blueprint wiring, physics assets, and
wheel blueprints still need UE4 authoring and verification.
"""

from __future__ import annotations

import os
from pathlib import Path

import unreal  # type: ignore


SOURCE_PACKAGE = Path(os.environ.get("ROBOBUS_SOURCE_PACKAGE", "artifacts/carla_blueprints/robobus117th_source"))
DEST_PATH = os.environ.get(
    "ROBOBUS_UNREAL_DEST",
    "/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/SourceMesh",
)


def pick_mesh() -> Path:
    candidates = [
        SOURCE_PACKAGE / "unreal_import" / "robobus.fbx",
        SOURCE_PACKAGE / "unreal_import" / "robobus.obj",
        SOURCE_PACKAGE / "unreal_import" / "robobus.dae",
        SOURCE_PACKAGE / "source" / "install" / "robobus_description" / "mesh" / "robobus.dae",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"No robobus mesh input found under {SOURCE_PACKAGE}")


def import_mesh(mesh_path: Path) -> None:
    task = unreal.AssetImportTask()
    task.filename = str(mesh_path)
    task.destination_path = DEST_PATH
    task.automated = True
    task.save = True
    task.replace_existing = True

    if mesh_path.suffix.lower() == ".fbx":
        options = unreal.FbxImportUI()
        options.import_mesh = True
        options.import_as_skeletal = False
        options.import_materials = True
        options.import_textures = True
        task.options = options

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    unreal.EditorAssetLibrary.save_directory(DEST_PATH)


def main() -> None:
    mesh = pick_mesh()
    unreal.log(f"Importing robobus117th mesh: {mesh}")
    unreal.log(f"Destination: {DEST_PATH}")
    import_mesh(mesh)
    unreal.log("Robobus117th mesh import finished. Continue with BP_Robobus117th, wheels, collision, and physics setup.")


main()

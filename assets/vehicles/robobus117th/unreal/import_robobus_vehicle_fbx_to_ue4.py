"""Import the rigged Robobus117th vehicle FBX into CARLA UE4.

Run from UE4.26 with CARLA's CarlaUE4.uproject. This imports the rigged
skeletal vehicle FBX generated from the Autoware visual mesh and Blender
wheel-bone helper. The source FBX comes in oversized in CARLA/UE4 unless an
import scale is applied, so the default import scale is 0.001 and the vehicle
blueprint component should remain at scale 1.0.
"""

from __future__ import annotations

import os
from pathlib import Path

import unreal  # type: ignore


PREFIX = "ZMF_ROBOBUS_IMPORT "
SOURCE_PACKAGE = Path(
    os.environ.get(
        "ROBOBUS_SOURCE_PACKAGE",
        "/home/pixmoving/PIX-Simulation-Validation-Platform/artifacts/carla_blueprints/robobus117th_source",
    )
)
SOURCE_FBX = Path(os.environ.get("ROBOBUS_SKELETAL_FBX", str(SOURCE_PACKAGE / "carla_vehicle_import" / "SKM_robobus117th.fbx")))
DEST = os.environ.get("ROBOBUS_STATIC_DEST", "/Game/Carla/Static/Vehicles/4Wheeled/Robobus117th")
IMPORT_SCALE = float(os.environ.get("ROBOBUS_IMPORT_UNIFORM_SCALE", "0.001"))
IMPORT_ROTATION_PITCH = float(os.environ.get("ROBOBUS_IMPORT_ROTATION_PITCH", "0.0"))
IMPORT_ROTATION_YAW = float(os.environ.get("ROBOBUS_IMPORT_ROTATION_YAW", "0.0"))
IMPORT_ROTATION_ROLL = float(os.environ.get("ROBOBUS_IMPORT_ROTATION_ROLL", "0.0"))
DELETE_EXISTING = os.environ.get("ROBOBUS_DELETE_EXISTING_SKM", "1") not in {"0", "false", "False"}
TARGET_SKELETON = os.environ.get("ROBOBUS_IMPORT_SKELETON", "").strip()
CREATE_PHYSICS_ASSET = os.environ.get("ROBOBUS_CREATE_PHYSICS_ASSET", "1") not in {"0", "false", "False"}

OLD_ASSETS = [
    DEST + "/SKM_robobus117th",
    DEST + "/SKM_robobus117th_Object_________1_6_PhysicsAsset",
    DEST + "/SKM_robobus117th_Object_________1_6_Skeleton",
]


def log(message: object) -> None:
    unreal.log(PREFIX + str(message))


def warn(message: object) -> None:
    unreal.log_warning(PREFIX + str(message))


def set_if_present(obj: object, prop: str, value: object) -> None:
    try:
        obj.set_editor_property(prop, value)
        log(f"SET {obj}.{prop}={value}")
    except Exception as exc:
        warn(f"SET_SKIP {obj}.{prop}: {exc}")


def delete_existing_assets() -> None:
    for path in OLD_ASSETS:
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            log(f"DELETE {path}")
            if not unreal.EditorAssetLibrary.delete_asset(path):
                raise RuntimeError(f"Failed to delete existing asset: {path}")
        else:
            log(f"DELETE_SKIP missing {path}")


def import_skeletal_fbx() -> None:
    if not SOURCE_FBX.is_file():
        raise FileNotFoundError(f"Robobus skeletal FBX not found: {SOURCE_FBX}")

    unreal.EditorAssetLibrary.make_directory(DEST)

    task = unreal.AssetImportTask()
    task.filename = str(SOURCE_FBX)
    task.destination_path = DEST
    task.automated = True
    task.save = True
    task.replace_existing = True

    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = True
    options.import_materials = True
    options.import_textures = False
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    set_if_present(options, "create_physics_asset", CREATE_PHYSICS_ASSET)
    if TARGET_SKELETON:
        skeleton = unreal.load_object(None, TARGET_SKELETON)
        if not skeleton:
            raise RuntimeError(f"Could not load target skeleton: {TARGET_SKELETON}")
        set_if_present(options, "skeleton", skeleton)
        log(f"TARGET_SKELETON {TARGET_SKELETON}")

    import_data = options.skeletal_mesh_import_data
    set_if_present(import_data, "import_uniform_scale", IMPORT_SCALE)
    set_if_present(
        import_data,
        "import_rotation",
        unreal.Rotator(
            pitch=IMPORT_ROTATION_PITCH,
            yaw=IMPORT_ROTATION_YAW,
            roll=IMPORT_ROTATION_ROLL,
        ),
    )
    set_if_present(import_data, "normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    set_if_present(import_data, "import_meshes_in_bone_hierarchy", True)
    set_if_present(import_data, "convert_scene", True)
    set_if_present(import_data, "convert_scene_unit", True)
    set_if_present(import_data, "force_front_x_axis", False)

    task.options = options
    log(f"IMPORT_FILE {SOURCE_FBX}")
    log(f"IMPORT_DEST {DEST}")
    log(f"IMPORT_SCALE {IMPORT_SCALE}")
    log(f"CREATE_PHYSICS_ASSET {CREATE_PHYSICS_ASSET}")
    log(f"IMPORT_ROTATION pitch={IMPORT_ROTATION_PITCH} yaw={IMPORT_ROTATION_YAW} roll={IMPORT_ROTATION_ROLL}")
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    log(f"IMPORTED_OBJECT_PATHS {list(task.imported_object_paths)}")
    unreal.EditorAssetLibrary.save_directory(DEST)


def main() -> None:
    if DELETE_EXISTING:
        delete_existing_assets()
    import_skeletal_fbx()
    log("DONE")


main()

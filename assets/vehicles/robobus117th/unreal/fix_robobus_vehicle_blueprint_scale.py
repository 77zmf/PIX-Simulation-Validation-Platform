"""Fix Robobus117th UE4 blueprint transform after FBX import.

Run from UE4.26 with CARLA's CarlaUE4.uproject. The imported FBX is valid
visually, but the FBX unit conversion must be handled at import time. After
the skeletal FBX is imported with the correct uniform scale, the vehicle mesh
component itself should stay at scale 1.0 so CARLA actor bounds and physics
do not get scaled independently from the visual model.
"""

from __future__ import annotations

import os

import unreal  # type: ignore


PREFIX = "ZMF_ROBOBUS_SCALE "
BP_ASSET = "/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/BP_Robobus117th"
BP_CLASS = BP_ASSET + ".BP_Robobus117th_C"
VEHICLE_FACTORY = "/Game/Carla/Blueprints/Vehicles/VehicleFactory"
TARGET_SCALE = float(os.environ.get("ROBOBUS_COMPONENT_SCALE", "1.0"))
TARGET_OFFSET_X = float(os.environ.get("ROBOBUS_COMPONENT_OFFSET_X", "0.0"))
TARGET_OFFSET_Y = float(os.environ.get("ROBOBUS_COMPONENT_OFFSET_Y", "11.23"))
TARGET_OFFSET_Z = float(os.environ.get("ROBOBUS_COMPONENT_OFFSET_Z", "220.72"))
TARGET_ROTATION_PITCH = float(os.environ.get("ROBOBUS_COMPONENT_ROTATION_PITCH", "0.0"))
TARGET_ROTATION_YAW = float(os.environ.get("ROBOBUS_COMPONENT_ROTATION_YAW", "0.0"))
TARGET_ROTATION_ROLL = float(os.environ.get("ROBOBUS_COMPONENT_ROTATION_ROLL", "90.0"))


def log(message: object) -> None:
    unreal.log(PREFIX + str(message))


def load_required_object(path: str):
    obj = unreal.load_object(None, path)
    if not obj:
        raise RuntimeError(f"Could not load object: {path}")
    return obj


def save_asset(path: str) -> None:
    try:
        ok = unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    except TypeError:
        ok = unreal.EditorAssetLibrary.save_asset(path)
    log(f"SAVE {path} ok={ok}")
    if not ok:
        raise RuntimeError(f"Failed to save asset: {path}")


def main() -> None:
    bp_cls = load_required_object(BP_CLASS)
    cdo = unreal.get_default_object(bp_cls)
    mesh = cdo.get_editor_property("mesh")
    movement = cdo.get_editor_property("vehicle_movement")

    old_scale = mesh.get_editor_property("relative_scale3d")
    old_location = mesh.get_editor_property("relative_location")
    old_rotation = mesh.get_editor_property("relative_rotation")
    old_bounds_scale = None
    try:
        old_bounds_scale = mesh.get_editor_property("bounds_scale")
    except Exception:
        pass

    mesh.set_editor_property("relative_scale3d", unreal.Vector(TARGET_SCALE, TARGET_SCALE, TARGET_SCALE))
    mesh.set_editor_property("relative_location", unreal.Vector(TARGET_OFFSET_X, TARGET_OFFSET_Y, TARGET_OFFSET_Z))
    mesh.set_editor_property(
        "relative_rotation",
        unreal.Rotator(TARGET_ROTATION_PITCH, TARGET_ROTATION_YAW, TARGET_ROTATION_ROLL),
    )
    try:
        mesh.set_editor_property("bounds_scale", 1.0)
    except Exception as exc:
        log(f"BOUNDS_SCALE_SKIP {exc}")

    # Keep movement dimensions aligned with the 117th vehicle spec in cm.
    for prop, value in [
        ("mass", 1800.0),
        ("drag_coefficient", 0.35),
        ("chassis_width", 191.0),
        ("chassis_height", 220.9),
    ]:
        movement.set_editor_property(prop, value)

    save_asset(BP_ASSET)
    save_asset(VEHICLE_FACTORY)

    new_scale = mesh.get_editor_property("relative_scale3d")
    new_location = mesh.get_editor_property("relative_location")
    new_rotation = mesh.get_editor_property("relative_rotation")
    new_bounds_scale = None
    try:
        new_bounds_scale = mesh.get_editor_property("bounds_scale")
    except Exception:
        pass

    log(f"BLUEPRINT={BP_ASSET}")
    log(f"MESH_SCALE_BEFORE={old_scale}")
    log(f"MESH_SCALE_AFTER={new_scale}")
    log(f"MESH_LOCATION_BEFORE={old_location}")
    log(f"MESH_LOCATION_AFTER={new_location}")
    log(f"MESH_ROTATION_BEFORE={old_rotation}")
    log(f"MESH_ROTATION_AFTER={new_rotation}")
    log(f"BOUNDS_SCALE_BEFORE={old_bounds_scale}")
    log(f"BOUNDS_SCALE_AFTER={new_bounds_scale}")
    log(f"MOVEMENT mass={movement.get_editor_property('mass')} chassis_width={movement.get_editor_property('chassis_width')} chassis_height={movement.get_editor_property('chassis_height')}")
    log("DONE")


main()

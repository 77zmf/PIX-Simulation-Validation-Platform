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
TARGET_SKELETAL_MESH = os.environ.get("ROBOBUS_SKELETAL_MESH", "").strip()
TARGET_PHYSICS_ASSET_OVERRIDE = os.environ.get("ROBOBUS_PHYSICS_ASSET_OVERRIDE")
TUNE_BODY_INSTANCE = os.environ.get("ROBOBUS_TUNE_BODY_INSTANCE", "0") in {"1", "true", "True"}
TARGET_BODY_MASS_KG = float(os.environ.get("ROBOBUS_BODY_MASS_KG", "1800.0"))
TARGET_BODY_LINEAR_DAMPING = float(os.environ.get("ROBOBUS_BODY_LINEAR_DAMPING", "0.2"))
TARGET_BODY_ANGULAR_DAMPING = float(os.environ.get("ROBOBUS_BODY_ANGULAR_DAMPING", "4.0"))
TARGET_BODY_COM_X = float(os.environ.get("ROBOBUS_BODY_COM_X", "0.0"))
TARGET_BODY_COM_Y = float(os.environ.get("ROBOBUS_BODY_COM_Y", "0.0"))
TARGET_BODY_COM_Z = float(os.environ.get("ROBOBUS_BODY_COM_Z", "-80.0"))
TARGET_BODY_INERTIA_SCALE = float(os.environ.get("ROBOBUS_BODY_INERTIA_SCALE", "3.0"))
TARGET_BODY_MAX_ANGULAR_VELOCITY = float(os.environ.get("ROBOBUS_BODY_MAX_ANGULAR_VELOCITY", "720.0"))


def log(message: object) -> None:
    unreal.log(PREFIX + str(message))


def load_required_object(path: str):
    obj = unreal.load_object(None, path)
    if not obj:
        raise RuntimeError(f"Could not load object: {path}")
    return obj


def load_optional_override(path: str):
    value = path.strip()
    if value.lower() in {"", "none", "null"}:
        return None
    return load_required_object(value)


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

    old_skeletal_mesh = None
    try:
        old_skeletal_mesh = mesh.get_editor_property("skeletal_mesh")
    except Exception as exc:
        log(f"SKELETAL_MESH_READ_SKIP {exc}")

    if TARGET_SKELETAL_MESH:
        new_skeletal_mesh = load_required_object(TARGET_SKELETAL_MESH)
        mesh.set_editor_property("skeletal_mesh", new_skeletal_mesh)
        log(f"SKELETAL_MESH_SET {TARGET_SKELETAL_MESH}")

    old_physics_asset_override = None
    try:
        old_physics_asset_override = mesh.get_editor_property("physics_asset_override")
    except Exception as exc:
        log(f"PHYSICS_ASSET_OVERRIDE_READ_SKIP {exc}")

    if TARGET_PHYSICS_ASSET_OVERRIDE is not None:
        override_asset = load_optional_override(TARGET_PHYSICS_ASSET_OVERRIDE)
        mesh.set_editor_property("physics_asset_override", override_asset)
        log(f"PHYSICS_ASSET_OVERRIDE_SET {override_asset}")

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
        unreal.Rotator(
            pitch=TARGET_ROTATION_PITCH,
            yaw=TARGET_ROTATION_YAW,
            roll=TARGET_ROTATION_ROLL,
        ),
    )
    try:
        mesh.set_editor_property("bounds_scale", 1.0)
    except Exception as exc:
        log(f"BOUNDS_SCALE_SKIP {exc}")

    if TUNE_BODY_INSTANCE:
        body_instance = mesh.get_editor_property("body_instance")
        for prop, value in [
            ("override_mass", True),
            ("mass_in_kg_override", TARGET_BODY_MASS_KG),
            ("linear_damping", TARGET_BODY_LINEAR_DAMPING),
            ("angular_damping", TARGET_BODY_ANGULAR_DAMPING),
            ("com_nudge", unreal.Vector(TARGET_BODY_COM_X, TARGET_BODY_COM_Y, TARGET_BODY_COM_Z)),
            (
                "inertia_tensor_scale",
                unreal.Vector(TARGET_BODY_INERTIA_SCALE, TARGET_BODY_INERTIA_SCALE, TARGET_BODY_INERTIA_SCALE),
            ),
            ("max_angular_velocity", TARGET_BODY_MAX_ANGULAR_VELOCITY),
        ]:
            body_instance.set_editor_property(prop, value)
        mesh.set_editor_property("body_instance", body_instance)
        log(
            "BODY_INSTANCE "
            f"mass={TARGET_BODY_MASS_KG} linear_damping={TARGET_BODY_LINEAR_DAMPING} "
            f"angular_damping={TARGET_BODY_ANGULAR_DAMPING} "
            f"com=({TARGET_BODY_COM_X},{TARGET_BODY_COM_Y},{TARGET_BODY_COM_Z}) "
            f"inertia_scale={TARGET_BODY_INERTIA_SCALE}"
        )
    else:
        log("BODY_INSTANCE_SKIP disabled")

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
    new_skeletal_mesh = None
    try:
        new_skeletal_mesh = mesh.get_editor_property("skeletal_mesh")
    except Exception as exc:
        log(f"SKELETAL_MESH_AFTER_READ_SKIP {exc}")
    new_physics_asset_override = None
    try:
        new_physics_asset_override = mesh.get_editor_property("physics_asset_override")
    except Exception as exc:
        log(f"PHYSICS_ASSET_OVERRIDE_AFTER_READ_SKIP {exc}")
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
    log(f"SKELETAL_MESH_BEFORE={old_skeletal_mesh}")
    log(f"SKELETAL_MESH_AFTER={new_skeletal_mesh}")
    log(f"PHYSICS_ASSET_OVERRIDE_BEFORE={old_physics_asset_override}")
    log(f"PHYSICS_ASSET_OVERRIDE_AFTER={new_physics_asset_override}")
    log(f"BOUNDS_SCALE_BEFORE={old_bounds_scale}")
    log(f"BOUNDS_SCALE_AFTER={new_bounds_scale}")
    log(f"MOVEMENT mass={movement.get_editor_property('mass')} chassis_width={movement.get_editor_property('chassis_width')} chassis_height={movement.get_editor_property('chassis_height')}")
    log("DONE")


main()

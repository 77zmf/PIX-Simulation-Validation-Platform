"""Experimentally wire the Robobus117th PIX mesh into the CARLA vehicle path.

Run from UE4.26 with CARLA's ``CarlaUE4.uproject`` after the PIX skeletal
mesh has been imported against the Mitsubishi FusoRosa skeleton. This keeps
the known-good CARLA vehicle animation blueprint and carrier physics, but
replaces the visible ``VehicleMesh`` with the PIX mesh so wheel animation is
driven by the standard WheelHandler path instead of a detached visual shell.

This is intentionally guarded because the 2026-04-19 runtime experiment proved
that the imported PIX mesh can be loaded and cooked, but direct replacement of
``VehicleMesh`` causes ``vehicle.pixmoving.robobus`` spawn failure. Keep the
stable runtime on the existing spawnable blueprint unless the experiment is
explicitly enabled and followed by CARLA spawn validation.
"""

from __future__ import annotations

import os

import unreal  # type: ignore


PREFIX = "ZMF_ROBOBUS_NATIVE_MESH "

BP_ASSET = os.environ.get(
    "ROBOBUS_BP_ASSET",
    "/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/BP_Robobus117th",
)
BP_CLASS = BP_ASSET + ".BP_Robobus117th_C"

TARGET_SKELETAL_MESH = os.environ.get(
    "ROBOBUS_NATIVE_SKELETAL_MESH",
    (
        "/Game/Carla/Static/Vehicles/4Wheeled/Robobus117thFusoSkelScale1/"
        "SKM_robobus117th_axis_safe."
        "SKM_robobus117th_axis_safe_robobus_part_000_Object_________1_6"
    ),
)
TARGET_ANIM_CLASS = os.environ.get(
    "ROBOBUS_NATIVE_ANIM_CLASS",
    "/Game/Carla/Static/Bus/Mitsubishi_FusoRosa/AnimBP_FusoRosa.AnimBP_FusoRosa_C",
)
TARGET_PHYSICS_ASSET = os.environ.get(
    "ROBOBUS_NATIVE_PHYSICS_ASSET",
    "/Game/Carla/Static/Bus/Mitsubishi_FusoRosa/Phys_FusoRosa.Phys_FusoRosa",
)

TARGET_OFFSET_X = float(os.environ.get("ROBOBUS_NATIVE_OFFSET_X", "0.0"))
TARGET_OFFSET_Y = float(os.environ.get("ROBOBUS_NATIVE_OFFSET_Y", "0.0"))
TARGET_OFFSET_Z = float(os.environ.get("ROBOBUS_NATIVE_OFFSET_Z", "0.0"))
TARGET_ROTATION_PITCH = float(os.environ.get("ROBOBUS_NATIVE_ROTATION_PITCH", "0.0"))
TARGET_ROTATION_YAW = float(os.environ.get("ROBOBUS_NATIVE_ROTATION_YAW", "0.0"))
TARGET_ROTATION_ROLL = float(os.environ.get("ROBOBUS_NATIVE_ROTATION_ROLL", "0.0"))
TARGET_SCALE = float(os.environ.get("ROBOBUS_NATIVE_SCALE", "1.0"))

VEHICLE_FACTORY = "/Game/Carla/Blueprints/Vehicles/VehicleFactory"
ALLOW_EXPERIMENT = os.environ.get("ROBOBUS_NATIVE_ALLOW_EXPERIMENT", "0") in {"1", "true", "True"}


def log(message: object) -> None:
    unreal.log(PREFIX + str(message))


def load_required_object(path: str):
    obj = unreal.load_object(None, path)
    if not obj:
        raise RuntimeError(f"Could not load object: {path}")
    return obj


def object_path(obj: object) -> str:
    if obj is None:
        return "None"
    try:
        return obj.get_path_name()
    except Exception:
        return str(obj)


def save_asset(path: str) -> None:
    try:
        ok = unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    except TypeError:
        ok = unreal.EditorAssetLibrary.save_asset(path)
    log(f"SAVE {path} ok={ok}")
    if not ok:
        raise RuntimeError(f"Failed to save asset: {path}")


def get_optional_editor_property(obj: object, prop: str):
    try:
        return obj.get_editor_property(prop)
    except Exception as exc:
        log(f"GET_SKIP {object_path(obj)}.{prop}: {exc}")
        return None


def main() -> None:
    if not ALLOW_EXPERIMENT:
        raise RuntimeError(
            "Native PIX VehicleMesh replacement is guarded because it is not yet "
            "stable-spawnable. Set ROBOBUS_NATIVE_ALLOW_EXPERIMENT=1 only for a "
            "backed-up UE4 experiment, then run CARLA spawn validation before deploy."
        )

    bp_cls = load_required_object(BP_CLASS)
    skeletal_mesh = load_required_object(TARGET_SKELETAL_MESH)
    anim_class = load_required_object(TARGET_ANIM_CLASS)
    physics_asset = load_required_object(TARGET_PHYSICS_ASSET)

    cdo = unreal.get_default_object(bp_cls)
    mesh = cdo.get_editor_property("mesh")
    movement = cdo.get_editor_property("vehicle_movement")

    old_skeletal_mesh = get_optional_editor_property(mesh, "skeletal_mesh")
    old_anim_class = get_optional_editor_property(mesh, "anim_class")
    old_anim_mode = get_optional_editor_property(mesh, "animation_mode")
    old_physics = get_optional_editor_property(mesh, "physics_asset_override")

    mesh.set_editor_property("skeletal_mesh", skeletal_mesh)
    mesh.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_BLUEPRINT)
    mesh.set_editor_property("anim_class", anim_class)
    mesh.set_editor_property("physics_asset_override", physics_asset)
    mesh.set_editor_property("relative_location", unreal.Vector(TARGET_OFFSET_X, TARGET_OFFSET_Y, TARGET_OFFSET_Z))
    mesh.set_editor_property(
        "relative_rotation",
        unreal.Rotator(
            pitch=TARGET_ROTATION_PITCH,
            yaw=TARGET_ROTATION_YAW,
            roll=TARGET_ROTATION_ROLL,
        ),
    )
    mesh.set_editor_property("relative_scale3d", unreal.Vector(TARGET_SCALE, TARGET_SCALE, TARGET_SCALE))
    try:
        mesh.set_editor_property("bounds_scale", 1.0)
    except Exception as exc:
        log(f"BOUNDS_SCALE_SKIP {exc}")

    for prop, value in [
        ("mass", 1800.0),
        ("drag_coefficient", 0.35),
        ("chassis_width", 191.0),
        ("chassis_height", 220.9),
    ]:
        movement.set_editor_property(prop, value)

    save_asset(BP_ASSET)
    save_asset(VEHICLE_FACTORY)

    new_skeletal_mesh = get_optional_editor_property(mesh, "skeletal_mesh")
    new_anim_class = get_optional_editor_property(mesh, "anim_class")
    new_anim_mode = get_optional_editor_property(mesh, "animation_mode")
    new_physics = get_optional_editor_property(mesh, "physics_asset_override")
    new_location = get_optional_editor_property(mesh, "relative_location")
    new_rotation = get_optional_editor_property(mesh, "relative_rotation")
    new_scale = get_optional_editor_property(mesh, "relative_scale3d")

    log(f"BLUEPRINT={BP_ASSET}")
    log(f"SKELETAL_MESH_BEFORE={object_path(old_skeletal_mesh)}")
    log(f"SKELETAL_MESH_AFTER={object_path(new_skeletal_mesh)}")
    log(f"ANIM_MODE_BEFORE={old_anim_mode}")
    log(f"ANIM_MODE_AFTER={new_anim_mode}")
    log(f"ANIM_CLASS_BEFORE={object_path(old_anim_class)}")
    log(f"ANIM_CLASS_AFTER={object_path(new_anim_class)}")
    log(f"PHYSICS_ASSET_BEFORE={object_path(old_physics)}")
    log(f"PHYSICS_ASSET_AFTER={object_path(new_physics)}")
    log(f"MESH_LOCATION_AFTER={new_location}")
    log(f"MESH_ROTATION_AFTER={new_rotation}")
    log(f"MESH_SCALE_AFTER={new_scale}")
    log(
        "MOVEMENT "
        f"mass={movement.get_editor_property('mass')} "
        f"width={movement.get_editor_property('chassis_width')} "
        f"height={movement.get_editor_property('chassis_height')}"
    )
    log("DONE")


main()

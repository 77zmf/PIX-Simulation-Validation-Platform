"""Create and tune Robobus117th CARLA wheel blueprints.

Run from UE4.26 with CARLA's CarlaUE4.uproject after the Robobus vehicle
blueprint exists. The script duplicates stable Fuso wheel blueprints into the
PIX namespace, tunes their collision radius/width to the Robobus mesh, and
wires the vehicle movement component to those PIX wheel classes.
"""

from __future__ import annotations

import os

import unreal  # type: ignore


PREFIX = "ZMF_ROBOBUS_WHEELS "
BP_ASSET = "/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/BP_Robobus117th"
BP_CLASS = BP_ASSET + ".BP_Robobus117th_C"
DEST_DIR = "/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th"
FRONT_RADIUS_CM = float(os.environ.get("ROBOBUS_FRONT_WHEEL_RADIUS_CM", "32.3"))
REAR_RADIUS_CM = float(os.environ.get("ROBOBUS_REAR_WHEEL_RADIUS_CM", "32.3"))
FRONT_WIDTH_CM = float(os.environ.get("ROBOBUS_FRONT_WHEEL_WIDTH_CM", "25.0"))
REAR_WIDTH_CM = float(os.environ.get("ROBOBUS_REAR_WHEEL_WIDTH_CM", "25.0"))
FRONT_STEER_DEG = float(os.environ.get("ROBOBUS_FRONT_STEER_DEG", "28.991"))

WHEELS = [
    {
        "name": "FLW",
        "source": "/Game/Carla/Blueprints/Vehicles/MitsubishiFusoRosa/BP_FusoRosa_FLW",
        "bone": "Wheel_Front_Left",
        "radius": FRONT_RADIUS_CM,
        "width": FRONT_WIDTH_CM,
        "steer_angle": FRONT_STEER_DEG,
        "disable_steering": False,
    },
    {
        "name": "FRW",
        "source": "/Game/Carla/Blueprints/Vehicles/MitsubishiFusoRosa/BP_FusoRosa_FRW",
        "bone": "Wheel_Front_Right",
        "radius": FRONT_RADIUS_CM,
        "width": FRONT_WIDTH_CM,
        "steer_angle": FRONT_STEER_DEG,
        "disable_steering": False,
    },
    {
        "name": "RLW",
        "source": "/Game/Carla/Blueprints/Vehicles/MitsubishiFusoRosa/BP_FusoRosa_RLW",
        "bone": "Wheel_Rear_Left",
        "radius": REAR_RADIUS_CM,
        "width": REAR_WIDTH_CM,
        "steer_angle": 0.0,
        "disable_steering": True,
    },
    {
        "name": "RRW",
        "source": "/Game/Carla/Blueprints/Vehicles/MitsubishiFusoRosa/BP_FusoRosa_RRW",
        "bone": "Wheel_Rear_Right",
        "radius": REAR_RADIUS_CM,
        "width": REAR_WIDTH_CM,
        "steer_angle": 0.0,
        "disable_steering": True,
    },
]


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


def set_if_present(obj: object, prop: str, value: object) -> None:
    try:
        obj.set_editor_property(prop, value)
        log(f"SET {obj}.{prop}={value}")
    except Exception as exc:
        log(f"SET_SKIP {obj}.{prop}: {exc}")


def ensure_wheel_asset(spec: dict[str, object]) -> str:
    dest = f"{DEST_DIR}/BP_Robobus117th_{spec['name']}"
    if not unreal.EditorAssetLibrary.does_asset_exist(dest):
        log(f"DUPLICATE {spec['source']} -> {dest}")
        duplicated = unreal.EditorAssetLibrary.duplicate_asset(str(spec["source"]), dest)
        if not duplicated:
            raise RuntimeError(f"Failed to duplicate wheel asset: {dest}")
    else:
        log(f"DUPLICATE_SKIP exists {dest}")

    wheel_cls = load_required_object(dest + f".BP_Robobus117th_{spec['name']}_C")
    cdo = unreal.get_default_object(wheel_cls)
    set_if_present(cdo, "shape_radius", float(spec["radius"]))
    set_if_present(cdo, "shape_width", float(spec["width"]))
    set_if_present(cdo, "steer_angle", float(spec["steer_angle"]))
    set_if_present(cdo, "mass", 20.0)
    set_if_present(cdo, "damping_rate", 0.35)
    set_if_present(cdo, "lat_stiff_max_load", 5.0)
    set_if_present(cdo, "lat_stiff_value", 20.0)
    set_if_present(cdo, "long_stiff_value", 3000.0)
    save_asset(dest)
    return dest + f".BP_Robobus117th_{spec['name']}_C"


def main() -> None:
    unreal.EditorAssetLibrary.make_directory(DEST_DIR)
    wheel_classes = [ensure_wheel_asset(spec) for spec in WHEELS]

    bp_cls = load_required_object(BP_CLASS)
    cdo = unreal.get_default_object(bp_cls)
    movement = cdo.get_editor_property("vehicle_movement")
    wheel_setups = list(movement.get_editor_property("wheel_setups"))
    if len(wheel_setups) < len(WHEELS):
        raise RuntimeError(f"Expected at least {len(WHEELS)} wheel setups, got {len(wheel_setups)}")

    for setup, spec, class_path in zip(wheel_setups, WHEELS, wheel_classes):
        wheel_cls = load_required_object(class_path)
        setup.set_editor_property("wheel_class", wheel_cls)
        setup.set_editor_property("bone_name", spec["bone"])
        set_if_present(setup, "additional_offset", unreal.Vector(0.0, 0.0, 0.0))
        set_if_present(setup, "disable_steering", bool(spec["disable_steering"]))
        log(
            "WHEEL_SETUP "
            f"name={spec['name']} bone={spec['bone']} class={class_path} "
            f"radius={spec['radius']} width={spec['width']}"
        )

    movement.set_editor_property("wheel_setups", wheel_setups)
    save_asset(BP_ASSET)
    log("DONE")


main()

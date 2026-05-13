"""Inspect Robobus117th UE4 wheel blueprint wiring.

Run from UE4.26 with CARLA's ``CarlaUE4.uproject``. This is read-only and is
intended to confirm whether the source project wheel blueprints carry the
117th wheel geometry before cooking/deploying runtime assets.
"""

from __future__ import annotations

import os

import unreal  # type: ignore


PREFIX = "ZMF_ROBOBUS_WHEEL_INSPECT "
BP_ASSET = os.environ.get(
    "ROBOBUS_BP_ASSET",
    "/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/BP_Robobus117th",
)
BP_CLASS = os.environ.get("ROBOBUS_BP_CLASS", BP_ASSET + ".BP_Robobus117th_C")
WHEEL_CLASS_PATHS = [
    os.environ.get("ROBOBUS_FL_WHEEL_CLASS", BP_ASSET + "_FLW.BP_Robobus117th_FLW_C"),
    os.environ.get("ROBOBUS_FR_WHEEL_CLASS", BP_ASSET + "_FRW.BP_Robobus117th_FRW_C"),
    os.environ.get("ROBOBUS_RL_WHEEL_CLASS", BP_ASSET + "_RLW.BP_Robobus117th_RLW_C"),
    os.environ.get("ROBOBUS_RR_WHEEL_CLASS", BP_ASSET + "_RRW.BP_Robobus117th_RRW_C"),
]


def log(message: object) -> None:
    unreal.log(PREFIX + str(message))


def object_path(obj: object) -> str:
    if obj is None:
        return "None"
    try:
        return obj.get_path_name()
    except Exception:
        return str(obj)


def load_optional_object(path: str):
    obj = unreal.load_object(None, path)
    log(f"LOAD {path} ok={obj is not None}")
    return obj


def safe_get(obj: object, prop: str):
    try:
        value = obj.get_editor_property(prop)
        log(f"PROP {object_path(obj)}.{prop}={value}")
        return value
    except Exception as exc:
        log(f"PROP_FAIL {object_path(obj)}.{prop}: {exc}")
        return None


def inspect_wheel_class(path: str) -> None:
    cls = load_optional_object(path)
    if not cls:
        return
    cdo = unreal.get_default_object(cls)
    for prop in [
        "shape_radius",
        "shape_width",
        "steer_angle",
        "mass",
        "damping_rate",
        "max_brake_torque",
        "max_handbrake_torque",
        "lat_stiff_max_load",
        "lat_stiff_value",
        "long_stiff_value",
    ]:
        safe_get(cdo, prop)


def main() -> None:
    bp_cls = load_optional_object(BP_CLASS)
    if bp_cls:
        cdo = unreal.get_default_object(bp_cls)
        movement = safe_get(cdo, "vehicle_movement")
        if movement:
            wheel_setups = safe_get(movement, "wheel_setups") or []
            log(f"WHEEL_SETUP_COUNT {len(wheel_setups)}")
            for idx, setup in enumerate(list(wheel_setups)):
                log(f"WHEEL_SETUP_INDEX {idx}")
                for prop in ["wheel_class", "bone_name", "additional_offset", "disable_steering"]:
                    safe_get(setup, prop)
    for path in WHEEL_CLASS_PATHS:
        inspect_wheel_class(path)
    log("DONE")


main()

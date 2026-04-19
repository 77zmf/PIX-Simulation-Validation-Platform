"""Inspect Robobus117th UE4 physics asset geometry.

This is a UE4.26 Python helper. It prints PhysicsAsset body setup geometry so
we can distinguish visual import success from usable CARLA collision bounds.
"""

from __future__ import annotations

import unreal  # type: ignore


PREFIX = "ZMF_ROBOBUS_PHYSICS "
PHYSICS_ASSET = (
    "/Game/Carla/Static/Vehicles/4Wheeled/Robobus117th/"
    "SKM_robobus117th_Object_________1_6_PhysicsAsset"
)
SKELETAL_MESH = (
    "/Game/Carla/Static/Vehicles/4Wheeled/Robobus117th/"
    "SKM_robobus117th.SKM_robobus117th_Object_________1_6"
)
BP_CLASS = (
    "/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/"
    "BP_Robobus117th.BP_Robobus117th_C"
)


def log(message: object) -> None:
    unreal.log(PREFIX + str(message))


def safe_get(obj: object, prop: str):
    try:
        value = obj.get_editor_property(prop)
        log(f"PROP {obj}.{prop}={value}")
        return value
    except Exception as exc:
        log(f"PROP_FAIL {obj}.{prop}: {exc}")
        return None


def log_agg_geom(body: object) -> None:
    agg = safe_get(body, "agg_geom")
    if agg is None:
        return
    for elem_prop in ["box_elems", "sphere_elems", "sphyl_elems", "convex_elems", "tapered_capsule_elems"]:
        elems = safe_get(agg, elem_prop)
        if elems is None:
            continue
        log(f"GEOM_COUNT body={body.get_name()} {elem_prop}={len(elems)}")
        for idx, elem in enumerate(list(elems)[:20]):
            parts = []
            for prop in [
                "center",
                "rotation",
                "x",
                "y",
                "z",
                "radius",
                "length",
                "transform",
                "elem_box",
            ]:
                try:
                    parts.append(f"{prop}={elem.get_editor_property(prop)}")
                except Exception:
                    pass
            log(f"GEOM body={body.get_name()} {elem_prop}[{idx}] {' '.join(parts)}")


def main() -> None:
    phys = unreal.load_asset(PHYSICS_ASSET)
    skm = unreal.load_asset(SKELETAL_MESH)
    bp_cls = unreal.load_object(None, BP_CLASS)
    log(f"PHYSICS_ASSET loaded={phys is not None} class={phys.get_class().get_name() if phys else None}")
    log(f"SKELETAL_MESH loaded={skm is not None} class={skm.get_class().get_name() if skm else None}")
    log(f"BP_CLASS loaded={bp_cls is not None}")

    if skm:
        for prop in ["bounds", "physics_asset", "positive_bounds_extension", "negative_bounds_extension"]:
            safe_get(skm, prop)
    if bp_cls:
        cdo = unreal.get_default_object(bp_cls)
        mesh = cdo.get_editor_property("mesh")
        for prop in ["relative_location", "relative_rotation", "relative_scale3d", "bounds_scale", "physics_asset_override"]:
            safe_get(mesh, prop)

    if not phys:
        raise RuntimeError(f"Could not load physics asset: {PHYSICS_ASSET}")
    bodies = []
    for prop in ["skeletal_body_setups", "constraint_setup", "bounds_bodies"]:
        value = safe_get(phys, prop)
        if prop == "skeletal_body_setups" and value is not None:
            bodies = list(value or [])
    log(f"BODY_COUNT {len(bodies)}")
    for idx, body in enumerate(bodies):
        log(f"BODY_INDEX {idx} name={body.get_name()} class={body.get_class().get_name()}")
        for prop in ["bone_name", "physics_type", "collision_trace_flag", "build_scale3d"]:
            safe_get(body, prop)
        log_agg_geom(body)
    log("DONE")


main()

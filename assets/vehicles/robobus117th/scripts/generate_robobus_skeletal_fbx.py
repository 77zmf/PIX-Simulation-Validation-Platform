"""Generate a CARLA-style skeletal FBX for the Robobus117th mesh.

Run with Blender:

    blender --background --python generate_robobus_skeletal_fbx.py -- \
      --input artifacts/carla_blueprints/robobus117th_source/unreal_import/robobus.fbx \
      --output artifacts/carla_blueprints/robobus117th_source/carla_vehicle_import/SKM_robobus117th.fbx

The generated FBX keeps mesh and wheel-bone coordinates in meters. Import it
into UE4 with uniform scale 1.0 and scene unit conversion enabled.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Vector


BONE_ROOT = "VehicleBase"
WHEEL_BONES = {
    "Wheel_Front_Left": (1.498, -0.923, 0.368),
    "Wheel_Front_Right": (1.498, 0.694, 0.368),
    "Wheel_Rear_Left": (-1.498, -0.923, 0.368),
    "Wheel_Rear_Right": (-1.498, 0.694, 0.368),
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source visual mesh, usually robobus.fbx or robobus.dae.")
    parser.add_argument("--output", required=True, help="Output skeletal FBX path.")
    parser.add_argument(
        "--metadata",
        default="",
        help="Optional metadata JSON path. Defaults to OUTPUT.with_suffix('.json').",
    )
    parser.add_argument(
        "--join-meshes",
        action="store_true",
        help="Join all baked visual pieces before armature binding. Off by default to preserve material slots.",
    )
    parser.add_argument(
        "--mesh-name",
        default="",
        help="Name for the joined mesh object. Defaults to the output file stem.",
    )
    parser.add_argument(
        "--exclude-object-contains",
        action="append",
        default=[],
        help="Drop imported mesh objects whose baked object name contains this text. Can be repeated.",
    )
    parser.add_argument(
        "--exclude-material",
        action="append",
        default=[],
        help="Drop imported mesh objects using a material with this exact name. Can be repeated.",
    )
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_visual(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".dae":
        bpy.ops.wm.collada_import(filepath=str(path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), use_image_search=False)
    elif suffix == ".obj":
        bpy.ops.import_scene.obj(filepath=str(path))
    else:
        raise ValueError(f"Unsupported mesh input: {path}")


def bake_meshes_to_world() -> list[bpy.types.Object]:
    """Bake imported hierarchy transforms into mesh vertices at scene origin."""

    depsgraph = bpy.context.evaluated_depsgraph_get()
    baked: list[bpy.types.Object] = []
    source_meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not source_meshes:
        raise RuntimeError("No mesh objects were imported")

    for index, obj in enumerate(source_meshes):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
        world = obj.matrix_world.copy()
        for vertex in mesh.vertices:
            vertex.co = world @ vertex.co
        mesh.update()
        baked_obj = bpy.data.objects.new(f"robobus_part_{index:03d}_{obj.name[:40]}", mesh)
        bpy.context.collection.objects.link(baked_obj)
        baked.append(baked_obj)

    for obj in list(bpy.context.scene.objects):
        if obj not in baked:
            bpy.data.objects.remove(obj, do_unlink=True)
    return baked


def object_bbox_center(obj: bpy.types.Object) -> Vector:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return Vector(
        (
            sum(corner.x for corner in corners) / len(corners),
            sum(corner.y for corner in corners) / len(corners),
            sum(corner.z for corner in corners) / len(corners),
        )
    )


def object_bbox_extent(obj: bpy.types.Object) -> Vector:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    maximum = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return maximum - minimum


def object_material_names(obj: bpy.types.Object) -> list[str]:
    return [slot.material.name for slot in obj.material_slots if slot.material]


def filter_meshes(
    meshes: list[bpy.types.Object],
    exclude_object_contains: list[str],
    exclude_materials: list[str],
) -> tuple[list[bpy.types.Object], list[dict[str, object]]]:
    kept: list[bpy.types.Object] = []
    removed: list[dict[str, object]] = []
    material_blocklist = set(exclude_materials)

    for obj in meshes:
        materials = object_material_names(obj)
        name_hits = [pattern for pattern in exclude_object_contains if pattern and pattern in obj.name]
        material_hits = [name for name in materials if name in material_blocklist]
        if name_hits or material_hits:
            removed.append(
                {
                    "name": obj.name,
                    "materials": materials,
                    "vertices": len(obj.data.vertices),
                    "polygons": len(obj.data.polygons),
                    "matched_object_contains": name_hits,
                    "matched_materials": material_hits,
                }
            )
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        kept.append(obj)

    return kept, removed


def scene_bbox(meshes: list[bpy.types.Object]) -> dict[str, list[float]]:
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    center = (minimum + maximum) / 2
    return {
        "min": list(minimum),
        "max": list(maximum),
        "extent": list(maximum - minimum),
        "center": list(center),
    }


def create_armature() -> bpy.types.Object:
    armature_data = bpy.data.armatures.new("Armature_robobus117th")
    armature_obj = bpy.data.objects.new("Armature_robobus117th", armature_data)
    bpy.context.collection.objects.link(armature_obj)
    bpy.context.view_layer.objects.active = armature_obj
    armature_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    root = armature_data.edit_bones.new(BONE_ROOT)
    root.head = (0.0, 0.0, 0.0)
    root.tail = (0.0, 0.0, 1.0)

    for name, head in WHEEL_BONES.items():
        bone = armature_data.edit_bones.new(name)
        bone.head = head
        bone.tail = (head[0], head[1], head[2] + 0.35)
        bone.parent = root

    bpy.ops.object.mode_set(mode="OBJECT")
    armature_obj.select_set(False)
    return armature_obj


def nearest_wheel_group(center: Vector, extent: Vector) -> str:
    """Assign obvious wheel-sized parts to wheel bones, otherwise root."""

    nearest_name = ""
    nearest_dist = math.inf
    for name, point in WHEEL_BONES.items():
        target = Vector(point)
        dist = (Vector((center.x, center.y, center.z)) - target).length
        if dist < nearest_dist:
            nearest_name = name
            nearest_dist = dist

    wheel_like_size = 0.12 <= max(extent.x, extent.y, extent.z) <= 0.75
    near_wheel = nearest_dist <= 0.55 and 0.0 <= center.z <= 0.9
    return nearest_name if wheel_like_size and near_wheel else BONE_ROOT


def bind_meshes(meshes: list[bpy.types.Object], armature: bpy.types.Object) -> dict[str, int]:
    assignment_counts = {BONE_ROOT: 0, **{name: 0 for name in WHEEL_BONES}}

    for obj in meshes:
        groups = {name: obj.vertex_groups.new(name=name) for name in assignment_counts}
        center = object_bbox_center(obj)
        extent = object_bbox_extent(obj)
        group_name = nearest_wheel_group(center, extent)
        vertex_indices = [vertex.index for vertex in obj.data.vertices]
        groups[group_name].add(vertex_indices, 1.0, "REPLACE")
        assignment_counts[group_name] += 1

        modifier = obj.modifiers.new("Armature_robobus117th", "ARMATURE")
        modifier.object = armature
        obj.parent = armature

    return assignment_counts


def maybe_join_meshes(meshes: list[bpy.types.Object], mesh_name: str) -> list[bpy.types.Object]:
    if len(meshes) <= 1:
        if mesh_name:
            meshes[0].name = mesh_name
        return meshes
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = mesh_name
    return [joined]


def export_fbx(output: Path, meshes: list[bpy.types.Object], armature: bpy.types.Object) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.fbx(
        filepath=str(output),
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False,
        axis_forward="X",
        axis_up="Z",
        apply_unit_scale=True,
        bake_space_transform=False,
    )


def main() -> int:
    args = parse_args(sys.argv)
    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    metadata = Path(args.metadata).resolve() if args.metadata else output.with_suffix(".json")

    clear_scene()
    import_visual(source)
    meshes = bake_meshes_to_world()
    removed_meshes: list[dict[str, object]] = []
    if args.exclude_object_contains or args.exclude_material:
        meshes, removed_meshes = filter_meshes(meshes, args.exclude_object_contains, args.exclude_material)
        if not meshes:
            raise RuntimeError("All mesh objects were filtered out")
    mesh_name = args.mesh_name or output.stem
    if args.join_meshes:
        meshes = maybe_join_meshes(meshes, mesh_name)
    armature = create_armature()
    assignment_counts = bind_meshes(meshes, armature)
    bbox = scene_bbox(meshes)
    export_fbx(output, meshes, armature)

    payload = {
        "source": str(source),
        "output": str(output),
        "mesh_count": len(meshes),
        "armature": armature.name,
        "bones": [BONE_ROOT, *WHEEL_BONES.keys()],
        "assignment_counts": assignment_counts,
        "bbox_m": bbox,
        "removed_count": len(removed_meshes),
        "removed": removed_meshes,
        "ue4_import": {
            "import_uniform_scale": 1.0,
            "convert_scene": True,
            "convert_scene_unit": True,
            "force_front_x_axis": False,
        },
    }
    metadata.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

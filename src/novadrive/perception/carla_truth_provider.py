from __future__ import annotations

import math
from typing import Any

from novadrive.foundation import DetectedObject, Vector3

from .provider import PerceptionSnapshot


class CarlaTruthProvider:
    source = "carla_truth"

    def __init__(self, world: Any, ego_actor: Any, *, ego_role_name: str = "ego_vehicle") -> None:
        self.world = world
        self.ego_actor = ego_actor
        self.ego_role_name = ego_role_name

    def detect(self, timestamp: float) -> PerceptionSnapshot:
        detections: list[DetectedObject] = []
        for actor in list(self.world.get_actors().filter("vehicle.*")) + list(
            self.world.get_actors().filter("walker.pedestrian.*")
        ):
            if int(actor.id) == int(self.ego_actor.id):
                continue
            if actor.attributes.get("role_name") in {self.ego_role_name, "ego_vehicle", "hero", "autoware_v1"}:
                continue
            detections.append(self._actor_to_detection(actor, timestamp))
        return PerceptionSnapshot(timestamp, self.source, detections=detections)

    def _actor_to_detection(self, actor: Any, timestamp: float) -> DetectedObject:
        transform = actor.get_transform()
        velocity = actor.get_velocity()
        extent = actor.bounding_box.extent
        type_id = str(actor.type_id)
        class_name = "pedestrian" if type_id.startswith("walker.") else "car"
        if ".bus" in type_id:
            class_name = "bus"
        elif ".truck" in type_id:
            class_name = "truck"
        elif ".motorcycle" in type_id:
            class_name = "motorcycle"
        elif ".bicycle" in type_id:
            class_name = "bicycle"
        return DetectedObject(
            timestamp=timestamp,
            frame_id="carla_world",
            source=self.source,
            object_id=str(actor.id),
            class_name=class_name,
            score=1.0,
            center=Vector3(float(transform.location.x), float(transform.location.y), float(transform.location.z)),
            size_lwh=Vector3(float(extent.x) * 2.0, float(extent.y) * 2.0, float(extent.z) * 2.0),
            yaw_rad=math.radians(float(transform.rotation.yaw)),
            velocity=Vector3(float(velocity.x), float(velocity.y), float(velocity.z)),
        )


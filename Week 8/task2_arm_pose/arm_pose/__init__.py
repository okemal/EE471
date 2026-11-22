"""EE471 Week 8 Task 2: Pose-based arm-up classification package."""

from arm_pose.classifier import (
    ArmMetrics,
    ArmPoseClassifier,
    ArmPoseResult,
    classify_pose_landmarks,
)
from arm_pose.config import ArmPoseConfig, InvalidImageError, settings

__all__ = [
    "ArmMetrics",
    "ArmPoseClassifier",
    "ArmPoseConfig",
    "ArmPoseResult",
    "InvalidImageError",
    "classify_pose_landmarks",
    "settings",
]

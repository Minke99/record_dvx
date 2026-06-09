from typing import Optional, Tuple

import numpy as np


def open_dvx_camera():
    try:
        import dv_processing as dv
    except ImportError as exc:
        raise ImportError("DVX recording requires dv_processing. See requirements.txt.") from exc

    capture = dv.io.camera.open()
    if capture is None:
        raise RuntimeError("No DVX camera found. Please make sure the camera is connected.")
    return capture


class CameraControlSource:
    def __init__(self, capture, camera_name, width, height):
        self.capture = capture
        self.camera_name = camera_name
        self.camera_width = width
        self.camera_height = height


def extract_xypt(event_batch) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    if event_batch is None:
        return None, None, None, None

    if hasattr(event_batch, "numpy"):
        data = event_batch.numpy()
        if data is not None and len(data) > 0:
            names = data.dtype.names or ()
            if {"x", "y", "timestamp", "polarity"}.issubset(set(names)):
                x = data["x"].astype(np.int32)
                y = data["y"].astype(np.int32)
                t = data["timestamp"].astype(np.int64)
                p = data["polarity"].astype(np.int8)
                return x, y, t, p

    if all(hasattr(event_batch, key) for key in ("x", "y", "timestamps", "polarities")):
        x = np.asarray(event_batch.x(), dtype=np.int32)
        y = np.asarray(event_batch.y(), dtype=np.int32)
        t = np.asarray(event_batch.timestamps(), dtype=np.int64)
        p = np.asarray(event_batch.polarities(), dtype=np.int8)
        return x, y, t, p

    raise RuntimeError("Unsupported DVX event batch format for the installed dv-processing package.")


def normalize_dataset_polarity(polarity: np.ndarray) -> np.ndarray:
    """Store polarity as 0/1, matching event_flow BaseDataLoader.event_formatting()."""
    polarity = np.asarray(polarity, dtype=np.int8)
    unique = np.unique(polarity)
    if np.all(np.isin(unique, [0, 1])):
        return polarity.astype(np.int8)
    return (polarity > 0).astype(np.int8)


def parse_resolution(value: str, source_height: int, source_width: int) -> tuple[int, int]:
    if value.lower() == "native":
        return source_height, source_width
    parts = value.replace("x", ",").split(",")
    if len(parts) != 2:
        raise ValueError("resolution must be native or HEIGHT,WIDTH, for example 480,640")
    return int(parts[0]), int(parts[1])


def scale_events(
    x: np.ndarray,
    y: np.ndarray,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[np.ndarray, np.ndarray]:
    if source_width == target_width and source_height == target_height:
        return x.astype(np.int32), y.astype(np.int32)
    sx = float(target_width) / float(source_width)
    sy = float(target_height) / float(source_height)
    x_scaled = np.floor(x.astype(np.float32) * sx).astype(np.int32)
    y_scaled = np.floor(y.astype(np.float32) * sy).astype(np.int32)
    x_scaled = np.clip(x_scaled, 0, target_width - 1)
    y_scaled = np.clip(y_scaled, 0, target_height - 1)
    return x_scaled, y_scaled

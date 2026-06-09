import cv2
import numpy as np


def resize_for_display(frame: np.ndarray, target_height: int) -> np.ndarray:
    if target_height <= 0 or frame.shape[0] == target_height:
        return frame
    scale = float(target_height) / float(frame.shape[0])
    target_width = max(1, int(round(frame.shape[1] * scale)))
    interpolation = cv2.INTER_NEAREST if scale >= 1.0 else cv2.INTER_AREA
    return cv2.resize(frame, (target_width, target_height), interpolation=interpolation)

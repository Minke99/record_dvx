#!/usr/bin/env python3
"""Record DVX events as event_flow training-compatible H5 (events/xs,ys,ts,ps)."""

import argparse
from datetime import datetime
import time

import cv2
import h5py
import numpy as np

from lib.camera_controls import apply_camera_controls
from lib.config import load_yaml
from lib.display import resize_for_display
from lib.dvx import (
    CameraControlSource,
    extract_xypt,
    normalize_dataset_polarity,
    open_dvx_camera,
    parse_resolution,
    scale_events,
)
from lib.h5_utils import append_dataset, create_resizable_dataset
from lib.paths import resolve_path


class EventPreview:
    def __init__(self, width: int, height: int, frame_interval_ms: float, display_height_px: int) -> None:
        self.width = int(width)
        self.height = int(height)
        self.frame_interval_s = max(float(frame_interval_ms), 1.0) / 1000.0
        self.display_height_px = int(display_height_px)
        self.last_frame_time = time.time()
        self.count = np.zeros((2, self.height, self.width), dtype=np.float32)

    def add(self, x: np.ndarray, y: np.ndarray, polarity01: np.ndarray) -> None:
        valid = (x >= 0) & (x < self.width) & (y >= 0) & (y < self.height)
        if not np.any(valid):
            return
        x = x[valid]
        y = y[valid]
        p = polarity01[valid]
        np.add.at(self.count[0], (y[p > 0], x[p > 0]), 1.0)
        np.add.at(self.count[1], (y[p <= 0], x[p <= 0]), 1.0)

    def maybe_show(self, total_events: int) -> int:
        now = time.time()
        if now - self.last_frame_time < self.frame_interval_s:
            return -1

        image = self._render(total_events)
        image = resize_for_display(image, self.display_height_px)
        cv2.imshow("DVX training dataset recording", image)
        self.count.fill(0.0)
        self.last_frame_time = now
        return cv2.waitKey(1) & 0xFF

    def _render(self, total_events: int) -> np.ndarray:
        pos = self.count[0]
        neg = self.count[1]
        nonzero = np.concatenate([pos[pos > 0], neg[neg > 0]])
        scale = float(np.percentile(nonzero, 99.0)) if nonzero.size else 1.0
        scale = max(scale, 1.0)
        image = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        image[:, :, 1] = np.clip(pos / scale * 255.0, 0, 255).astype(np.uint8)
        image[:, :, 2] = np.clip(neg / scale * 255.0, 0, 255).astype(np.uint8)
        cv2.putText(
            image,
            "recording dataset events={}  q/Esc=stop".format(total_events),
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return image


def create_output_path(output_dir: str, prefix: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolve_path(output_dir) / "{}_{}.h5".format(prefix, timestamp)


def record(args) -> None:
    config = load_yaml(args.config)
    camera_config = config.get("camera", {}) or {}
    display_config = config.get("display", {}) or {}

    output_path = resolve_path(args.output) if args.output else create_output_path(args.output_dir, args.prefix)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    capture = open_dvx_camera()
    camera_name = capture.getCameraName()
    width, height = capture.getEventResolution()
    width = int(width)
    height = int(height)
    target_height, target_width = parse_resolution(args.resolution, height, width)
    apply_camera_controls(CameraControlSource(capture, camera_name, width, height), camera_config)

    preview = EventPreview(
        width=target_width,
        height=target_height,
        frame_interval_ms=float(display_config.get("frame_interval_ms", 33)),
        display_height_px=int(display_config.get("display_height_px", 720)),
    )
    cv2.namedWindow("DVX training dataset recording", cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        "DVX training dataset recording",
        int(target_width * preview.display_height_px / target_height),
        preview.display_height_px,
    )

    print("camera = {}, resolution = {}x{}".format(camera_name, width, height))
    print("dataset resolution = {}x{} (H x W = [{}, {}])".format(target_width, target_height, target_height, target_width))
    print("writing training-compatible H5 to:", output_path)
    print("press q or Esc in the preview window to stop")

    total_events = 0
    total_packets = 0
    t0 = None
    last_t = None
    start_wall = time.time()

    with h5py.File(output_path, "w") as handle:
        events_group = handle.create_group("events")
        xs_ds = create_resizable_dataset(events_group, "xs", np.int32)
        ys_ds = create_resizable_dataset(events_group, "ys", np.int32)
        ts_ds = create_resizable_dataset(events_group, "ts", np.int64)
        ps_ds = create_resizable_dataset(events_group, "ps", np.int8)

        handle.attrs["camera_name"] = camera_name
        handle.attrs["sensor_resolution"] = np.asarray([height, width], dtype=np.int32)
        handle.attrs["source_resolution_width"] = width
        handle.attrs["source_resolution_height"] = height
        handle.attrs["resolution_width"] = target_width
        handle.attrs["resolution_height"] = target_height
        handle.attrs["loader_resolution"] = np.asarray([target_height, target_width], dtype=np.int32)
        handle.attrs["time_unit"] = "us"
        handle.attrs["format"] = "event_flow_training_events_v1"

        try:
            while capture.isRunning():
                event_batch = capture.getNextEventBatch()
                if event_batch is None:
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break
                    time.sleep(args.idle_sleep_s)
                    continue

                x, y, t, p = extract_xypt(event_batch)
                if x is None or len(x) == 0:
                    continue

                p = normalize_dataset_polarity(p)
                x, y = scale_events(x, y, width, height, target_width, target_height)
                if t0 is None:
                    t0 = int(t[0])
                last_t = int(t[-1])

                append_dataset(xs_ds, x)
                append_dataset(ys_ds, y)
                append_dataset(ts_ds, t)
                append_dataset(ps_ds, p)

                total_events += len(x)
                total_packets += 1
                preview.add(x, y, p)

                key = preview.maybe_show(total_events)
                if key in (ord("q"), 27):
                    break

                if args.max_events > 0 and total_events >= args.max_events:
                    break
                if args.status_every > 0 and total_packets % args.status_every == 0:
                    elapsed = max(time.time() - start_wall, 1e-6)
                    print("packets={}, events={}, rate={:.0f} ev/s".format(total_packets, total_events, total_events / elapsed))
        except KeyboardInterrupt:
            print("\nrecording stopped by Ctrl+C")
        finally:
            cv2.destroyAllWindows()

        if t0 is None:
            t0 = 0
        if last_t is None:
            last_t = t0
        handle.attrs["t0"] = int(t0)
        handle.attrs["duration"] = int(last_t - t0)
        handle.attrs["num_events"] = int(total_events)
        handle.attrs["num_packets"] = int(total_packets)
        handle.attrs["duration_wall_s"] = float(time.time() - start_wall)

    print("saved {}, events={}".format(output_path, total_events))


def parse_args():
    parser = argparse.ArgumentParser(description="Record DVXplorer events as an event_flow training-compatible H5.")
    parser.add_argument("--config", default="config/camera.yaml", help="Camera/display config path relative to record_dvx/.")
    parser.add_argument("--output-dir", default="datasets/dvx_training_240x320", help="Output folder relative to record_dvx/.")
    parser.add_argument("--prefix", default="dvx_train", help="Output filename prefix when --output is not set.")
    parser.add_argument("--output", default=None, help="Exact output H5 path relative to record_dvx/.")
    parser.add_argument("--resolution", default="240,320", help="Saved dataset H,W resolution, e.g. 240,320, native, or 128,128.")
    parser.add_argument("--max-events", type=int, default=0, help="Optional maximum event count; <=0 records until q/Esc.")
    parser.add_argument("--idle-sleep-s", type=float, default=0.001, help="Sleep when camera has no new events.")
    parser.add_argument("--status-every", type=int, default=50, help="Print status every N packets; <=0 disables status.")
    return parser.parse_args()


if __name__ == "__main__":
    record(parse_args())

#!/usr/bin/env python3
"""Record raw DVX events to HDF5 (deploy replay format: events/x,y,t,p)."""

import argparse
import time

import h5py
import numpy as np

from lib.camera_controls import apply_camera_controls
from lib.config import load_yaml
from lib.dvx import CameraControlSource, extract_xypt, open_dvx_camera
from lib.h5_utils import append_dataset, create_resizable_dataset
from lib.paths import resolve_path


def record(args):
    config = load_yaml(args.config) if args.config else {}
    input_config = config.get("input", {}) or {}
    camera_config = config.get("camera", {}) or {}

    output = args.output or input_config.get("recording", "recordings/dvx_raw.h5")
    output_path = resolve_path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    capture = open_dvx_camera()
    camera_name = capture.getCameraName()
    width, height = capture.getEventResolution()
    width = int(width)
    height = int(height)
    if camera_config:
        apply_camera_controls(CameraControlSource(capture, camera_name, width, height), camera_config)
    print("camera = {}, resolution = {}x{}".format(camera_name, width, height))
    print("recording raw events to:", output_path)
    print("stop with Ctrl+C")

    start = time.time()
    total_events = 0
    total_packets = 0
    with h5py.File(output_path, "w") as handle:
        events_group = handle.create_group("events")
        x_ds = create_resizable_dataset(events_group, "x", np.int32)
        y_ds = create_resizable_dataset(events_group, "y", np.int32)
        t_ds = create_resizable_dataset(events_group, "t", np.int64)
        p_ds = create_resizable_dataset(events_group, "p", np.int8)

        handle.attrs["camera_name"] = camera_name
        handle.attrs["resolution_width"] = width
        handle.attrs["resolution_height"] = height
        handle.attrs["time_unit"] = "us"
        handle.attrs["format"] = "raw_dvx_events_v1"

        try:
            while capture.isRunning():
                if args.duration > 0 and time.time() - start >= args.duration:
                    break
                if args.max_events > 0 and total_events >= args.max_events:
                    break

                event_batch = capture.getNextEventBatch()
                if event_batch is None:
                    time.sleep(args.idle_sleep_s)
                    continue

                x, y, t, p = extract_xypt(event_batch)
                if x is None or len(x) == 0:
                    continue

                if args.max_events > 0:
                    remaining = args.max_events - total_events
                    if remaining <= 0:
                        break
                    x = x[:remaining]
                    y = y[:remaining]
                    t = t[:remaining]
                    p = p[:remaining]

                append_dataset(x_ds, x)
                append_dataset(y_ds, y)
                append_dataset(t_ds, t)
                append_dataset(p_ds, p)
                total_events += len(x)
                total_packets += 1

                if total_packets % args.status_every == 0:
                    print("packets={}, events={}".format(total_packets, total_events))
        except KeyboardInterrupt:
            print("\nrecording stopped by user")

        handle.attrs["num_events"] = int(total_events)
        handle.attrs["num_packets"] = int(total_packets)
        handle.attrs["duration_wall_s"] = float(time.time() - start)

    print("saved {}, events={}".format(output_path, total_events))


def parse_args():
    parser = argparse.ArgumentParser(description="Record raw DVX events to HDF5 for offline replay.")
    parser.add_argument("--config", default="config/camera.yaml", help="Camera config path relative to record_dvx/.")
    parser.add_argument("--output", default=None, help="H5 output path relative to record_dvx/.")
    parser.add_argument("--duration", type=float, default=0.0, help="Recording duration in seconds; <=0 runs until Ctrl+C.")
    parser.add_argument("--max-events", type=int, default=0, help="Maximum events to record; <=0 means unlimited.")
    parser.add_argument("--idle-sleep-s", type=float, default=0.001, help="Sleep when camera has no new events.")
    parser.add_argument("--status-every", type=int, default=50, help="Print progress every N event packets.")
    return parser.parse_args()


if __name__ == "__main__":
    record(parse_args())

#!/usr/bin/env python3
"""Record raw DVX events to HDF5 (deploy replay format: events/x,y,t,p)."""

import argparse
import datetime
import json
import time

import h5py
import numpy as np

from lib.camera_controls import apply_camera_controls
from lib.config import load_yaml
from lib.dvx import CameraControlSource, extract_xypt, open_dvx_camera
from lib.h5_utils import append_dataset, create_resizable_dataset
from lib.paths import resolve_path
from lib.quit_key import QuitKey


def build_noise_filter(width, height, camera_config):
    """Build an optional software noise filter from camera_config.

    Config keys (under `camera:` in the yaml):
      noise_bg_activity_ms: float  -> BackgroundActivityNoiseFilter window (ms).
                                       <=0 or absent disables filtering.
    Returns the filter object or None.
    """
    bg_ms = 0.0
    if camera_config:
        bg_ms = float(camera_config.get("noise_bg_activity_ms", 0.0) or 0.0)
    if bg_ms <= 0:
        return None
    try:
        import dv_processing as dv
        nf = dv.noise.BackgroundActivityNoiseFilter(
            (int(width), int(height)),
            backgroundActivityDuration=datetime.timedelta(milliseconds=bg_ms),
        )
        print("noise filter: BackgroundActivityNoiseFilter, window={} ms".format(bg_ms))
        return nf
    except Exception as exc:  # noqa: BLE001
        print("WARNING: failed to build noise filter ({}); recording unfiltered.".format(exc))
        return None


def apply_noise_filter(noise_filter, event_batch):
    """Run the noise filter; on any failure, fall back to the raw batch."""
    if noise_filter is None or event_batch is None:
        return event_batch
    try:
        noise_filter.accept(event_batch)
        return noise_filter.generateEvents()
    except Exception as exc:  # noqa: BLE001
        print("WARNING: noise filter failed ({}); using raw batch for this packet.".format(exc))
        return event_batch


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

    noise_filter = build_noise_filter(width, height, camera_config)

    print("recording raw events to:", output_path)
    quit_key = QuitKey()
    print("stop by pressing 'q'" + ("" if quit_key.enabled else " (stdin not a TTY; use SIGTERM/SIGINT)"))

    start = time.time()
    total_events = 0
    total_packets = 0
    sync_written = False
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
                if quit_key.pressed():
                    print("\nrecording stopped by 'q'")
                    break
                if args.duration > 0 and time.time() - start >= args.duration:
                    break
                if args.max_events > 0 and total_events >= args.max_events:
                    break

                event_batch = capture.getNextEventBatch()
                if event_batch is None:
                    time.sleep(args.idle_sleep_s)
                    continue

                recv_wall_us = int(time.time() * 1e6)
                event_batch = apply_noise_filter(noise_filter, event_batch)
                x, y, t, p = extract_xypt(event_batch)
                if x is None or len(x) == 0:
                    continue

                if not sync_written and args.sync_out:
                    sync_path = resolve_path(args.sync_out)
                    sync_path.parent.mkdir(parents=True, exist_ok=True)
                    sync_payload = {
                        "camera_first_us": int(t[0]),
                        "wall_first_us": int(recv_wall_us),
                    }
                    tmp_path = sync_path.with_suffix(sync_path.suffix + ".tmp")
                    tmp_path.write_text(json.dumps(sync_payload))
                    tmp_path.replace(sync_path)
                    sync_written = True
                    print("sync file:", sync_path)

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
        finally:
            quit_key.restore()

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
    parser.add_argument("--sync-out", default=None,
                        help="Optional JSON file path (relative to record_dvx/) to write {camera_first_us, wall_first_us} on first event batch. Used by record_mocap.py to align to camera time.")
    return parser.parse_args()


if __name__ == "__main__":
    record(parse_args())
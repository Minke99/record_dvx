#!/usr/bin/env python3
"""Resize event_flow training H5 event coordinates to a new resolution."""

import argparse
from pathlib import Path

import h5py
import numpy as np

from lib.dvx import parse_resolution, scale_events
from lib.h5_utils import append_dataset, create_resizable_dataset
from lib.paths import resolve_path


def infer_source_resolution(handle) -> tuple[int, int]:
    width = handle.attrs.get("source_resolution_width", handle.attrs.get("resolution_width"))
    height = handle.attrs.get("source_resolution_height", handle.attrs.get("resolution_height"))
    if width is None or height is None:
        width = int(np.max(handle["events/xs"][:])) + 1
        height = int(np.max(handle["events/ys"][:])) + 1
    return int(height), int(width)


def copy_attrs(src, dst, source_height: int, source_width: int, target_height: int, target_width: int) -> None:
    for key, value in src.attrs.items():
        dst.attrs[key] = value
    dst.attrs["source_resolution_height"] = int(source_height)
    dst.attrs["source_resolution_width"] = int(source_width)
    dst.attrs["resolution_height"] = int(target_height)
    dst.attrs["resolution_width"] = int(target_width)
    dst.attrs["loader_resolution"] = np.asarray([target_height, target_width], dtype=np.int32)
    dst.attrs["format"] = "event_flow_training_events_v1"


def resize_file(input_path: Path, output_path: Path, target_height: int, target_width: int, chunk_events: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(input_path, "r") as src, h5py.File(output_path, "w") as dst:
        if "events" not in src:
            raise KeyError("Missing events group: {}".format(input_path))
        events = src["events"]
        for key in ("xs", "ys", "ts", "ps"):
            if key not in events:
                raise KeyError("Missing events/{} in {}".format(key, input_path))

        source_height, source_width = infer_source_resolution(src)
        dst_events = dst.create_group("events")
        xs_ds = create_resizable_dataset(dst_events, "xs", np.int32)
        ys_ds = create_resizable_dataset(dst_events, "ys", np.int32)
        ts_ds = create_resizable_dataset(dst_events, "ts", events["ts"].dtype)
        ps_ds = create_resizable_dataset(dst_events, "ps", events["ps"].dtype)

        total = len(events["xs"])
        for start in range(0, total, chunk_events):
            end = min(start + chunk_events, total)
            x = np.asarray(events["xs"][start:end], dtype=np.int32)
            y = np.asarray(events["ys"][start:end], dtype=np.int32)
            x_scaled, y_scaled = scale_events(x, y, source_width, source_height, target_width, target_height)
            append_dataset(xs_ds, x_scaled)
            append_dataset(ys_ds, y_scaled)
            append_dataset(ts_ds, events["ts"][start:end])
            append_dataset(ps_ds, events["ps"][start:end])

        copy_attrs(src, dst, source_height, source_width, target_height, target_width)
        dst.attrs["num_events"] = int(total)

    print("wrote {} -> {} at [{}, {}]".format(input_path, output_path, target_height, target_width))


def parse_args():
    parser = argparse.ArgumentParser(description="Resize event_flow training H5 event coordinates.")
    parser.add_argument("--input", required=True, help="Input H5 file or folder, relative to record_dvx/.")
    parser.add_argument("--output-dir", required=True, help="Output folder relative to record_dvx/.")
    parser.add_argument("--resolution", default="240,320", help="Target H,W resolution.")
    parser.add_argument("--chunk-events", type=int, default=500000, help="Events processed per chunk.")
    return parser.parse_args()


def main(args) -> None:
    input_path = resolve_path(args.input)
    output_dir = resolve_path(args.output_dir)
    target_height, target_width = parse_resolution(args.resolution, 0, 0)

    if input_path.is_dir():
        files = sorted(input_path.glob("*.h5"))
    else:
        files = [input_path]
    if not files:
        raise FileNotFoundError("No H5 files found at {}".format(input_path))

    for file_path in files:
        resize_file(file_path, output_dir / file_path.name, target_height, target_width, args.chunk_events)


if __name__ == "__main__":
    main(parse_args())

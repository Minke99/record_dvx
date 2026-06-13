#!/usr/bin/env python3
"""Launch DVX event recording and Motive mocap recording side-by-side in one session."""

import argparse
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.paths import resolve_path
from lib.quit_key import QuitKey


def main():
    parser = argparse.ArgumentParser(
        description="Record DVX events + Motive mocap to a session directory."
    )
    parser.add_argument("--session-name", default=None,
                        help="Subdir under recordings/ (default: timestamp).")
    parser.add_argument("--session-root", default="recordings",
                        help="Parent dir for session folders (default recordings/).")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="Recording duration in seconds; <=0 runs until Ctrl+C.")
    parser.add_argument("--config", default="config/camera.yaml",
                        help="Camera config for record_raw.py.")
    parser.add_argument("--multicast", default="239.255.42.99")
    parser.add_argument("--port", type=int, default=1511)
    parser.add_argument("--bind-ip", default="0.0.0.0")
    args = parser.parse_args()

    session_name = args.session_name or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir = resolve_path(Path(args.session_root) / session_name)
    session_dir.mkdir(parents=True, exist_ok=True)
    events_h5 = session_dir / "events.h5"
    mocap_h5 = session_dir / "mocap.h5"
    sync_json = session_dir / "sync.json"

    python = sys.executable
    record_raw = str(_REPO_ROOT / "record_raw.py")
    record_mocap = str(_REPO_ROOT / "record_mocap.py")

    raw_cmd = [python, record_raw,
               "--config", args.config,
               "--output", str(events_h5),
               "--sync-out", str(sync_json)]
    mocap_cmd = [python, record_mocap,
                 "--multicast", args.multicast,
                 "--port", str(args.port),
                 "--bind-ip", args.bind_ip,
                 "--output", str(mocap_h5),
                 "--sync-from", str(sync_json)]
    if args.duration > 0:
        raw_cmd += ["--duration", str(args.duration)]
        mocap_cmd += ["--duration", str(args.duration)]

    print("session dir :", session_dir)
    print("events ->", events_h5)
    print("mocap  ->", mocap_h5)
    print("sync   ->", sync_json)
    print("starting children…")
    session_start = time.time()
    # start both as close to each other in wall time as possible.
    # children get stdin=DEVNULL so only the parent owns the TTY for the 'q' key.
    p_raw = subprocess.Popen(raw_cmd, cwd=str(_REPO_ROOT), stdin=subprocess.DEVNULL)
    p_mocap = subprocess.Popen(mocap_cmd, cwd=str(_REPO_ROOT), stdin=subprocess.DEVNULL)
    print("session_start_wall_s = {:.6f}".format(session_start))
    print("PIDs: raw={} mocap={}".format(p_raw.pid, p_mocap.pid))

    stopping = {"flag": False}

    def stop_children(signum=None, frame=None):
        if stopping["flag"]:
            return
        stopping["flag"] = True
        for p in (p_raw, p_mocap):
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass

    signal.signal(signal.SIGINT, stop_children)
    signal.signal(signal.SIGTERM, stop_children)

    quit_key = QuitKey()
    print("stop by pressing 'q'" + ("" if quit_key.enabled else " (no TTY; use SIGTERM)"))

    try:
        while True:
            if p_raw.poll() is not None and p_mocap.poll() is not None:
                break
            if quit_key.pressed():
                print("\n'q' pressed; stopping children…")
                stop_children()
                break
            time.sleep(0.1)
    finally:
        quit_key.restore()

    rc_raw = p_raw.wait()
    rc_mocap = p_mocap.wait()
    print("exit codes: raw={}, mocap={}".format(rc_raw, rc_mocap))
    print("session saved to:", session_dir)


if __name__ == "__main__":
    main()

# record_dvx

Standalone DVXplorer recording tools. Run everything from this folder:

```bash
cd record_dvx
pip install -r requirements.txt
```

## Scripts

| Script | Output | Use case |
|--------|--------|----------|
| `record_raw.py` | `recordings/*.h5` with `events/x,y,t,p` | Offline replay / deploy |
| `record_training.py` | `datasets/*.h5` with `events/xs,ys,ts,ps` | `event_flow2bio` training / fine-tune |
| `resize_training.py` | Rescaled copy of training H5 | Change resolution without re-recording |

## Quick start

### Record raw events (5 seconds)

```bash
python record_raw.py --duration 5
```

Output: `recordings/dvx_raw.h5`

### Record training dataset (with preview, press q/Esc to stop)

```bash
python record_training.py
```

Output: `datasets/dvx_training_240x320/dvx_train_YYYYMMDD_HHMMSS.h5`

Default saved resolution is 240×320 (H×W). Use `--resolution native` to keep camera resolution.

### Resize an existing training H5

```bash
python resize_training.py \
  --input datasets/dvx_training_240x320 \
  --output-dir datasets/dvx_training_128x128 \
  --resolution 128,128
```

## Config

Edit `config/camera.yaml` to tune contrast threshold and other camera controls.

## H5 formats

**Raw replay** (`record_raw.py`):

```
events/x, y, t, p
```

**Training** (`record_training.py`):

```
events/xs, ys, ts, ps
attrs: t0, duration, resolution_height, resolution_width
```

Training files can be pointed at directly from `event_flow2bio` configs, e.g.:

```yaml
data:
  path: ../record_dvx/datasets/dvx_training_240x320/
```

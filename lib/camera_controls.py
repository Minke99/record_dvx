from typing import Dict


def apply_camera_controls(source, camera_config: Dict) -> None:
    capture = getattr(source, "capture", None)
    if capture is None:
        return

    print("camera = {}, resolution = {}x{}".format(source.camera_name, source.camera_width, source.camera_height))
    if bool(camera_config.get("print_available_controls", False)):
        _print_camera_control_methods(capture)

    threshold_on = camera_config.get("contrast_threshold_on")
    threshold_off = camera_config.get("contrast_threshold_off")
    if threshold_on is not None:
        _call_camera_method(capture, "setContrastThresholdOn", int(threshold_on))
    if threshold_off is not None:
        _call_camera_method(capture, "setContrastThresholdOff", int(threshold_off))

    crop_area = camera_config.get("crop_area")
    if crop_area is not None:
        _call_camera_method(capture, "setCropArea", tuple(int(value) for value in crop_area))

    global_hold = camera_config.get("global_hold")
    if global_hold is not None:
        _call_camera_method(capture, "setGlobalHold", bool(global_hold))

    global_reset = camera_config.get("global_reset")
    if global_reset is not None:
        _call_camera_method(capture, "setGlobalReset", bool(global_reset))

    readout_fps = camera_config.get("readout_fps")
    if readout_fps is not None:
        _set_readout_fps(capture, readout_fps)


def _call_camera_method(capture, method_name: str, value) -> None:
    method = getattr(capture, method_name, None)
    if method is None:
        print("warning: camera object has no {}({}); leave it unset".format(method_name, value))
        return
    try:
        method(value)
    except TypeError:
        if not isinstance(value, tuple):
            raise
        method(list(value))
    print("{}({})".format(method_name, value))


def _set_readout_fps(capture, readout_fps) -> None:
    enum_value = readout_fps
    if isinstance(readout_fps, str):
        enum_name = readout_fps.strip()
        enum_container = getattr(type(capture), "ReadoutFPS", None) or getattr(capture, "ReadoutFPS", None)
        if enum_container is None or not hasattr(enum_container, enum_name):
            print("warning: cannot resolve ReadoutFPS {}; leave it unset".format(enum_name))
            return
        enum_value = getattr(enum_container, enum_name)
    _call_camera_method(capture, "setReadoutFPS", enum_value)


def _print_camera_control_methods(capture) -> None:
    keywords = ("Bias", "bias", "Threshold", "threshold", "Readout", "Crop", "Hold", "Reset")
    methods = [name for name in dir(capture) if any(keyword in name for keyword in keywords)]
    if methods:
        print("camera control methods:", ", ".join(sorted(methods)))

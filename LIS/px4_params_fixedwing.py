"""固定翼扩展：在 ``px4_params`` 能力基础上增加 MAVSDK ``fixedwing_metrics``（指示空速等）。"""
import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Union

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.offboard import Attitude, OffboardError


@dataclass
class Vec3:
    """三维向量；用于 IMU 时为 FRD（前-右-下），用于速度时为 NED 时见字段名。"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class BatteryTelemetry:
    voltage_v: float = 0.0
    remaining_percent: float = 0.0


@dataclass
class ImuTelemetry:
    accel: Vec3 = field(default_factory=Vec3)
    gyro: Vec3 = field(default_factory=Vec3)
    mag: Vec3 = field(default_factory=Vec3)


@dataclass
class AttitudeDeg:
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class PositionTelemetry:
    latitude_deg: float = 0.0
    longitude_deg: float = 0.0
    absolute_altitude_m: float = 0.0
    relative_altitude_m: float = 0.0


@dataclass
class VelocityNed:
    north_m_s: float = 0.0
    east_m_s: float = 0.0
    down_m_s: float = 0.0


@dataclass
class GpsTelemetry:
    num_satellites: int = 0
    fix_type: Union[int, str] = 0


@dataclass
class FixedwingTelemetry:
    """来自 ``telemetry.fixedwing_metrics()``（IAS、油门、爬升率、地速、航向、高度等）。"""

    airspeed_m_s: float = 0.0
    throttle_pct: float = 0.0
    climb_rate_m_s: float = 0.0
    groundspeed_m_s: float = 0.0
    heading_deg: float = 0.0
    absolute_altitude_m: float = 0.0


@dataclass
class TelemetryView:
    """从 `get_state_snapshot()` 的字典解析出的结构化视图，便于主循环里少写字、按角色访问。"""

    battery: BatteryTelemetry = field(default_factory=BatteryTelemetry)
    imu: ImuTelemetry = field(default_factory=ImuTelemetry)
    attitude_deg: AttitudeDeg = field(default_factory=AttitudeDeg)
    position: PositionTelemetry = field(default_factory=PositionTelemetry)
    velocity_ned: VelocityNed = field(default_factory=VelocityNed)
    gps: GpsTelemetry = field(default_factory=GpsTelemetry)
    fixedwing: FixedwingTelemetry = field(default_factory=FixedwingTelemetry)
    in_air: int = 0
    armed: int = 0
    flight_mode: str = ""


def parse_telemetry_state(state: dict) -> TelemetryView:
    """
    把 TelemetryLogger.get_state_snapshot() 返回的 dict 转成 TelemetryView。
    未订阅的组对应字段保持默认值（0）。
    """
    g = state.get

    fix_raw = g("gps_fix_type", 0)
    if isinstance(fix_raw, (int, str)):
        fix_out: Union[int, str] = fix_raw
    else:
        try:
            fix_out = int(fix_raw)
        except Exception:
            fix_out = str(fix_raw)

    return TelemetryView(
        battery=BatteryTelemetry(
            voltage_v=float(g("battery_voltage_v", 0.0) or 0.0),
            remaining_percent=float(g("battery_remaining_percent", 0.0) or 0.0),
        ),
        imu=ImuTelemetry(
            accel=Vec3(
                float(g("imu_accel_x", 0.0) or 0.0),
                float(g("imu_accel_y", 0.0) or 0.0),
                float(g("imu_accel_z", 0.0) or 0.0),
            ),
            gyro=Vec3(
                float(g("imu_gyro_x", 0.0) or 0.0),
                float(g("imu_gyro_y", 0.0) or 0.0),
                float(g("imu_gyro_z", 0.0) or 0.0),
            ),
            mag=Vec3(
                float(g("imu_mag_x", 0.0) or 0.0),
                float(g("imu_mag_y", 0.0) or 0.0),
                float(g("imu_mag_z", 0.0) or 0.0),
            ),
        ),
        attitude_deg=AttitudeDeg(
            roll=float(g("roll_deg", 0.0) or 0.0),
            pitch=float(g("pitch_deg", 0.0) or 0.0),
            yaw=float(g("yaw_deg", 0.0) or 0.0),
        ),
        position=PositionTelemetry(
            latitude_deg=float(g("latitude_deg", 0.0) or 0.0),
            longitude_deg=float(g("longitude_deg", 0.0) or 0.0),
            absolute_altitude_m=float(g("absolute_altitude_m", 0.0) or 0.0),
            relative_altitude_m=float(g("relative_altitude_m", 0.0) or 0.0),
        ),
        velocity_ned=VelocityNed(
            north_m_s=float(g("velocity_north_m_s", 0.0) or 0.0),
            east_m_s=float(g("velocity_east_m_s", 0.0) or 0.0),
            down_m_s=float(g("velocity_down_m_s", 0.0) or 0.0),
        ),
        gps=GpsTelemetry(
            num_satellites=int(g("gps_num_satellites", 0) or 0),
            fix_type=fix_out,
        ),
        fixedwing=FixedwingTelemetry(
            airspeed_m_s=float(g("airspeed_m_s", 0.0) or 0.0),
            throttle_pct=float(g("fw_throttle_pct", 0.0) or 0.0),
            climb_rate_m_s=float(g("fw_climb_rate_m_s", 0.0) or 0.0),
            groundspeed_m_s=float(g("fw_groundspeed_m_s", 0.0) or 0.0),
            heading_deg=float(g("fw_heading_deg", 0.0) or 0.0),
            absolute_altitude_m=float(g("fw_abs_altitude_m", 0.0) or 0.0),
        ),
        in_air=int(g("in_air", 0) or 0),
        armed=int(g("armed", 0) or 0),
        flight_mode=str(g("flight_mode", "") or ""),
    )


def telemetry_view_to_state_dict(p: TelemetryView) -> dict:
    """与 TelemetryLogger 内存中的字段名一致（不含 timestamp），用于按列名取值。"""
    fix = p.gps.fix_type
    return {
        "imu_accel_x": p.imu.accel.x,
        "imu_accel_y": p.imu.accel.y,
        "imu_accel_z": p.imu.accel.z,
        "imu_gyro_x": p.imu.gyro.x,
        "imu_gyro_y": p.imu.gyro.y,
        "imu_gyro_z": p.imu.gyro.z,
        "imu_mag_x": p.imu.mag.x,
        "imu_mag_y": p.imu.mag.y,
        "imu_mag_z": p.imu.mag.z,
        "roll_deg": p.attitude_deg.roll,
        "pitch_deg": p.attitude_deg.pitch,
        "yaw_deg": p.attitude_deg.yaw,
        "latitude_deg": p.position.latitude_deg,
        "longitude_deg": p.position.longitude_deg,
        "absolute_altitude_m": p.position.absolute_altitude_m,
        "relative_altitude_m": p.position.relative_altitude_m,
        "velocity_north_m_s": p.velocity_ned.north_m_s,
        "velocity_east_m_s": p.velocity_ned.east_m_s,
        "velocity_down_m_s": p.velocity_ned.down_m_s,
        "gps_num_satellites": p.gps.num_satellites,
        "gps_fix_type": fix,
        "battery_voltage_v": p.battery.voltage_v,
        "battery_remaining_percent": p.battery.remaining_percent,
        "airspeed_m_s": p.fixedwing.airspeed_m_s,
        "fw_throttle_pct": p.fixedwing.throttle_pct,
        "fw_climb_rate_m_s": p.fixedwing.climb_rate_m_s,
        "fw_groundspeed_m_s": p.fixedwing.groundspeed_m_s,
        "fw_heading_deg": p.fixedwing.heading_deg,
        "fw_abs_altitude_m": p.fixedwing.absolute_altitude_m,
        "in_air": p.in_air,
        "armed": p.armed,
        "flight_mode": p.flight_mode,
    }


def telemetry_view_to_ordered_values(px4_param, field_names):
    """按 ``field_names`` 顺序取值；``field_names`` 应来自 ``telemetry_field_names_for_groups``。"""
    d = telemetry_view_to_state_dict(px4_param)
    return tuple(d[name] for name in field_names)


def safe_get(obj, *attrs, default=0.0):
    cur = obj
    for attr in attrs:
        if cur is None:
            return default
        cur = getattr(cur, attr, None)
    return default if cur is None else cur


class TelemetryLogger:
    """只负责遥测采集与内存状态（供 loop 读取）；固定翼组订阅 ``fixedwing_metrics``。"""

    FIELD_GROUPS = {
        "imu": [
            "imu_accel_x",
            "imu_accel_y",
            "imu_accel_z",
            "imu_gyro_x",
            "imu_gyro_y",
            "imu_gyro_z",
            "imu_mag_x",
            "imu_mag_y",
            "imu_mag_z",
        ],
        "attitude": ["roll_deg", "pitch_deg", "yaw_deg"],
        "position": ["latitude_deg", "longitude_deg", "absolute_altitude_m", "relative_altitude_m"],
        "velocity": ["velocity_north_m_s", "velocity_east_m_s", "velocity_down_m_s"],
        "gps": ["gps_num_satellites", "gps_fix_type"],
        "fixedwing": [
            "airspeed_m_s",
            "fw_throttle_pct",
            "fw_climb_rate_m_s",
            "fw_groundspeed_m_s",
            "fw_heading_deg",
            "fw_abs_altitude_m",
        ],
        "battery": ["battery_voltage_v", "battery_remaining_percent"],
        "in_air": ["in_air"],
        "armed": ["armed"],
        "flight_mode": ["flight_mode"],
    }

    def __init__(
        self,
        drone: System,
        enabled_groups=None,
        imu_rate_hz=50.0,
        battery_rate_hz=1.0,
        attitude_rate_hz=20.0,
        position_rate_hz=10.0,
        velocity_rate_hz=20.0,
        gps_rate_hz=5.0,
        fixedwing_rate_hz=10.0,
    ):
        self.drone = drone
        if enabled_groups is None:
            enabled_groups = tuple(self.FIELD_GROUPS.keys())
        self.enabled_groups = set(enabled_groups)
        # MAVSDK: one set_rate per stream type. IMU message includes accel + gyro + mag.
        self.imu_rate_hz = imu_rate_hz
        self.battery_rate_hz = battery_rate_hz
        self.attitude_rate_hz = attitude_rate_hz
        self.position_rate_hz = position_rate_hz
        self.velocity_rate_hz = velocity_rate_hz
        self.gps_rate_hz = gps_rate_hz
        self.fixedwing_rate_hz = fixedwing_rate_hz
        unknown = self.enabled_groups - set(self.FIELD_GROUPS.keys())
        if unknown:
            raise ValueError(f"Unknown telemetry groups: {sorted(unknown)}")
        self.state_lock = asyncio.Lock()
        self.state = self._make_default_state(self.enabled_groups)
        self._tasks = []

    @staticmethod
    def _make_default_state(enabled_groups):
        defaults = {"timestamp": 0.0}
        for group in enabled_groups:
            for key in TelemetryLogger.FIELD_GROUPS[group]:
                if key in {"gps_num_satellites", "gps_fix_type", "in_air", "armed"}:
                    defaults[key] = 0
                elif key == "flight_mode":
                    defaults[key] = ""
                else:
                    defaults[key] = 0.0
        return defaults

    async def _update_state(self, updates: dict):
        updates = {k: v for k, v in updates.items() if k in self.state}
        if not updates:
            return
        async with self.state_lock:
            self.state.update(updates)

    async def get_state_snapshot(self):
        async with self.state_lock:
            return deepcopy(self.state)

    async def get_telemetry_view(self) -> TelemetryView:
        """与 get_state_snapshot() 相同数据，但打包为 TelemetryView，主循环里少写 .get()。"""
        return parse_telemetry_state(await self.get_state_snapshot())

    async def _collect_imu(self):
        try:
            async for imu in self.drone.telemetry.imu():
                await self._update_state(
                    {
                        "imu_accel_x": safe_get(imu, "acceleration_frd", "forward_m_s2", default=0.0),
                        "imu_accel_y": safe_get(imu, "acceleration_frd", "right_m_s2", default=0.0),
                        "imu_accel_z": safe_get(imu, "acceleration_frd", "down_m_s2", default=0.0),
                        "imu_gyro_x": safe_get(imu, "angular_velocity_frd", "forward_rad_s", default=0.0),
                        "imu_gyro_y": safe_get(imu, "angular_velocity_frd", "right_rad_s", default=0.0),
                        "imu_gyro_z": safe_get(imu, "angular_velocity_frd", "down_rad_s", default=0.0),
                        "imu_mag_x": safe_get(imu, "magnetic_field_frd", "forward_gauss", default=0.0),
                        "imu_mag_y": safe_get(imu, "magnetic_field_frd", "right_gauss", default=0.0),
                        "imu_mag_z": safe_get(imu, "magnetic_field_frd", "down_gauss", default=0.0),
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_imu stopped: {e}")

    async def _collect_attitude(self):
        try:
            async for att in self.drone.telemetry.attitude_euler():
                await self._update_state(
                    {
                        "roll_deg": safe_get(att, "roll_deg", default=0.0),
                        "pitch_deg": safe_get(att, "pitch_deg", default=0.0),
                        "yaw_deg": safe_get(att, "yaw_deg", default=0.0),
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_attitude stopped: {e}")

    async def _collect_position(self):
        try:
            async for pos in self.drone.telemetry.position():
                await self._update_state(
                    {
                        "latitude_deg": safe_get(pos, "latitude_deg", default=0.0),
                        "longitude_deg": safe_get(pos, "longitude_deg", default=0.0),
                        "absolute_altitude_m": safe_get(pos, "absolute_altitude_m", default=0.0),
                        "relative_altitude_m": safe_get(pos, "relative_altitude_m", default=0.0),
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_position stopped: {e}")

    async def _collect_velocity(self):
        try:
            async for vel in self.drone.telemetry.velocity_ned():
                await self._update_state(
                    {
                        "velocity_north_m_s": safe_get(vel, "north_m_s", default=0.0),
                        "velocity_east_m_s": safe_get(vel, "east_m_s", default=0.0),
                        "velocity_down_m_s": safe_get(vel, "down_m_s", default=0.0),
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_velocity stopped: {e}")

    async def _collect_gps(self):
        try:
            async for gps in self.drone.telemetry.gps_info():
                fix_type = safe_get(gps, "fix_type", default=0)
                try:
                    fix_type_out = int(fix_type)
                except Exception:
                    fix_type_out = str(fix_type)
                await self._update_state(
                    {
                        "gps_num_satellites": safe_get(gps, "num_satellites", default=0),
                        "gps_fix_type": fix_type_out,
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_gps stopped: {e}")

    async def _collect_fixedwing(self):
        try:
            async for m in self.drone.telemetry.fixedwing_metrics():
                await self._update_state(
                    {
                        "airspeed_m_s": safe_get(m, "airspeed_m_s", default=0.0),
                        "fw_throttle_pct": safe_get(m, "throttle_percentage", default=0.0),
                        "fw_climb_rate_m_s": safe_get(m, "climb_rate_m_s", default=0.0),
                        "fw_groundspeed_m_s": safe_get(m, "groundspeed_m_s", default=0.0),
                        "fw_heading_deg": safe_get(m, "heading_deg", default=0.0),
                        "fw_abs_altitude_m": safe_get(m, "absolute_altitude_m", default=0.0),
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_fixedwing stopped: {e}")

    async def _collect_battery(self):
        try:
            async for batt in self.drone.telemetry.battery():
                remaining = safe_get(batt, "remaining_percent", default=0.0)
                try:
                    rp = float(remaining)
                except (TypeError, ValueError):
                    rp = 0.0
                if rp != rp:
                    rp = 0.0
                await self._update_state(
                    {
                        "battery_voltage_v": safe_get(batt, "voltage_v", default=0.0),
                        "battery_remaining_percent": rp,
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_battery stopped: {e}")

    async def _collect_in_air(self):
        try:
            async for in_air in self.drone.telemetry.in_air():
                await self._update_state({"in_air": 1 if in_air else 0})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_in_air stopped: {e}")

    async def _collect_armed(self):
        try:
            async for armed in self.drone.telemetry.armed():
                await self._update_state({"armed": 1 if armed else 0})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_armed stopped: {e}")

    async def _collect_flight_mode(self):
        try:
            async for mode in self.drone.telemetry.flight_mode():
                await self._update_state({"flight_mode": str(mode)})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WARN] collect_flight_mode stopped: {e}")

    async def _request_telemetry_rates(self):
        """Without set_rate_* many PX4 links never push imu()/battery(); state stays at defaults."""
        telem = self.drone.telemetry
        if "imu" in self.enabled_groups:
            try:
                await telem.set_rate_imu(self.imu_rate_hz)
            except Exception as e:
                print(f"[WARN] set_rate_imu({self.imu_rate_hz} Hz): {e}")
        if "battery" in self.enabled_groups:
            try:
                await telem.set_rate_battery(self.battery_rate_hz)
            except Exception as e:
                print(f"[WARN] set_rate_battery({self.battery_rate_hz} Hz): {e}")
        if "attitude" in self.enabled_groups:
            try:
                await telem.set_rate_attitude_euler(self.attitude_rate_hz)
            except Exception as e:
                print(f"[WARN] set_rate_attitude_euler({self.attitude_rate_hz} Hz): {e}")
        if "position" in self.enabled_groups:
            try:
                await telem.set_rate_position(self.position_rate_hz)
            except Exception as e:
                print(f"[WARN] set_rate_position({self.position_rate_hz} Hz): {e}")
        if "velocity" in self.enabled_groups:
            try:
                await telem.set_rate_velocity_ned(self.velocity_rate_hz)
            except Exception as e:
                print(f"[WARN] set_rate_velocity_ned({self.velocity_rate_hz} Hz): {e}")
        if "gps" in self.enabled_groups:
            try:
                await telem.set_rate_gps_info(self.gps_rate_hz)
            except Exception as e:
                print(f"[WARN] set_rate_gps_info({self.gps_rate_hz} Hz): {e}")
        if "fixedwing" in self.enabled_groups:
            try:
                await telem.set_rate_fixedwing_metrics(self.fixedwing_rate_hz)
            except Exception as e:
                print(f"[WARN] set_rate_fixedwing_metrics({self.fixedwing_rate_hz} Hz): {e}")
        if "in_air" in self.enabled_groups:
            try:
                await telem.set_rate_in_air(5.0)
            except Exception as e:
                print(f"[WARN] set_rate_in_air: {e}")

    async def start(self):
        await self._request_telemetry_rates()
        self._tasks = []
        if "imu" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_imu()))
        if "attitude" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_attitude()))
        if "position" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_position()))
        if "velocity" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_velocity()))
        if "gps" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_gps()))
        if "fixedwing" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_fixedwing()))
        if "battery" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_battery()))
        if "in_air" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_in_air()))
        if "armed" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_armed()))
        if "flight_mode" in self.enabled_groups:
            self._tasks.append(asyncio.create_task(self._collect_flight_mode()))

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


_GROUP_ORDER_FOR_LOG = (
    "imu",
    "attitude",
    "position",
    "velocity",
    "gps",
    "fixedwing",
    "battery",
    "in_air",
    "armed",
    "flight_mode",
)


def telemetry_field_names_for_groups(enabled_groups):
    """
    与 ``TelemetryLogger(..., enabled_groups=...)`` 使用同一组名时，得到对应的 parquet 列名顺序
    （不含 ``timestamp`` / ``thrust`` / ``phase``）。请与 ``DataSaver`` 里展开顺序保持一致。
    """
    eg = set(enabled_groups)
    unknown = eg - set(TelemetryLogger.FIELD_GROUPS.keys())
    if unknown:
        raise ValueError(f"Unknown telemetry groups: {sorted(unknown)}")
    names = []
    for g in _GROUP_ORDER_FOR_LOG:
        if g in eg:
            names.extend(TelemetryLogger.FIELD_GROUPS[g])
    return tuple(names)


TELEMETRY_PARQUET_COLUMN_NAMES = telemetry_field_names_for_groups(_GROUP_ORDER_FOR_LOG)


class DroneController:
    """只负责控制动作：连接、mode、offboard、arm/disarm、姿态发送。"""

    def __init__(self, drone: System):
        self.drone = drone

    async def connect(self, system_address: str):
        await self.drone.connect(system_address=system_address)
        print("Waiting for drone to connect...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                print("-- Connected")
                return

    async def print_status_text(self):
        try:
            async for status in self.drone.telemetry.status_text():
                print(f"[PX4] {status.type}: {status.text}")
        except asyncio.CancelledError:
            pass

    async def prime_attitude_setpoint(self, seconds=1.5, dt=0.05):
        print(f"-- Priming attitude setpoint for {seconds:.1f}s")
        n = int(seconds / dt)
        for _ in range(n):
            await self.drone.offboard.set_attitude(Attitude(0.0, 0.0, 0.0, 0.0))
            await asyncio.sleep(dt)

    async def send_attitude_for(self, roll, pitch, yaw, thrust, seconds, dt=0.05):
        n = int(seconds / dt)
        for _ in range(n):
            await self.drone.offboard.set_attitude(Attitude(roll, pitch, yaw, thrust))
            await asyncio.sleep(dt)

    async def start_offboard(self):
        print("-- Starting offboard")
        try:
            await self.drone.offboard.start()
            print("-- Offboard started")
            return True
        except OffboardError as e:
            print(f"Offboard start failed: {e._result.result}")
            return False

    async def arm(self):
        print("-- Arming")
        await self.drone.action.arm()
        print("-- Armed")

    async def disarm(self):
        print("-- Disarming")
        await self.drone.action.disarm()
        print("-- Disarmed")

    async def set_mode_hold(self):
        print("-- Switching mode to HOLD")
        await self.drone.action.hold()

    async def wait_until_landed(self, timeout_s=5.0):
        print("-- Waiting for landed detection")
        try:
            async with asyncio.timeout(timeout_s):
                async for in_air in self.drone.telemetry.in_air():
                    print(f"   in_air={in_air}")
                    if not in_air:
                        print("-- Landed detected")
                        return True
        except TimeoutError:
            pass
        print("-- Landed not confirmed within timeout")
        return False

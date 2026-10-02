from __future__ import annotations

import math
import queue
import threading
import time
from dataclasses import dataclass

import serial


@dataclass(frozen=True)
class PedestalTelemetry:
    position_m: float | None
    sensor_voltage_v: float | None
    target_position_m: float
    goal_active: bool
    task_state: str
    unlocked: bool
    received_time_sec: float


@dataclass(frozen=True)
class PedestalState:
    position_m: float | None
    sensor_voltage_v: float | None
    target_position_m: float
    goal_active: bool
    task_state: str
    unlocked: bool
    fault_reason: str


class PedestalSerial:
    """Threaded adapter for the ESP32 pedestal position protocol."""

    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        heartbeat_period_sec: float = 0.1,
    ) -> None:
        self._serial = serial.Serial(
            port,
            baud_rate,
            timeout=0.1,
        )

        self._write_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._telemetry_lock = threading.Lock()
        self._event_lock = threading.Lock()

        self._response_queue: queue.Queue[str] = queue.Queue()

        self._goal_active = threading.Event()
        self._shutdown = threading.Event()

        self._heartbeat_period_sec = heartbeat_period_sec

        self._latest_telemetry: PedestalTelemetry | None = None
        self._latest_state: PedestalState | None = None
        self._last_event: str | None = None

        # Opening the ESP32 serial port can reset it.
        time.sleep(2.0)
        self._serial.reset_input_buffer()

        self._reader_thread = threading.Thread(
            target=self._reader_worker,
            daemon=True,
        )

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_worker,
            daemon=True,
        )

        self._reader_thread.start()
        self._heartbeat_thread.start()

    @property
    def latest_telemetry(self) -> PedestalTelemetry | None:
        with self._telemetry_lock:
            return self._latest_telemetry

    @property
    def latest_state(self) -> PedestalState | None:
        return self._latest_state

    @property
    def last_event(self) -> str | None:
        with self._event_lock:
            return self._last_event

    def set_target(self, position_m: float) -> bool:
        if not math.isfinite(position_m):
            return False

        success = self._send_command(
            command=f"P {position_m:.4f}",
            expected_prefix="ACK TARGET ",
        )

        if success:
            # Start heartbeats immediately instead of waiting for the next
            # telemetry frame. The firmware watchdog is 500 ms.
            self._goal_active.set()

        return success

    def stop(self) -> bool:
        # Stop heartbeats immediately. If serial communication is lost, this
        # intentionally lets the ESP32 watchdog become the final backstop.
        self._goal_active.clear()

        return self._send_command(
            command="S",
            expected_line="ACK STOP",
        )

    def reset_fault(self) -> bool:
        success = self._send_command(
            command="R",
            expected_line="ACK RESET",
        )

        if success:
            self._goal_active.clear()

        return success

    def query_state(self) -> PedestalState | None:
        with self._command_lock:
            self._clear_response_queue()
            self._send("Q")

            deadline = time.monotonic() + 1.0

            while True:
                remaining_sec = deadline - time.monotonic()

                if remaining_sec <= 0.0:
                    return None

                try:
                    line = self._response_queue.get(
                        timeout=remaining_sec,
                    )
                except queue.Empty:
                    return None

                if line.startswith("STATE "):
                    state = self._parse_state(line)

                    if state is not None:
                        self._latest_state = state

                    return state

                if line.startswith("ERR "):
                    return None

    def close(self) -> None:
        self._goal_active.clear()

        try:
            if self._serial.is_open and not self._shutdown.is_set():
                self.stop()
        finally:
            self._shutdown.set()

            self._reader_thread.join(timeout=1.0)
            self._heartbeat_thread.join(timeout=1.0)

            if self._serial.is_open:
                self._serial.close()

    def _send(self, command: str) -> None:
        wire_command = f"{command}\n"

        with self._write_lock:
            self._serial.write(wire_command.encode("ascii"))
            self._serial.flush()

    def _send_command(
        self,
        command: str,
        expected_line: str | None = None,
        expected_prefix: str | None = None,
        timeout_sec: float = 1.0,
    ) -> bool:
        with self._command_lock:
            self._clear_response_queue()
            self._send(command)

            deadline = time.monotonic() + timeout_sec

            while True:
                remaining_sec = deadline - time.monotonic()

                if remaining_sec <= 0.0:
                    return False

                try:
                    line = self._response_queue.get(
                        timeout=remaining_sec,
                    )
                except queue.Empty:
                    return False

                if expected_line is not None and line == expected_line:
                    return True

                if expected_prefix is not None and line.startswith(
                    expected_prefix
                ):
                    return True

                if line.startswith("ERR "):
                    return False

    def _reader_worker(self) -> None:
        while not self._shutdown.is_set():
            try:
                line = (
                    self._serial.readline()
                    .decode("ascii", errors="replace")
                    .strip()
                )
            except serial.SerialException:
                self._goal_active.clear()
                return

            if not line:
                continue

            if line.startswith("TEL "):
                self._handle_telemetry(line)
                continue

            if line.startswith("STATE "):
                state = self._parse_state(line)

                if state is not None:
                    self._latest_state = state

                    if not state.goal_active:
                        self._goal_active.clear()

                self._response_queue.put(line)
                continue

            if line.startswith("EVENT "):
                self._handle_event(line)
                continue

            if line.startswith("INFO "):
                continue

            if line.startswith("ACK ") or line.startswith("ERR "):
                self._response_queue.put(line)

    def _handle_telemetry(self, line: str) -> None:
        fields = line.split()

        if not fields or fields[0] != "TEL":
            return

        values = self._parse_key_value_fields(fields[1:])

        required = {
            "POSITION_M",
            "SENSOR_V",
            "TARGET_M",
            "GOAL_ACTIVE",
            "STATE",
            "UNLOCKED",
        }

        if not required.issubset(values):
            return

        position_m = self._parse_optional_float(values["POSITION_M"])
        sensor_voltage_v = self._parse_optional_float(values["SENSOR_V"])

        try:
            target_position_m = float(values["TARGET_M"])
            goal_active = self._parse_bool(values["GOAL_ACTIVE"])
            unlocked = self._parse_bool(values["UNLOCKED"])
        except ValueError:
            return

        telemetry = PedestalTelemetry(
            position_m=position_m,
            sensor_voltage_v=sensor_voltage_v,
            target_position_m=target_position_m,
            goal_active=goal_active,
            task_state=values["STATE"],
            unlocked=unlocked,
            received_time_sec=time.monotonic(),
        )

        with self._telemetry_lock:
            self._latest_telemetry = telemetry

        if goal_active:
            self._goal_active.set()
        else:
            self._goal_active.clear()

    def _handle_event(self, line: str) -> None:
        event = line.removeprefix("EVENT ").strip()

        with self._event_lock:
            self._last_event = event

        if event == "GOAL_REACHED" or event.startswith("FAULT "):
            self._goal_active.clear()

    def _parse_state(self, line: str) -> PedestalState | None:
        fields = line.split()

        if len(fields) < 3 or fields[0] != "STATE":
            return None

        task_state = fields[1]
        values = self._parse_key_value_fields(fields[2:])

        required = {
            "POSITION_M",
            "SENSOR_V",
            "TARGET_M",
            "GOAL_ACTIVE",
            "UNLOCKED",
            "FAULT",
        }

        if not required.issubset(values):
            return None

        try:
            target_position_m = float(values["TARGET_M"])
            goal_active = self._parse_bool(values["GOAL_ACTIVE"])
            unlocked = self._parse_bool(values["UNLOCKED"])
        except ValueError:
            return None

        return PedestalState(
            position_m=self._parse_optional_float(values["POSITION_M"]),
            sensor_voltage_v=self._parse_optional_float(values["SENSOR_V"]),
            target_position_m=target_position_m,
            goal_active=goal_active,
            task_state=task_state,
            unlocked=unlocked,
            fault_reason=values["FAULT"],
        )

    @staticmethod
    def _parse_key_value_fields(fields: list[str]) -> dict[str, str]:
        if len(fields) % 2 != 0:
            return {}

        return dict(zip(fields[0::2], fields[1::2]))

    @staticmethod
    def _parse_optional_float(value: str) -> float | None:
        if value == "INVALID":
            return None

        try:
            result = float(value)
        except ValueError:
            return None

        return result if math.isfinite(result) else None

    @staticmethod
    def _parse_optional_int(value: str) -> int | None:
        if value == "INVALID":
            return None

        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_bool(value: str) -> bool:
        if value == "1":
            return True

        if value == "0":
            return False

        raise ValueError(f"invalid boolean value: {value}")

    def _clear_response_queue(self) -> None:
        while True:
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                return

    def _heartbeat_worker(self) -> None:
        while not self._shutdown.wait(self._heartbeat_period_sec):
            if not self._goal_active.is_set():
                continue

            try:
                self._send("H")
            except serial.SerialException:
                self._goal_active.clear()
                return

from __future__ import annotations

import threading
import time

import serial


class PedestalSerial:
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

        self._serial_lock = threading.Lock()
        self._motion_active = threading.Event()
        self._shutdown = threading.Event()

        self._heartbeat_period_sec = heartbeat_period_sec

        time.sleep(2.0)
        self._serial.reset_input_buffer()

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_worker,
            daemon=True,
        )

        self._heartbeat_thread.start()

    def unlock(self) -> bool:
        return self._send_command("l", "OK UNLOCK")

    def up(self) -> bool:
        success = self._send_command("u", "OK UP")

        if success:
            self._motion_active.set()

        return success

    def down(self) -> bool:
        success = self._send_command("d", "OK DOWN")

        if success:
            self._motion_active.set()

        return success

    def stop(self) -> bool:
        success = self._send_command("s", "OK STOP")

        if success:
            self._motion_active.clear()

        return success

    def close(self) -> None:
        self._motion_active.clear()

        try:
            self.stop()
        finally:
            self._shutdown.set()
            self._heartbeat_thread.join()
            self._serial.close()

    def _send(self, command: str) -> None:
        with self._serial_lock:
            self._serial.write(command.encode())
            self._serial.flush()

    def _send_command(
        self,
        command: str,
        expected_response: str,
    ) -> bool:
        self._send(command)

        while True:
            line = self._serial.readline().decode().strip()

            if not line:
                continue

            print(line)

            if line == expected_response:
                return True

            if line.startswith("ERR "):
                return False

            if command == "l" and line == "ALREADY UNLOCKED":
                return True

    def _heartbeat_worker(self) -> None:
        while not self._shutdown.is_set():
            if self._motion_active.is_set():
                self._send("h")

            time.sleep(self._heartbeat_period_sec)

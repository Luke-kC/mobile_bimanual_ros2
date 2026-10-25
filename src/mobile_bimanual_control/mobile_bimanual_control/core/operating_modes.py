from enum import StrEnum


class OperatingMode(StrEnum):
    NO_MOTION = "no_motion"
    BASE_MOTION = "base_motion"
    HEIGHT_ADJUST = "height_adjust"
    MANIPULATION = "manipulation"


class Subsystem(StrEnum):
    TRACER = "tracer"
    PEDESTAL = "pedestal"
    OPENARM = "openarm"


_AUTHORIZED = {
    OperatingMode.NO_MOTION: None,
    OperatingMode.BASE_MOTION: Subsystem.TRACER,
    OperatingMode.HEIGHT_ADJUST: Subsystem.PEDESTAL,
    OperatingMode.MANIPULATION: Subsystem.OPENARM,
}


class OperatingModeController:
    """Explicit operating mode and command permissions; no command queue."""

    def __init__(self) -> None:
        self._mode = OperatingMode.NO_MOTION

    @property
    def mode(self) -> OperatingMode:
        return self._mode

    def set_mode(self, mode: OperatingMode) -> None:
        self._mode = mode

    def is_command_allowed(self, subsystem: Subsystem) -> bool:
        return _AUTHORIZED[self._mode] is subsystem

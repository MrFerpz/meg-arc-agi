"""Trigger outputs: MEG TTL (parallel port / serial box), EyeLink messages, LSL.

Every output gets the same code at the same moment through MultiTrigger.
Each pulse goes high for `pulse_s`, then back to 0, with at least `min_gap_s`
of 0 between pulses so that mne.find_events can split them.
"""

import logging
import time
from typing import Any, Callable, Optional, Protocol

log = logging.getLogger(__name__)


def _busy_wait(seconds: float) -> None:
    # time.sleep() can overshoot by >1 ms on Windows, so spin instead.
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


class TriggerOutput(Protocol):
    def set(self, code: int) -> None: ...
    def close(self) -> None: ...


class NullOutput:
    """Does nothing. Use on a laptop with no trigger hardware."""

    def set(self, code: int) -> None:
        pass

    def close(self) -> None:
        pass


class ParallelPortOutput:
    """TTL via a parallel port (pins 2-9 = bits 0-7), through PsychoPy."""

    def __init__(self, address: int | str = 0x378) -> None:
        from psychopy import parallel

        self._port = parallel.ParallelPort(address=address)
        self._port.setData(0)

    def set(self, code: int) -> None:
        self._port.setData(code)

    def close(self) -> None:
        self._port.setData(0)


class SerialOutput:
    """USB/serial trigger box that takes one byte per state change.

    Fits Brain Products TriggerBox and similar boxes that copy the byte to
    their 8-bit TTL output. Check the box manual: some boxes pulse on their own
    and do not need the 0 byte.
    """

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        import serial

        self._ser = serial.Serial(port, baudrate=baudrate, timeout=0)
        self._ser.write(bytes([0]))

    def set(self, code: int) -> None:
        self._ser.write(bytes([code]))

    def close(self) -> None:
        self._ser.write(bytes([0]))
        self._ser.close()


class TriggerSender:
    """Sends one code to all outputs, logs it, and keeps pulses apart."""

    def __init__(
        self,
        ttl_outputs: list[TriggerOutput],
        pulse_s: float = 0.010,
        min_gap_s: float = 0.005,
        clock: Callable[[], float] = time.perf_counter,
        on_send: Optional[Callable[[int, float, str], None]] = None,
        eyelink: Any = None,
        lsl_outlet: Any = None,
    ) -> None:
        self.ttl_outputs = ttl_outputs
        self.pulse_s = pulse_s
        self.min_gap_s = min_gap_s
        self.clock = clock
        self.on_send = on_send
        self.eyelink = eyelink  # pylink.EyeLink, or None
        self.lsl_outlet = lsl_outlet  # pylsl.StreamOutlet, or None
        self._last_low = -1e9

    def pulse(self, code: int, label: str = "") -> float:
        """Send `code` now. Blocks for about pulse_s. Returns the onset time."""
        if not 1 <= code <= 255:
            raise ValueError(f"trigger code {code} out of range 1-255")

        wait = self._last_low + self.min_gap_s - self.clock()
        if wait > 0:
            _busy_wait(wait)

        for out in self.ttl_outputs:
            out.set(code)
        onset = self.clock()

        # Messages go out while the TTL line is high. They do not delay onset.
        if self.eyelink is not None:
            self.eyelink.sendMessage(f"TRIGGER {code} {label}".strip())
        if self.lsl_outlet is not None:
            self.lsl_outlet.push_sample([code])

        _busy_wait(self.pulse_s - (self.clock() - onset))
        for out in self.ttl_outputs:
            out.set(0)
        self._last_low = self.clock()

        if self.on_send is not None:
            self.on_send(code, onset, label)
        return onset

    def close(self) -> None:
        for out in self.ttl_outputs:
            out.close()


def make_ttl_output(kind: str, address: str = "") -> TriggerOutput:
    if kind == "none":
        return NullOutput()
    if kind == "parallel":
        return ParallelPortOutput(int(address, 0) if address else 0x378)
    if kind == "serial":
        if not address:
            raise ValueError("serial trigger needs --trigger-address, e.g. COM3")
        return SerialOutput(address)
    raise ValueError(f"unknown trigger kind {kind!r}")

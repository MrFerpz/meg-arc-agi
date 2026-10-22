"""Tab-separated event log. One row per trigger or player input."""

import csv
import time
from pathlib import Path
from typing import Any, Callable

COLUMNS = [
    "t",  # seconds, same clock as the trigger onset (the clock passed in)
    "event",
    "code",
    "game_id",
    "game_number",
    "action",
    "x",
    "y",
    "frame_index",
    "n_frames",
    "state",
    "levels_completed",
    "input_t",  # keyboard/mouse timestamp from PsychoPy, if any
    "flip_t",  # screen flip time from PsychoPy, if any
    "note",
]


class EventLog:
    def __init__(self, path: Path, clock: Callable[[], float] = time.perf_counter) -> None:
        self.clock = clock
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(path, "w", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._f, fieldnames=COLUMNS, delimiter="\t")
        self._w.writeheader()
        self.context: dict[str, Any] = {}
        # Anchor so the log can be lined up with wall-clock files.
        self.write("clock_anchor", note=f"unix={time.time():.6f}")  # same moment as t

    def write(self, event: str, t: float | None = None, **fields: Any) -> None:
        row = {**self.context, **fields, "event": event}
        row["t"] = f"{self.clock() if t is None else t:.6f}"
        self._w.writerow({k: row.get(k, "") for k in COLUMNS})
        self._f.flush()

    def close(self) -> None:
        self._f.close()

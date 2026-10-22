"""PsychoPy task: a participant plays ARC-AGI-3 games while triggers go to MEG.

Run:
    uv run --extra psychopy python -m meg_arc.task --participant P01 \
        --games ls20 ft09 vc33 --trigger none --windowed

Timing rule: every trigger that marks something on screen is sent from
win.callOnFlip(), so it goes out right after the frame is shown. A photodiode
patch turns white on those same frames so that the delay of the projector can
be measured and removed.
"""

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any, Optional

from arcengine import GameAction, GameState
from PIL import Image

from . import codes
from .display import (BORDER_RGB, border_px, check_grid_px, grid_overlay, level_text,
                      photodiode_pos, pos_to_cell)
from .eventlog import EventLog
from .game import GameRunner, Response, frame_to_rgb, make_arcade
from .triggers import TriggerSender, make_ttl_output

# Same keys as the ARC-AGI-3 web player (docs.arcprize.org/actions).
# Button boxes in the MEG room usually type keys too: map them here.
DEFAULT_KEYS: dict[str, GameAction] = {
    "w": GameAction.ACTION1, "up": GameAction.ACTION1,
    "s": GameAction.ACTION2, "down": GameAction.ACTION2,
    "a": GameAction.ACTION3, "left": GameAction.ACTION3,
    "d": GameAction.ACTION4, "right": GameAction.ACTION4,
    "space": GameAction.ACTION5, "f": GameAction.ACTION5,
    "z": GameAction.ACTION7,
    "r": GameAction.RESET,
}
QUIT_KEY = "escape"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--participant", required=True)
    p.add_argument("--games", nargs="+", default=["ls20", "ft09", "vc33"])
    p.add_argument("--minutes-per-game", type=float, default=10.0)
    p.add_argument("--rest-seconds", type=float, default=30.0)
    p.add_argument("--environments-dir", default="environment_files")
    p.add_argument("--out-dir", default="data")
    p.add_argument("--online", action="store_true", help="allow network game download")
    # Trigger hardware
    p.add_argument("--trigger", choices=["none", "parallel", "serial"], default="none")
    p.add_argument("--trigger-address", default="", help="e.g. 0x378, 0xD010 or COM3")
    p.add_argument("--pulse-ms", type=float, default=10.0)
    p.add_argument("--gap-ms", type=float, default=5.0)
    p.add_argument("--eyelink", default="", help="EyeLink host IP, e.g. 100.1.1.1")
    p.add_argument("--lsl", action="store_true", help="also send codes as an LSL stream")
    # Display
    p.add_argument("--windowed", action="store_true")
    p.add_argument("--screen", type=int, default=0)
    p.add_argument("--grid-px", type=int, default=640, help="grid size on screen, a multiple of 64")
    p.add_argument("--photodiode", choices=["off", "tl", "tr", "bl", "br"], default="bl")
    p.add_argument("--photodiode-px", type=int, default=60)
    p.add_argument("--no-mouse", action="store_true", help="disable ACTION6 clicks")
    return p.parse_args(argv)


def connect_eyelink(address: str, edf_name: str) -> Any:
    """Messages-only EyeLink link. Calibrate with the facility's routine first.

    UNTESTED here (no tracker). Based on the SR Research pylink API.
    """
    import pylink

    el = pylink.EyeLink(address)
    el.openDataFile(edf_name)  # 8.3 name, e.g. P01.EDF
    el.sendCommand("add_file_preamble_text 'ARC-AGI-3 MEG'")
    el.startRecording(1, 1, 1, 1)
    return el


def make_lsl_outlet() -> Any:
    from pylsl import StreamInfo, StreamOutlet

    info = StreamInfo("ARC_MEG_Markers", "Markers", 1, 0, "int32", "arc-meg-task")
    return StreamOutlet(info)


class Task:
    def __init__(self, args: argparse.Namespace) -> None:
        from psychopy import core, event, visual
        from psychopy.hardware import keyboard

        self.args = args
        self.core = core
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.out = Path(args.out_dir) / f"{args.participant}_{stamp}"
        self.log = EventLog(self.out / "events.tsv", clock=core.getTime)

        self.eyelink = connect_eyelink(args.eyelink, f"{args.participant[:8]}.EDF") if args.eyelink else None
        self.trig = TriggerSender(
            [make_ttl_output(args.trigger, args.trigger_address)],
            pulse_s=args.pulse_ms / 1000,
            min_gap_s=args.gap_ms / 1000,
            clock=core.getTime,
            on_send=lambda code, t, label: self.log.write("trigger", t=t, code=code, note=label),
            eyelink=self.eyelink,
            lsl_outlet=make_lsl_outlet() if args.lsl else None,
        )

        self.win = visual.Window(
            fullscr=not args.windowed, size=(1024, 768), screen=args.screen, units="pix",
            color=(-1, -1, -1), allowGUI=args.windowed, waitBlanking=True,
        )
        rate = self.win.getActualFrameRate(nIdentical=20, nMaxFrames=120) or 60.0
        self.frame_s = 1.0 / rate
        if args.pulse_ms / 1000 + args.gap_ms / 1000 > self.frame_s:
            print(f"WARNING: pulse+gap longer than one frame ({self.frame_s*1000:.1f} ms)", file=sys.stderr)
        self.log.write("display", note=f"refresh_hz={rate:.3f} size={self.win.size.tolist()}")

        gp = check_grid_px(args.grid_px)
        bw = border_px(gp)
        self.border = visual.Rect(self.win, width=gp + 2 * bw, height=gp + 2 * bw, fillColor=BORDER_RGB,
                                  colorSpace="rgb255", lineColor=None)
        self.grid = visual.ImageStim(self.win, size=(gp, gp), interpolate=False)
        # Grid lines as on the web player: one RGBA texture, drawn over each frame.
        self.lines = visual.ImageStim(self.win, image=Image.fromarray(grid_overlay(gp), "RGBA"),
                                      size=(gp, gp), interpolate=False)
        self.diode = None
        if args.photodiode != "off":
            w, h = self.win.size
            self.diode = visual.Rect(
                self.win, width=args.photodiode_px, height=args.photodiode_px,
                pos=photodiode_pos(args.photodiode, w, h, args.photodiode_px),
                fillColor="black", lineColor=None,
            )
        self.text = visual.TextStim(self.win, height=28, wrapWidth=1200, color="white")
        # Level counter above the top-right corner of the border. It changes only on a new level.
        self.hud = visual.TextStim(self.win, height=20, color="grey", anchorHoriz="right",
                                   alignText="right", pos=(gp / 2 + bw, gp / 2 + bw + 18))
        self.kb = keyboard.Keyboard()
        self.mouse = None if args.no_mouse else event.Mouse(win=self.win, visible=True)
        self._mouse_was_down = False
        self.keys = DEFAULT_KEYS
        self.arcade = make_arcade(args.environments_dir, str(self.out / "arc_recordings"), offline=not args.online)

    # -- drawing -------------------------------------------------------------

    def draw_frame(self, frame: Any, diode_on: bool, hud: str = "") -> None:
        self.border.draw()
        # Pass uint8 via PIL: exact colours. (A float -1..1 array came out wrong:
        # measured 0, 51, 102 -> 0, 0, 0 on screen.)
        self.grid.image = Image.fromarray(frame_to_rgb(frame))
        self.grid.draw()
        self.lines.draw()
        if hud:
            self.hud.text = hud
            self.hud.draw()
        if self.diode is not None:
            self.diode.fillColor = "white" if diode_on else "black"
            self.diode.draw()

    def flip_with_codes(self, codes_to_send: list[int], label: str, **fields: Any) -> None:
        def on_flip() -> None:
            flip_t = self.core.getTime()
            for code in codes_to_send:
                self.trig.pulse(code, label)
            self.log.write("flip", t=flip_t, flip_t=f"{flip_t:.6f}", note=label, **fields)

        if codes_to_send:
            self.win.callOnFlip(on_flip)
        self.win.flip()

    def message(self, text: str, code: Optional[int] = None, wait_keys: Optional[list[str]] = None,
                seconds: Optional[float] = None) -> None:
        self.text.text = text
        self.text.draw()
        if self.diode is not None:
            self.diode.fillColor = "white" if code else "black"
            self.diode.draw()
        self.flip_with_codes([code] if code else [], f"message:{text[:20]}")
        if wait_keys:
            self.kb.clearEvents()
            keys = self.kb.waitKeys(keyList=wait_keys + [QUIT_KEY])
            if keys and keys[0].name == QUIT_KEY:
                raise KeyboardInterrupt
        elif seconds:
            self.core.wait(seconds)

    # -- input ---------------------------------------------------------------

    def read_inputs(self) -> list[tuple[GameAction, dict[str, Any], float, str]]:
        """Return (action, data, input_time, source) for every new input."""
        out = []
        for k in self.kb.getKeys(keyList=list(self.keys) + [QUIT_KEY], waitRelease=False):
            if k.name == QUIT_KEY:
                raise KeyboardInterrupt
            out.append((self.keys[k.name], {}, float(k.tDown), f"key:{k.name}"))
        if self.mouse is not None:
            down = bool(self.mouse.getPressed()[0])
            if down and not self._mouse_was_down:
                x, y = self.mouse.getPos()
                cell = pos_to_cell(float(x), float(y), self.args.grid_px)
                data = {"x": cell[0], "y": cell[1]} if cell else {}
                out.append((GameAction.ACTION6, data, self.core.getTime(), "mouse"))
            self._mouse_was_down = down
        return out

    # -- game loop -----------------------------------------------------------

    def play_response(self, runner: GameRunner, resp: Response, game_number: int) -> None:
        hold = max(1, round((1.0 / runner.default_fps) / self.frame_s))
        n = len(resp.frames)
        hud = level_text(resp.levels_completed, resp.win_levels)
        for i, frame in enumerate(resp.frames):
            first, last = i == 0, i == n - 1
            send = list(resp.onset_codes) if first else []
            if last:
                send.extend(resp.end_codes)
            self.draw_frame(frame, diode_on=bool(send), hud=hud)
            self.flip_with_codes(send, f"{resp.action.name} frame {i + 1}/{n}",
                                 frame_index=i, n_frames=n, state=resp.state.name,
                                 levels_completed=resp.levels_completed)
            if not last:
                for _ in range(hold - 1):  # keep the frame for 1/default_fps s
                    self.draw_frame(frame, diode_on=False, hud=hud)
                    self.win.flip()

    def play_game(self, game_id: str, game_number: int) -> None:
        runner = GameRunner(self.arcade, game_id)
        self.log.context = {"game_id": game_id, "game_number": game_number}
        limit = self.core.getTime() + self.args.minutes_per_game * 60

        hud = level_text(0, runner.last.win_levels)
        self.draw_frame(runner.current_frame, diode_on=True, hud=hud)
        self.flip_with_codes([codes.game_start(game_number), codes.LEVEL_START], f"game_start {game_id}")
        self.kb.clearEvents()

        while self.core.getTime() < limit:
            for action, data, input_t, source in self.read_inputs():
                # The pad has no reset button: after game over, any input resets.
                # For a reset during a level, the operator presses R (docs/02, 2.6).
                if runner.last.state is GameState.GAME_OVER and action is not GameAction.RESET:
                    action, data, source = GameAction.RESET, {}, f"{source} auto_reset"
                fields = dict(action=action.name, x=data.get("x", ""), y=data.get("y", ""),
                              input_t=f"{input_t:.6f}", note=source)
                if not runner.is_allowed(action) or (action is GameAction.ACTION6 and not data):
                    self.log.write("input_ignored", **fields)
                    self.trig.pulse(codes.INPUT_IGNORED, "input_ignored")
                    continue
                self.log.write("input", **fields)
                self.trig.pulse(codes.INPUT[action], action.name)
                resp = runner.apply(action, data)
                self.play_response(runner, resp, game_number)
                # Inputs made during an animation are dropped, then logged.
                dropped = self.kb.getKeys(keyList=list(self.keys), waitRelease=False)
                if dropped:
                    self.log.write("inputs_dropped", note=",".join(k.name for k in dropped))
                break  # read inputs again after each response
            else:
                self.draw_frame(runner.current_frame, diode_on=False,
                                hud=level_text(runner.last.levels_completed, runner.last.win_levels))
                self.win.flip()
                continue
            if runner.last.state is GameState.WIN:
                break

        self.trig.pulse(codes.GAME_END, f"game_end {game_id}")
        self.log.write("game_end", state=runner.last.state.name,
                       levels_completed=runner.last.levels_completed)
        self.log.context = {}

    def run(self) -> None:
        try:
            self.message("Waiting for the MEG operator.\n\nPress SPACE to start.", wait_keys=["space"])
            self.trig.pulse(codes.SESSION_START, "session_start")
            for number, game_id in enumerate(self.args.games, start=1):
                self.play_game(game_id, number)
                if number < len(self.args.games):
                    self.message("Rest.", code=codes.REST_START, seconds=self.args.rest_seconds)
                    self.message("Press SPACE for the next game.", code=codes.REST_END, wait_keys=["space"])
        except KeyboardInterrupt:
            self.log.write("aborted")
        finally:
            self.trig.pulse(codes.SESSION_END, "session_end")
            self.trig.close()
            if self.eyelink is not None:
                self.eyelink.stopRecording()
                self.eyelink.closeDataFile()
                self.eyelink.receiveDataFile("", str(self.out / f"{self.args.participant[:8]}.EDF"))
                self.eyelink.close()
            self.log.close()
            self.win.close()
            self.core.quit()


def main() -> None:
    Task(parse_args()).run()


if __name__ == "__main__":
    main()

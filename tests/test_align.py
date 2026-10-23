import csv
import json
import subprocess
import sys

import numpy as np
import pytest

mne = pytest.importorskip("mne")  # uv run --extra analysis pytest


def test_align_session_recovers_clocks(tmp_path):
    rng = np.random.default_rng(0)
    sfreq, first_samp = 1000.0, 12345
    codes = rng.choice([1, 2, 3, 4, 11, 12, 13, 14, 31, 41], size=300)
    t_meg = 5 + np.cumsum(rng.uniform(0.05, 12.0, size=300))  # about 30 min, s from the start of the .fif

    # .fif: 10-ms pulses on STI101, plus a response-pad bit (512) that the mask must drop
    n = int((t_meg[-1] + 5) * sfreq)
    sti = np.zeros(n)
    for c, t in zip(codes, t_meg):
        s = int(round(t * sfreq))
        sti[s:s + 10] = c
    sti[int(100 * sfreq):int(100 * sfreq) + 50] += 512
    info = mne.create_info(["STI101"], sfreq, ["stim"])
    raw = mne.io.RawArray(sti[None], info, first_samp=first_samp, verbose="error")
    fif = tmp_path / "test_raw.fif"
    raw.save(fif, verbose="error")

    # events.tsv: GetSecs clock with an offset, 20 ms/hour drift, 0.2 ms jitter; first 5 codes missing
    run = tmp_path / "run"
    run.mkdir()
    rate_tsv, off_tsv = 1 + 20 / 3.6e6, 1234.5
    t_tsv = (t_meg - off_tsv) / rate_tsv + rng.normal(0, 0.0002, 300)
    with open(run / "events.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["t", "event", "code", "game_id", "game_number", "action", "x", "y", "n_frames",
                    "state", "levels_completed", "note"])
        w.writerow([f"{t_tsv[0] - 1:.6f}", "input", "", "ls20", 1, 1, "", "", "", "", "", "mouse:wheel_up"])
        for c, t in list(zip(codes, t_tsv))[5:]:
            w.writerow([f"{t:.6f}", "trigger", c, "ls20", 1, "", "", "", "", "", "", ""])

    # .asc: EyeLink ms clock, messages about 0.5 ms after the pulse, plus samples and events
    rate_eye, off_eye = 1 - 50 / 3.6e6, -800.0
    t_eye = (t_meg + 0.0005 - off_eye) / rate_eye
    lines = ["SAMPLES\tGAZE\tLEFT\tRATE\t1000.00\n"]
    for k in range(3):
        lines.append(f"{t_eye[0] * 1000 + k:.0f}\t 512.0\t 384.0\t 1200.0\t...\n")
    lines.append(f"{t_eye[0] * 1000 + 3:.0f}\t   .\t   .\t    0.0\t...\n")
    lines.append(f"EFIX L   {t_eye[1] * 1000:.0f}\t{t_eye[1] * 1000 + 200:.0f}\t201\t 512.0\t 384.0\t 1200\n")
    lines += [f"MSG\t{t * 1000:.0f} TRIGGER {c} frame 1/1\n" for c, t in zip(codes, t_eye)]
    (run / "TEST.asc").write_text("".join(lines))

    subprocess.run([sys.executable, "scripts/align_session.py", "--fif", str(fif), "--run", str(run)], check=True)

    res = json.loads((run / "alignment.json").read_text())
    assert res["events_tsv"]["n_matched"] == 295
    assert abs(res["events_tsv"]["drift_ms_per_hour"] - 20) < 2
    assert res["events_tsv"]["residual_max_ms"] < 1.5
    assert res["eyelink"]["n_matched"] == 300
    assert abs(res["eyelink"]["drift_ms_per_hour"] + 50) < 2

    rows = list(csv.DictReader(open(run / "events_meg.tsv"), delimiter="\t"))
    trig = [r for r in rows if r["event"] == "trigger"]
    err = np.array([float(r["t_meg"]) for r in trig]) - t_meg[5:]
    assert np.max(np.abs(err)) < 0.0015
    assert int(trig[0]["meg_sample"]) == int(round(t_meg[5] * sfreq)) + first_samp

    gaze = np.load(run / "gaze_meg.npz")
    assert gaze["data"].shape == (4, 4) and np.isnan(gaze["data"][3, 1])
    assert abs(gaze["t_meg"][0] - (t_meg[0] + 0.0005)) < 0.0015
    eye_events = list(csv.DictReader(open(run / "eye_events_meg.tsv"), delimiter="\t"))
    assert eye_events[0]["type"] == "FIX" and abs(float(eye_events[0]["onset_meg"]) - t_meg[1] - 0.0005) < 0.0015

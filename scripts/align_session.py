"""Put events.tsv and the EyeLink data on the MEG clock, after a session.

The MEG (.fif, STI101), the stimulus PC (events.tsv, GetSecs) and the EyeLink
(.edf, its own ms clock) each record every trigger code. This script matches
the codes in order and fits a straight line per clock:
    t_meg = offset + rate * t_other
then uses it to convert every row to MEG time.

    uv run --extra analysis python scripts/align_session.py \\
        --fif P01_raw.fif --run data/P01_20261022-174800

Inputs:
    --fif   the MEG recording (from the MEG acquisition PC)
    --run   the run folder from the stimulus PC (events.tsv, and the .edf)
    --asc   optional: the EyeLink file as text. If left out, the script uses the
            .asc in the run folder, or makes one from the .edf with SR Research's
            edf2asc (EyeLink Developers Kit) if it is on the PATH.
    --eye-input  use the EyeLink INPUT events (trigger cable split to the EyeLink
            Host PC) instead of the TRIGGER messages: exact pulse times.

Outputs (in the run folder, or --out):
    alignment.json          the fits and how good they are
    matched_triggers.tsv    every matched code with its time on each clock
    events_meg.tsv          events.tsv + t_meg (s from the start of the .fif) + meg_sample
    eye_events_meg.tsv      fixations, saccades, blinks in MEG time
    gaze_meg.npz            every gaze sample in MEG time (t_meg + the asc columns)

t_meg is the same time base as raw.times in MNE. meg_sample counts like
mne.find_events (it includes raw.first_samp).
"""

import argparse
import csv
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

# Where the EyeLink Developers Kit puts edf2asc on Windows, if it is not on the PATH.
EDF2ASC_WINDOWS = [
    r"C:\Program Files (x86)\SR Research\EyeLink\bin\edf2asc.exe",
    r"C:\Program Files\SR Research\EyeLink\bin\edf2asc.exe",
    r"C:\Program Files (x86)\SR Research\EyeLink\bin\64\edf2asc.exe",
    r"C:\Program Files\SR Research\EyeLink\bin\64\edf2asc.exe",
]

MSG_TRIGGER = re.compile(r"^MSG\s+(\d+(?:\.\d+)?)\s+(?:(-?\d+)\s+)?TRIGGER\s+(\d+)")


def meg_triggers(fif: Path) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Codes and times (s, raw.times base) of every pulse in STI101, bits 1-8 only."""
    import mne

    raw = mne.io.read_raw_fif(fif, preload=False, verbose="error")
    # mask 0xFF: drop the response-pad bits (STI009-STI016) if the pads use them
    ev = mne.find_events(raw, stim_channel="STI101", mask=0xFF, mask_type="and",
                         uint_cast=True, shortest_event=1, verbose="error")
    sfreq = raw.info["sfreq"]
    return ev[:, 2], (ev[:, 0] - raw.first_samp) / sfreq, sfreq, raw.first_samp


def tsv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def tsv_triggers(rows: list[dict[str, str]]) -> tuple[np.ndarray, np.ndarray]:
    trig = [r for r in rows if r["event"] == "trigger"]
    return np.array([int(r["code"]) for r in trig]), np.array([float(r["t"]) for r in trig])


def find_asc(run: Path, asc: Path | None) -> Path | None:
    if asc:
        return asc
    found = sorted(run.glob("*.asc"))
    if found:
        return found[0]
    edfs = sorted(run.glob("*.edf"))
    if not edfs:
        return None
    exe = shutil.which("edf2asc") or next((p for p in EDF2ASC_WINDOWS if Path(p).is_file()), None)
    if exe is None:
        sys.exit(f"{edfs[0]} needs to be converted to text first. Install the EyeLink Developers Kit "
                 f"(SR Research) and run:  edf2asc {edfs[0]}   then run this script again.")
    subprocess.run([exe, "-y", str(edfs[0])], check=False)  # edf2asc exits non-zero on warnings
    out = edfs[0].with_suffix(".asc")
    if not out.exists():
        sys.exit(f"edf2asc did not make {out}")
    return out


def eye_triggers(asc: Path, use_input: bool) -> tuple[np.ndarray, np.ndarray]:
    """Codes and EyeLink times (s) from TRIGGER messages, or from INPUT port events."""
    codes, times, last = [], [], 0
    with open(asc, errors="replace") as f:
        for line in f:
            if use_input and line.startswith("INPUT"):
                _, t, value = line.split()[:3]
                value = int(value) & 0xFF
                if value and value != last:  # one event per pulse onset
                    codes.append(value)
                    times.append(float(t) / 1000)
                last = value
            elif not use_input and line.startswith("MSG"):
                m = MSG_TRIGGER.match(line)
                if m:
                    offset = int(m.group(2) or 0)  # "MSG time offset text": the event was at time - offset
                    codes.append(int(m.group(3)))
                    times.append((float(m.group(1)) - offset) / 1000)
    return np.array(codes, dtype=int), np.array(times)


def match(ref_codes: np.ndarray, codes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Index pairs (ref, other) where the two code sequences agree, in order."""
    sm = difflib.SequenceMatcher(None, ref_codes.tolist(), codes.tolist(), autojunk=False)
    i, j = [], []
    for block in sm.get_matching_blocks():
        i.extend(range(block.a, block.a + block.size))
        j.extend(range(block.b, block.b + block.size))
    return np.array(i, dtype=int), np.array(j, dtype=int)


def fit_clock(t_other: np.ndarray, t_meg: np.ndarray) -> dict:
    """t_meg = offset + rate * t_other, robust to a few bad pairs."""
    keep = np.ones(len(t_meg), bool)
    for _ in range(3):
        rate, offset = np.polyfit(t_other[keep], t_meg[keep], 1)
        res = t_meg - (offset + rate * t_other)
        mad = np.median(np.abs(res[keep] - np.median(res[keep])))
        keep = np.abs(res) < max(5 * 1.4826 * mad, 0.002)  # 2 ms floor: 1-ms MEG samples
    rate, offset = np.polyfit(t_other[keep], t_meg[keep], 1)
    res = t_meg - (offset + rate * t_other)
    return {
        "offset_s": float(offset), "rate": float(rate),
        "drift_ms_per_hour": float((rate - 1) * 3600 * 1000),
        "n_matched": int(len(t_meg)), "n_used": int(keep.sum()),
        "residual_sd_ms": float(np.std(res[keep]) * 1000),
        "residual_max_ms": float(np.max(np.abs(res[keep])) * 1000),
        "keep": keep,
    }


def convert(fit: dict, t: np.ndarray) -> np.ndarray:
    return fit["offset_s"] + fit["rate"] * t


def report(name: str, n_meg: int, n_other: int, fit: dict) -> None:
    print(f"{name}: {n_other} codes, {fit['n_matched']} matched to the MEG's {n_meg}, "
          f"{fit['n_used']} used in the fit")
    print(f"    offset {fit['offset_s']:.6f} s, drift {fit['drift_ms_per_hour']:+.2f} ms/hour, "
          f"residual SD {fit['residual_sd_ms']:.3f} ms, max {fit['residual_max_ms']:.3f} ms")
    if fit["n_matched"] < 0.9 * min(n_meg, n_other):
        print("    WARNING: under 90 % of the codes matched. Check that the files are from the same run.")
    if fit["residual_max_ms"] > 3:
        print("    WARNING: residual over 3 ms. Look at matched_triggers.tsv.")


def parse_eye(asc: Path) -> tuple[list[str], np.ndarray, list[tuple]]:
    """Gaze samples (time ms + values) and EFIX / ESACC / EBLINK events."""
    eyes, samples, events = ["L"], [], []
    with open(asc, errors="replace") as f:
        for line in f:
            if line[:1].isdigit():
                p = line.split()
                n = 1 + 3 * len(eyes)
                samples.append([float(v) if v != "." else np.nan for v in p[:n]])
            elif line.startswith("SAMPLES"):
                eyes = [e for e in ("LEFT", "RIGHT") if e in line.split()] or ["LEFT"]
            elif line.startswith(("EFIX", "ESACC", "EBLINK")):
                events.append(tuple(line.split()))
    cols = ["t_eye_ms"] + [f"{c}_{e[0]}" for e in eyes for c in ("x", "y", "pupil")]
    data = np.array([s for s in samples if len(s) == len(cols)])
    return cols, data, events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fif", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--asc", type=Path)
    ap.add_argument("--eye-input", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = a.out or a.run
    out.mkdir(parents=True, exist_ok=True)

    meg_codes, meg_t, sfreq, first_samp = meg_triggers(a.fif)
    rows = tsv_rows(a.run / "events.tsv")
    tsv_codes, tsv_t = tsv_triggers(rows)
    i, j = match(meg_codes, tsv_codes)
    if len(i) < 3:
        sys.exit("Fewer than 3 trigger codes match between the .fif and events.tsv.")
    tsv_fit = fit_clock(tsv_t[j], meg_t[i])
    report("events.tsv", len(meg_codes), len(tsv_codes), tsv_fit)
    result = {"fif": str(a.fif), "run": str(a.run), "sfreq": sfreq, "first_samp": int(first_samp),
              "events_tsv": {k: v for k, v in tsv_fit.items() if k != "keep"}}

    # matched_triggers.tsv: one row per MEG code, with the other clocks where they match
    table = {"code": meg_codes, "t_meg": meg_t, "t_tsv": np.full(len(meg_t), np.nan)}
    table["t_tsv"][i] = tsv_t[j]
    table["tsv_residual_ms"] = (meg_t - convert(tsv_fit, table["t_tsv"])) * 1000

    # events_meg.tsv: every row of events.tsv on the MEG clock
    with open(out / "events_meg.tsv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) + ["t_meg", "meg_sample"], delimiter="\t")
        w.writeheader()
        for r in rows:
            t = float(convert(tsv_fit, np.array(float(r["t"]))))
            w.writerow({**r, "t_meg": f"{t:.6f}", "meg_sample": int(round(t * sfreq)) + first_samp})

    asc = find_asc(a.run, a.asc)
    if asc is None:
        print("No .asc or .edf in the run folder: EyeLink skipped.")
    else:
        eye_codes, eye_t = eye_triggers(asc, a.eye_input)
        i, j = match(meg_codes, eye_codes)
        if len(i) < 3:
            sys.exit(f"Fewer than 3 trigger codes match between the .fif and {asc.name}.")
        eye_fit = fit_clock(eye_t[j], meg_t[i])
        report(f"EyeLink ({'INPUT' if a.eye_input else 'TRIGGER messages'})", len(meg_codes), len(eye_codes), eye_fit)
        result["eyelink"] = {"asc": str(asc), "source": "INPUT" if a.eye_input else "MSG TRIGGER",
                             **{k: v for k, v in eye_fit.items() if k != "keep"}}
        table["t_eye"] = np.full(len(meg_t), np.nan)
        table["t_eye"][i] = eye_t[j]
        table["eye_residual_ms"] = (meg_t - convert(eye_fit, table["t_eye"])) * 1000

        cols, gaze, events = parse_eye(asc)
        np.savez_compressed(out / "gaze_meg.npz", t_meg=convert(eye_fit, gaze[:, 0] / 1000),
                            columns=np.array(cols), data=gaze)
        with open(out / "eye_events_meg.tsv", "w", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["type", "eye", "onset_meg", "offset_meg", "duration_ms", "values"])
            for e in events:
                on, off = convert(eye_fit, np.array([float(e[2]), float(e[3])]) / 1000)
                w.writerow([e[0][1:], e[1], f"{on:.6f}", f"{off:.6f}", e[4], " ".join(e[5:])])
        print(f"    {len(gaze)} gaze samples, {len(events)} eye events")

    with open(out / "matched_triggers.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(list(table))
        for k in range(len(meg_t)):
            w.writerow([int(table["code"][k])] + [f"{table[c][k]:.6f}" for c in list(table)[1:]])
    (out / "alignment.json").write_text(json.dumps(result, indent=2))
    print(f"Written to {out}")


if __name__ == "__main__":
    main()

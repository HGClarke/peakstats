"""Pure ride-analytics math. No I/O, no fastapi — heavily unit-tested."""


def deltas(time: list[int]) -> list[float]:
    """Per-sample Δt seconds. First sample is weighted by the first gap (or 1.0)."""
    if not time:
        return []
    gaps = [float(time[i] - time[i - 1]) for i in range(1, len(time))]
    first = gaps[0] if gaps else 1.0
    return [first, *gaps]


def weighted_mean(time: list[int], series: list) -> float | None:
    """Δt-weighted mean of `series`, skipping None samples. None if no valid data."""
    if not series:
        return None
    dt = deltas(time)
    total_w = 0.0
    acc = 0.0
    for w, v in zip(dt, series, strict=False):
        if v is None:
            continue
        acc += v * w
        total_w += w
    return acc / total_w if total_w > 0 else None


def total_work_kj(time: list[int], watts: list | None) -> float | None:
    """Sum of watts·Δt over the ride, in kJ. None if no watts."""
    if not watts:
        return None
    dt = deltas(time)
    joules = sum((w or 0) * d for w, d in zip(watts, dt, strict=False))
    return joules / 1000.0


def normalized_power(time: list[int], watts: list | None) -> float | None:
    """30 s rolling-avg power → 4th power → mean → 4th root. None if no watts."""
    if not watts:
        return None
    clean = [w if w is not None else 0 for w in watts]
    window = 30
    if len(clean) < window:
        avg = sum(clean) / len(clean)
        return float(avg)
    rolling = []
    running = sum(clean[:window])
    rolling.append(running / window)
    for i in range(window, len(clean)):
        running += clean[i] - clean[i - window]
        rolling.append(running / window)
    fourth = sum(p**4 for p in rolling) / len(rolling)
    return float(fourth ** 0.25)


POWER_ZONES = [
    ("Z1", "Active Rec.",   0.0,  0.55),
    ("Z2", "Endurance",     0.55, 0.75),
    ("Z3", "Tempo",         0.75, 0.90),
    ("Z4", "Threshold",     0.90, 1.05),
    ("Z5", "VO₂ Max",       1.05, 1.20),
    ("Z6", "Anaerobic",     1.20, 1.50),
    ("Z7", "Neuromuscular", 1.50, None),
]
HR_ZONE_BOUNDS = [0.68, 0.78, 0.88, 0.95]
HR_ZONE_NAMES = ["Recovery", "Endurance", "Tempo", "Threshold", "Maximum"]

POWER_BIN_W = 10
POWER_BINS = 150       # [0, 1500) W; samples ≥ 1500 fold into the last bin
HR_BIN_BPM = 5
HR_BINS = 44           # [0, 220) bpm; overflow into the last bin


def _fmt_range(lo: int, hi: int | None, unit: str) -> str:
    if lo == 0 and hi is not None:
        return f"< {hi} {unit}"
    if hi is None:
        return f"> {lo} {unit}"
    return f"{lo}–{hi} {unit}"


def power_zones(ftp: int) -> list[dict]:
    """Return Coggan 7-zone power zones scaled to `ftp` watts."""
    out = []
    for z, name, lo_f, hi_f in POWER_ZONES:
        lo = round(lo_f * ftp)
        hi = round(hi_f * ftp) if hi_f is not None else None
        out.append({"z": z, "name": name, "range": _fmt_range(lo, hi, "W"), "lo": lo, "hi": hi})
    return out


def hr_zones(hr_max: int) -> list[dict]:
    """Return 5 HR zones scaled to `hr_max` bpm."""
    bounds = [round(b * hr_max) for b in HR_ZONE_BOUNDS]
    lo_edges: list[int] = [0, *bounds]
    hi_edges: list[int | None] = [*bounds, None]
    out = []
    for i, name in enumerate(HR_ZONE_NAMES):
        lo = lo_edges[i]
        hi = hi_edges[i]
        rng = _fmt_range(lo, hi, "bpm")
        out.append({"z": f"Z{i+1}", "name": name, "range": rng, "lo": lo, "hi": hi})
    return out


def compute_climbs(rows: list[dict]) -> list[dict]:
    """Add VAM (metres/hour) to each climb row and sort by category then time, desc."""
    out = []
    for r in rows:
        secs = r["elapsed_time_s"]
        vam = round(r["elev_gain_m"] / (secs / 3600)) if secs else 0
        out.append({**r, "vam": vam})
    out.sort(key=lambda c: (c["climb_category"], c["elapsed_time_s"]), reverse=True)
    return out


def histogram(time: list[int], series: list | None, bin_w: int, n_bins: int) -> list[float]:
    """Δt-weighted seconds per absolute bin. Overflow folds into the last bin;
    None samples are skipped. Empty/None series → a zero array of length n_bins."""
    out = [0.0] * n_bins
    if not series:
        return out
    dt = deltas(time)
    for w, v in zip(dt, series, strict=False):
        if v is None:
            continue
        idx = int(v // bin_w)
        idx = 0 if idx < 0 else min(idx, n_bins - 1)
        out[idx] += w
    return out


def zone_seconds_from_histogram(
    hist: list[float], bin_w: int, zones: list[dict]
) -> list[float]:
    """Sum each bin's seconds into the zone whose [lo, hi) contains the bin midpoint."""
    secs = [0.0] * len(zones)
    for i, s in enumerate(hist):
        mid = i * bin_w + bin_w / 2
        for j, z in enumerate(zones):
            hi = z["hi"]
            if mid >= z["lo"] and (hi is None or mid < hi):
                secs[j] += s
                break
    return secs


def buckets_from_zone_seconds(secs: list[float], zones: list[dict]) -> list[dict]:
    """Format per-zone seconds into {z,name,range,seconds,pct} dicts."""
    total = sum(secs) or 1.0
    return [
        {"z": z["z"], "name": z["name"], "range": z["range"],
         "seconds": round(secs[i]), "pct": round(secs[i] / total * 100, 1)}
        for i, z in enumerate(zones)
    ]


def time_in_zones(time: list[int], series: list, zones: list[dict]) -> list[dict]:
    """Δt-weighted seconds and percentage spent in each zone bucket."""
    dt = deltas(time)
    secs = [0.0] * len(zones)
    for w, v in zip(dt, series, strict=False):
        if v is None:
            continue
        for i, z in enumerate(zones):
            hi = z["hi"]
            if v >= z["lo"] and (hi is None or v < hi):
                secs[i] += w
                break
    return buckets_from_zone_seconds(secs, zones)

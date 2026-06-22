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

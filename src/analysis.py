"""GML fitting via OLS on log-transformed matching data."""
from __future__ import annotations
import math
from typing import Optional

from .data import GMLFit, ScheduleSummary


def fit_gml(
    summaries: list[ScheduleSummary],
    session_id: str,
    participant_id: str,
) -> Optional[GMLFit]:
    """Fit the generalized matching law: log(B1/B2) = a·log(R1/R2) + log(b).

    Excludes schedules with exclusive reinforcer acquisition (R1==0 or R2==0).
    Returns None if fewer than 2 data points remain after filtering.
    """
    points = []
    included = []
    for s in summaries:
        if s.phase != "experimental":
            continue
        if s.exclusive_acquisition:
            continue
        if s.B1 == 0 and s.B2 == 0:
            continue
        if s.R1 == 0 or s.R2 == 0:
            continue
        b_ratio = math.log(s.B1 / s.B2) if s.B2 > 0 else None
        r_ratio = math.log(s.R1 / s.R2) if s.R2 > 0 else None
        if b_ratio is None or r_ratio is None:
            continue
        points.append((r_ratio, b_ratio))
        included.append(s.schedule_index)

    n = len(points)
    if n < 2:
        return None

    # OLS: y = a*x + c  (c = log(b))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    if ss_xx == 0:
        return None
    a = ss_xy / ss_xx
    log_b = y_mean - a * x_mean

    # R²
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    y_pred = [a * x + log_b for x in xs]
    ss_res = sum((y - yp) ** 2 for y, yp in zip(ys, y_pred))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return GMLFit(
        session_id=session_id,
        participant_id=participant_id,
        schedules_included=included,
        n=n,
        sensitivity=a,
        log_bias=log_b,
        r_squared=r_squared,
    )

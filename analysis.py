from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures

SEGMENT_DEFINITIONS = [
    ('Very Low (< 3.0)', lambda s: s < 3.0),
    ('Low (3.0 - 3.8)', lambda s: (s >= 3.0) & (s < 3.9)),
    ('In Range (3.9 - 10.0)', lambda s: (s >= 3.9) & (s <= 10.0)),
    ('High (10.1 - 13.9)', lambda s: (s > 10.0) & (s <= 13.9)),
    ('Very High (> 13.9)', lambda s: s > 13.9),
]


@dataclass(frozen=True)
class AnalysisResult:
    period_name: str
    raw_count: int
    clean_count: int
    avg_mmol: float
    clean_frame: pd.DataFrame
    segment_table: pd.DataFrame
    agp_frame: pd.DataFrame


def records_to_frame(raw_data: Iterable[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(list(raw_data))
    if frame.empty:
        return pd.DataFrame(columns=['noise', 'sgv', 'date'])

    for column in ('noise', 'sgv', 'date'):
        if column not in frame.columns:
            frame[column] = np.nan

    return frame[['noise', 'sgv', 'date']].copy()


def prepare_clean_frame(raw_data: Iterable[dict]) -> pd.DataFrame:
    frame = records_to_frame(raw_data)
    if frame.empty:
        return frame.assign(mmol=pd.Series(dtype='float64'))

    clean = frame.copy()
    clean['noise'] = pd.to_numeric(clean['noise'], errors='coerce')
    clean['sgv'] = pd.to_numeric(clean['sgv'], errors='coerce')
    clean['date'] = pd.to_numeric(clean['date'], errors='coerce')

    clean = clean.dropna(subset=['noise', 'sgv', 'date'])
    clean = clean[(clean['noise'] < 5.0) & (clean['sgv'] > 0)]
    clean = clean.assign(
        date_ms=clean['date'].astype('int64'),
        timestamp=pd.to_datetime(clean['date'], unit='ms', errors='coerce'),
    )
    clean = clean.dropna(subset=['timestamp'])
    clean = clean.assign(
        mmol=clean['sgv'] / 18.0,
        hour_decimal=clean['timestamp'].dt.hour + clean['timestamp'].dt.minute / 60.0,
    )

    return clean.reset_index(drop=True)


def calculate_clean_count(clean_frame: pd.DataFrame) -> int:
    return int(len(clean_frame))


def calculate_average_mmol(clean_frame: pd.DataFrame) -> Optional[float]:
    if clean_frame.empty:
        return None
    return float(clean_frame['mmol'].mean())


def build_segment_table(clean_frame: pd.DataFrame) -> pd.DataFrame:
    total = calculate_clean_count(clean_frame)
    rows = []

    if total == 0:
        return pd.DataFrame(columns=['segment', 'count', 'percent'])

    mmol = clean_frame['mmol']
    for name, matcher in SEGMENT_DEFINITIONS:
        mask = matcher(mmol)
        count = int(mask.sum())
        percent = (count / total) * 100.0
        rows.append({'segment': name, 'count': count, 'percent': percent})

    return pd.DataFrame(rows)


def build_agp_frame(clean_frame: pd.DataFrame, min_bucket_size: int = 6) -> pd.DataFrame:
    if clean_frame.empty:
        return pd.DataFrame(columns=['time_center', 'count', 'p10', 'p25', 'p50', 'p75', 'p90'])

    working = clean_frame[['hour_decimal', 'mmol']].dropna().copy()
    if working.empty:
        return pd.DataFrame(columns=['time_center', 'count', 'p10', 'p25', 'p50', 'p75', 'p90'])

    working['time_center'] = np.floor(working['hour_decimal'] * 2) / 2 + 0.25
    grouped = working.groupby('time_center')['mmol']

    agp = grouped.agg(
        count='count',
        p10=lambda s: float(np.percentile(s, 10)),
        p25=lambda s: float(np.percentile(s, 25)),
        p50=lambda s: float(np.percentile(s, 50)),
        p75=lambda s: float(np.percentile(s, 75)),
        p90=lambda s: float(np.percentile(s, 90)),
    ).reset_index()

    agp = agp[agp['count'] >= min_bucket_size].sort_values('time_center').reset_index(drop=True)
    return agp


# Forecast/prediction functionality removed per request.


def generate_3day_forecast(raw_data: Iterable[dict], now_ms: int) -> pd.DataFrame:
    clean_frame = prepare_clean_frame(list(raw_data))
    cols = ['timestamp', 'p10', 'p25', 'p50', 'p75', 'p90']
    if clean_frame.empty:
        return pd.DataFrame(columns=cols)

    working = clean_frame[['timestamp', 'mmol']].dropna().copy()
    if working.empty:
        return pd.DataFrame(columns=cols)

    working['hour_decimal'] = working['timestamp'].dt.hour + working['timestamp'].dt.minute / 60.0

    if len(working) > 2000:
        working = working.sample(2000, random_state=42)

    start_ts_num = float(working['timestamp'].min().value) / 10**9
    time_continuous = (working['timestamp'].values.astype(np.int64) / 10**9 - start_ts_num) / 3600.0
    hour_series = working['hour_decimal'].values

    X = np.column_stack([
        time_continuous,
        np.sin(2 * np.pi * hour_series / 24),
        np.cos(2 * np.pi * hour_series / 24),
        np.sin(4 * np.pi * hour_series / 24),
        np.cos(4 * np.pi * hour_series / 24),
        np.sin(6 * np.pi * hour_series / 24),
        np.cos(6 * np.pi * hour_series / 24),
        np.sin(8 * np.pi * hour_series / 24),
        np.cos(8 * np.pi * hour_series / 24),
        np.sin(12 * np.pi * hour_series / 24),
        np.cos(12 * np.pi * hour_series / 24),
        np.sin(24 * np.pi * hour_series / 24),
        np.cos(24 * np.pi * hour_series / 24)
    ])
    y = working['mmol'].values

    model = make_pipeline(PolynomialFeatures(degree=5, include_bias=False), LinearRegression())
    model.fit(X, y)
    
    y_pred_all = model.predict(X)
    
    residuals = y - y_pred_all
    safe_std = float(max(np.std(residuals), 0.5))

    start_ts = pd.to_datetime(now_ms, unit='ms')
    rows = []

    for h in range(72 * 10): # Tenths of hour (every 6 minutes)
        target_ts = start_ts + pd.Timedelta(hours=h/10.0)
        td_hour = target_ts.hour + target_ts.minute / 60.0
        tc_h = (float(target_ts.value) / 10**9 - start_ts_num) / 3600.0

        x_pred = np.array([[
            tc_h,
            np.sin(2 * np.pi * td_hour / 24),
            np.cos(2 * np.pi * td_hour / 24),
            np.sin(4 * np.pi * td_hour / 24),
            np.cos(4 * np.pi * td_hour / 24),
            np.sin(6 * np.pi * td_hour / 24),
            np.cos(6 * np.pi * td_hour / 24),
            np.sin(8 * np.pi * td_hour / 24),
            np.cos(8 * np.pi * td_hour / 24),
            np.sin(12 * np.pi * td_hour / 24),
            np.cos(12 * np.pi * td_hour / 24),
            np.sin(24 * np.pi * td_hour / 24),
            np.cos(24 * np.pi * td_hour / 24)
        ]])
        y_mean = float(model.predict(x_pred)[0])

        dist = norm(loc=y_mean, scale=safe_std)

        rows.append({
            'timestamp': target_ts,
            'p10': float(dist.ppf(0.10)),
            'p25': float(dist.ppf(0.25)),
            'p50': float(dist.ppf(0.50)),
            'p75': float(dist.ppf(0.75)),
            'p90': float(dist.ppf(0.90)),
        })

    return pd.DataFrame(rows)


def build_analysis_result(raw_data: Iterable[dict], period_name: str) -> AnalysisResult:
    raw_list = list(raw_data)
    clean_frame = prepare_clean_frame(raw_list)
    clean_count = calculate_clean_count(clean_frame)
    avg_mmol = calculate_average_mmol(clean_frame)
    segment_table = build_segment_table(clean_frame)
    agp_frame = build_agp_frame(clean_frame)

    return AnalysisResult(
        period_name=period_name,
        raw_count=len(raw_list),
        clean_count=clean_count,
        avg_mmol=avg_mmol if avg_mmol is not None else float('nan'),
        clean_frame=clean_frame,
        segment_table=segment_table,
        agp_frame=agp_frame,
    )

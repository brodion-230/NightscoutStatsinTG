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


def build_next_week_agp_forecast(clean_frame: pd.DataFrame, min_bucket_size: int = 6) -> pd.DataFrame:
    cols = ['forecast_ts', 'p10', 'p25', 'p50', 'p75', 'p90']
    if clean_frame.empty or 'timestamp' not in clean_frame.columns:
        return pd.DataFrame(columns=cols)

    working = clean_frame[['timestamp', 'hour_decimal', 'mmol']].dropna().copy()
    if working.empty:
        return pd.DataFrame(columns=cols)

    working['weekday'] = working['timestamp'].dt.weekday
    working['time_center'] = np.floor(working['hour_decimal'] * 2) / 2 + 0.25

    def safe_percentile(s, p):
        return float(np.percentile(s, p)) if len(s) >= min_bucket_size else np.nan

    global_agp = working.groupby('time_center')['mmol'].agg(
        p10=lambda s: safe_percentile(s, 10),
        p25=lambda s: safe_percentile(s, 25),
        p50=lambda s: safe_percentile(s, 50),
        p75=lambda s: safe_percentile(s, 75),
        p90=lambda s: safe_percentile(s, 90),
    ).reset_index()

    wd_agp = working.groupby(['weekday', 'time_center'])['mmol'].agg(
        count='count',
        p10=lambda s: float(np.percentile(s, 10)),
        p25=lambda s: float(np.percentile(s, 25)),
        p50=lambda s: float(np.percentile(s, 50)),
        p75=lambda s: float(np.percentile(s, 75)),
        p90=lambda s: float(np.percentile(s, 90)),
    ).reset_index()

    last_ts = working['timestamp'].max()
    start_ts = last_ts.replace(hour=0, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)

    rows = []
    for day_offset in range(7):
        target_date = start_ts + pd.Timedelta(days=day_offset)
        target_wd = target_date.weekday()
        for h in range(48):
            tc = h / 2 + 0.25
            forecast_ts = target_date + pd.Timedelta(hours=h / 2)
            
            match = wd_agp[(wd_agp['weekday'] == target_wd) & (wd_agp['time_center'] == tc)]
            if not match.empty and match.iloc[0]['count'] >= min_bucket_size:
                r = match.iloc[0]
                rows.append({
                    'forecast_ts': forecast_ts,
                    'p10': r['p10'], 'p25': r['p25'], 'p50': r['p50'], 'p75': r['p75'], 'p90': r['p90']
                })
            else:
                gm = global_agp[global_agp['time_center'] == tc]
                if not gm.empty and pd.notna(gm.iloc[0]['p50']):
                    r = gm.iloc[0]
                    rows.append({
                        'forecast_ts': forecast_ts,
                        'p10': r['p10'], 'p25': r['p25'], 'p50': r['p50'], 'p75': r['p75'], 'p90': r['p90']
                    })
                else:
                    rows.append({
                        'forecast_ts': forecast_ts,
                        'p10': np.nan, 'p25': np.nan, 'p50': np.nan, 'p75': np.nan, 'p90': np.nan
                    })

    return pd.DataFrame(rows).dropna().reset_index(drop=True)


def generate_3day_forecast(raw_data: Iterable[dict], now_ms: int) -> pd.DataFrame:
    clean_frame = prepare_clean_frame(list(raw_data))
    cols = ['timestamp', 'p10', 'p25', 'p50', 'p75', 'p90']
    if clean_frame.empty:
        return pd.DataFrame(columns=cols)

    working = clean_frame[['timestamp', 'mmol']].dropna().copy()
    if working.empty:
        return pd.DataFrame(columns=cols)

    working['hour_decimal'] = working['timestamp'].dt.hour + working['timestamp'].dt.minute / 60.0

    if len(working) > 1000:
        working = working.sample(1000, random_state=42)

    X = working[['hour_decimal']].values
    y = working['mmol'].values

    model = make_pipeline(PolynomialFeatures(degree=5), LinearRegression())
    model.fit(X, y)
    
    y_pred_all = model.predict(X)
    std_dev = np.std(y - y_pred_all)
    safe_std = float(max(std_dev, 0.1))

    start_ts = pd.to_datetime(now_ms, unit='ms')
    rows = []

    for h in range(72 * 2): # Halves of hour
        target_ts = start_ts + pd.Timedelta(hours=h/2.0)
        td_hour = target_ts.hour + target_ts.minute / 60.0

        y_mean = float(model.predict([[td_hour]])[0])

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

import math

import pandas as pd

from analysis import build_analysis_result, prepare_clean_frame


def test_prepare_clean_frame_drops_invalid_rows_by_subset_and_filter():
    raw = [
        {'noise': '1', 'sgv': '180', 'date': '1710000000000'},  # valid numeric strings
        {'noise': None, 'sgv': 150, 'date': 1710000300000},  # noise missing -> dropped by subset
        {'noise': 'abc', 'sgv': 120, 'date': 1710000600000},  # noise non-numeric -> dropped
        {'noise': 1, 'sgv': 'bad', 'date': 1710000900000},  # sgv non-numeric -> dropped
        {'noise': 1, 'sgv': 140, 'date': 'bad-date'},  # date non-numeric -> dropped
        {'noise': 5.1, 'sgv': 140, 'date': 1710001200000},  # filtered by noise < 5
        {'noise': 2.0, 'sgv': 0, 'date': 1710001500000},  # filtered by sgv > 0
    ]

    clean = prepare_clean_frame(raw)

    assert len(clean) == 1
    assert {'noise', 'sgv', 'date', 'date_ms', 'timestamp', 'mmol', 'hour_decimal'}.issubset(clean.columns)
    assert clean.iloc[0]['noise'] == 1
    assert clean.iloc[0]['sgv'] == 180
    assert math.isclose(clean.iloc[0]['mmol'], 10.0, rel_tol=1e-9)
    assert pd.notna(clean.iloc[0]['timestamp'])


def test_build_analysis_result_counts_and_average_after_dropna_strategy():
    raw = [
        {'noise': 1, 'sgv': 90, 'date': 1710000000000},
        {'noise': 2, 'sgv': 180, 'date': 1710000300000},
        {'noise': None, 'sgv': 100, 'date': 1710000600000},  # dropped by subset
        {'noise': 4, 'sgv': 'oops', 'date': 1710000900000},  # dropped by subset
        {'noise': 6, 'sgv': 120, 'date': 1710001200000},  # dropped by mask
    ]

    result = build_analysis_result(raw, period_name='Test period')

    assert result.period_name == 'Test period'
    assert result.raw_count == 5
    assert result.clean_count == 2
    assert not math.isnan(result.avg_mmol)
    assert math.isclose(result.avg_mmol, (90 / 18 + 180 / 18) / 2, rel_tol=1e-9)


def test_build_next_week_agp_forecast_empty():
    from analysis import build_next_week_agp_forecast
    df = build_next_week_agp_forecast(pd.DataFrame())
    assert df.empty


def test_build_next_week_agp_forecast_generates_forecast():
    from analysis import build_next_week_agp_forecast
    from datetime import datetime, timedelta
    
    now = datetime(2026, 4, 15, 12, 0)
    data = []
    # Generate some dummy data covering a week, every 30 mins
    for d in range(14):
        for h in range(48):
            dt = now - timedelta(days=d, minutes=h*30)
            data.append({
                'noise': 1, 'sgv': 100, 'date': int(dt.timestamp() * 1000)
            })
            
    df = prepare_clean_frame(data)
    forecast_df = build_next_week_agp_forecast(df, min_bucket_size=1)
    
    assert not forecast_df.empty
    # We generated data, forecast should give 7 days * 48 half-hours = 336 rows
    assert len(forecast_df) == 336
    assert set(['forecast_ts', 'p10', 'p25', 'p50', 'p75', 'p90']).issubset(forecast_df.columns)
    assert not forecast_df['p50'].isna().any()

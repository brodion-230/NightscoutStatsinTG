from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from analysis import AnalysisResult
from charts import (
    create_agp_figure,
    create_distribution_figure,
    figure_to_png_bytes,
    show_figure,
)


def _empty_result() -> AnalysisResult:
    return AnalysisResult(
        period_name='Test',
        raw_count=0,
        clean_count=0,
        avg_mmol=float('nan'),
        clean_frame=pd.DataFrame(),
        segment_table=pd.DataFrame(),
        agp_frame=pd.DataFrame(),
    )


def test_create_agp_figure_returns_none_for_empty_frame():
    fig = create_agp_figure(_empty_result())
    assert fig is None


def test_create_distribution_figure_returns_none_for_empty_clean_frame():
    fig = create_distribution_figure(_empty_result())
    assert fig is None


def test_create_forecast_agp_figure_returns_none_for_empty_frame():
    from charts import create_forecast_agp_figure

    fig = create_forecast_agp_figure(pd.DataFrame())
    assert fig is None


def test_create_forecast_agp_figure_returns_figure():
    from charts import create_forecast_agp_figure
    import datetime

    now = datetime.datetime.now()
    forecast_frame = pd.DataFrame(
        {
            'forecast_ts': [now, now + datetime.timedelta(hours=1)],
            'p10': [4.0, 4.0],
            'p25': [5.0, 5.0],
            'p50': [6.0, 6.0],
            'p75': [7.0, 7.0],
            'p90': [8.0, 8.0],
        }
    )
    fig = create_forecast_agp_figure(forecast_frame)
    assert fig is not None
    assert len(fig.axes) > 0
    fig.clf()


def test_create_agp_figure_contains_expected_title_and_lines():
    result = AnalysisResult(
        period_name='Last 14 days',
        raw_count=6,
        clean_count=6,
        avg_mmol=6.2,
        clean_frame=pd.DataFrame({'mmol': [5.0, 6.0, 7.0]}),
        segment_table=pd.DataFrame(),
        agp_frame=pd.DataFrame(
            {
                'time_center': [0.25, 0.75, 1.25],
                'count': [6, 6, 6],
                'p10': [4.2, 4.5, 4.8],
                'p25': [4.8, 5.1, 5.3],
                'p50': [5.4, 5.8, 6.1],
                'p75': [6.1, 6.4, 6.8],
                'p90': [6.9, 7.2, 7.6],
            }
        ),
    )

    fig = create_agp_figure(result)
    assert fig is not None
    ax = fig.axes[0]
    assert 'Daily Glucose Profile (AGP) (Last 14 days)' == ax.get_title()
    # Median + two threshold horizontal lines.
    assert len(ax.lines) >= 3
    fig.clf()


def test_create_distribution_figure_has_histogram_and_avg_line():
    clean = pd.DataFrame({'mmol': [4.2, 5.5, 6.0, 7.2, 9.1, 10.5]})
    result = AnalysisResult(
        period_name='Last 30 days',
        raw_count=6,
        clean_count=6,
        avg_mmol=float(clean['mmol'].mean()),
        clean_frame=clean,
        segment_table=pd.DataFrame(),
        agp_frame=pd.DataFrame(),
    )

    fig = create_distribution_figure(result)
    assert fig is not None
    ax = fig.axes[0]
    assert 'Glucose Level Distribution (Last 30 days)' == ax.get_title()
    assert len(ax.patches) > 0
    assert len(ax.lines) >= 1
    fig.clf()


def test_figure_to_png_bytes_returns_png_header():
    clean = pd.DataFrame({'mmol': [4.0, 6.0, 8.0, 9.0]})
    result = AnalysisResult(
        period_name='Bytes',
        raw_count=4,
        clean_count=4,
        avg_mmol=float(clean['mmol'].mean()),
        clean_frame=clean,
        segment_table=pd.DataFrame(),
        agp_frame=pd.DataFrame(),
    )
    fig = create_distribution_figure(result)

    png = figure_to_png_bytes(fig)

    assert isinstance(png, bytes)
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    assert len(png) > 1000
    fig.clf()


def test_show_figure_calls_show_and_close_for_real_figure():
    clean = pd.DataFrame({'mmol': [5.0, 6.0, 7.0]})
    result = AnalysisResult(
        period_name='Display',
        raw_count=3,
        clean_count=3,
        avg_mmol=6.0,
        clean_frame=clean,
        segment_table=pd.DataFrame(),
        agp_frame=pd.DataFrame(),
    )
    fig = create_distribution_figure(result)

    with patch('charts.plt.show') as show_mock, patch('charts.plt.close') as close_mock:
        show_figure(fig)
        show_mock.assert_called_once()
        close_mock.assert_called_once_with(fig)


def test_show_figure_does_nothing_for_none():
    with patch('charts.plt.show') as show_mock, patch('charts.plt.close') as close_mock:
        show_figure(None)
        show_mock.assert_not_called()
        close_mock.assert_not_called()

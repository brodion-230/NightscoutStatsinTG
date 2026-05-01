from __future__ import annotations

from io import BytesIO
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from analysis import AnalysisResult


def create_agp_figure(result: AnalysisResult):
    if result.agp_frame.empty:
        print('[!] Not enough data in 30-minute buckets to draw AGP chart.')
        return None

    fig, ax = plt.subplots(figsize=(12, 6))
    data = result.agp_frame

    ax.fill_between(data['time_center'], data['p10'], data['p90'], color='blue', alpha=0.15, label='10%-90% percentile')
    ax.fill_between(data['time_center'], data['p25'], data['p75'], color='darkblue', alpha=0.4, label='25%-75% percentile')
    ax.plot(data['time_center'], data['p50'], color='black', linewidth=2, label='Median')

    ax.axhline(10.0, color='goldenrod', linewidth=1.5, label='High (10.0)')
    ax.axhline(3.9, color='red', linewidth=1.5, label='Low (3.9)')

    ax.set_title(f'Daily Glucose Profile (AGP) ({result.period_name})', fontsize=14, fontweight='bold')
    ax.set_xlabel('Time of Day', fontsize=12)
    ax.set_ylabel('Glucose (mmol/L)', fontsize=12)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 2)])
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 22)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend(loc='upper right')
    fig.tight_layout()
    return fig


def create_distribution_figure(result: AnalysisResult):
    if result.clean_frame.empty:
        print('[!] No clean records to draw distribution chart.')
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    data = result.clean_frame['mmol'].to_numpy()

    ax.hist(data, bins=50, range=(2.0, 18.0), color='skyblue', edgecolor='black', alpha=0.8)
    ax.axvspan(3.9, 10.0, color='lightgreen', alpha=0.3, label='Target range (3.9 - 10.0)')
    ax.axvline(result.avg_mmol, color='red', linestyle='dashed', linewidth=2, label=f'Average: {result.avg_mmol:.2f}')

    ax.set_title(f'Glucose Level Distribution ({result.period_name})', fontsize=14)
    ax.set_xlabel('Glucose (mmol/L)', fontsize=12)
    ax.set_ylabel('Number of Measurements', fontsize=12)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    fig.tight_layout()
    return fig


def create_forecast_agp_figure(forecast_frame, period_name: str = "Next 7 days"):
    if forecast_frame is None or forecast_frame.empty:
        print('[!] Not enough data to draw forecast chart.')
        return None

    fig, ax = plt.subplots(figsize=(14, 6))
    data = forecast_frame

    ax.fill_between(data['forecast_ts'], data['p10'], data['p90'], color='purple', alpha=0.15, label='10%-90% percentile')
    ax.fill_between(data['forecast_ts'], data['p25'], data['p75'], color='darkviolet', alpha=0.4, label='25%-75% percentile')
    ax.plot(data['forecast_ts'], data['p50'], color='black', linewidth=2, label='Median Trend')

    ax.axhline(10.0, color='goldenrod', linewidth=1.5, label='High (10.0)')
    ax.axhline(3.9, color='red', linewidth=1.5, label='Low (3.9)')

    ax.set_title(f'Glucose Trend Forecast ({period_name})', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date / Time', fontsize=12)
    ax.set_ylabel('Glucose (mmol/L)', fontsize=12)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:00'))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))
    
    ax.set_ylim(0, 22)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend(loc='upper right')
    fig.tight_layout()
    return fig


def figure_to_png_bytes(fig) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    return buffer.getvalue()


def show_figure(fig) -> None:
    if fig is not None:
        plt.show()
        plt.close(fig)


def create_forecast_chart(forecast_df: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    x = forecast_df['timestamp']
    
    ax.fill_between(x, forecast_df['p10'], forecast_df['p90'], color='blue', alpha=0.1, label='10%-90%')
    ax.fill_between(x, forecast_df['p25'], forecast_df['p75'], color='blue', alpha=0.3, label='25%-75%')
    ax.plot(x, forecast_df['p50'], color='darkblue', linewidth=2, label='Median (p50)')
    
    ax.set_title("3-Day Glucose Forecast (Linear Regression)")
    ax.set_ylabel("Glucose (mmol/L)")
    ax.grid(True)
    ax.legend(loc='upper right')
    fig.autofmt_xdate()
    
    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png')
    plt.close(fig)
    return buf.getvalue()


def create_next_week_forecast_agp_figure(forecast_df: pd.DataFrame, title: str = "7-Day Forecast") -> bytes:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    x = forecast_df['timestamp']
    
    ax.fill_between(x, forecast_df['p10'], forecast_df['p90'], color='blue', alpha=0.1, label='10%-90%')
    ax.fill_between(x, forecast_df['p25'], forecast_df['p75'], color='blue', alpha=0.3, label='25%-75%')
    ax.plot(x, forecast_df['p50'], color='darkblue', linewidth=2, label='Median (p50)')
    
    ax.set_title(title, pad=20)
    ax.set_xlabel('Time of Day')
    ax.set_ylabel('Glucose (mmol/L)')
    ax.grid(True)
    ax.legend(loc='upper right')
    fig.autofmt_xdate()
    
    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png')
    plt.close(fig)
    return buf.getvalue()

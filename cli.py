from __future__ import annotations

import sys

from analysis import AnalysisResult, build_analysis_result, build_next_week_agp_forecast
from charts import create_agp_figure, create_distribution_figure, create_forecast_agp_figure, show_figure
from db import load_raw_data
from periods import build_all_time_query, build_last_days_query, build_month_query


def print_summary(result: AnalysisResult) -> None:
    print(f"\n--- Results: {result.period_name} ---")
    print(f"Records analyzed: {result.clean_count}")
    print(f"AVERAGE GLUCOSE:    {result.avg_mmol:.2f} mmol/L")
    print('-' * 55)
    print(f"{'Segment':<25} | {'Count':<10} | {'Percent':<10}")
    print('-' * 55)

    if result.segment_table.empty:
        print('No segments to display.')
        return

    for _, row in result.segment_table.iterrows():
        print(f"{row['segment']:<25} | {int(row['count']):<10} | {row['percent']:.2f}%")


def prompt_yes_no(message: str) -> bool:
    answer = input(message).strip().lower()
    return answer in {'y', 'yes'}


def run_analysis(query, period_name):
    raw_data = load_raw_data(query)

    if not raw_data:
        print(f"\n[!] No data found for period '{period_name}'.")
        return

    result = build_analysis_result(raw_data, period_name)

    if result.clean_count == 0:
        print(f"\n[!] No clean records for period {period_name}.")
        return

    print_summary(result)

    if prompt_yes_no('\nOpen AGP daily glucose profile chart? (y/n): '):
        agp_fig = create_agp_figure(result)
        show_figure(agp_fig)

    if prompt_yes_no('\nOpen value distribution chart? (y/n): '):
        dist_fig = create_distribution_figure(result)
        show_figure(dist_fig)


def main_menu():
    while True:
        print('\n=== NIGHTSCOUT STATISTICS MENU ===')
        print('1. Last 24 hours')
        print('2. Last 7 days')
        print('3. Last 30 days')
        print('4. Select specific month (MM.YYYY)')
        print('5. All-time statistics')
        print('6. Forecast next 7 days (based on last 3 months)')
        print('0. Exit')

        choice = input('\nChoose an option: ').strip()

        if choice == '1':
            query, name = build_last_days_query(1)
        elif choice == '2':
            query, name = build_last_days_query(7)
        elif choice == '3':
            query, name = build_last_days_query(30)
        elif choice == '4':
            date_str = input('Enter month and year (for example, 03.2026): ').strip()
            try:
                query, name = build_month_query(date_str)
            except Exception as exc:
                print(f'Format error: {exc}')
                continue
        elif choice == '5':
            query, name = build_all_time_query()
        elif choice == '6':
            query, name = build_last_days_query(90)
            raw_data = load_raw_data(query)
            if not raw_data:
                print("\n[!] No data found for last 90 days.")
                continue
            
            result = build_analysis_result(raw_data, name)
            if result.clean_count == 0:
                print("\n[!] No clean records for last 90 days.")
                continue
            
            forecast_df = build_next_week_agp_forecast(result.clean_frame)
            if forecast_df.empty:
                print("\n[!] Not enough data for forecast.")
                continue
                
            print(f"\nCreated forecast based on {result.clean_count} records from the last 90 days.")
            if prompt_yes_no('\nOpen Forecast chart? (y/n): '):
                fig = create_forecast_agp_figure(forecast_df)
                show_figure(fig)
            continue
        elif choice == '0':
            print('Exiting...')
            sys.exit()
        else:
            print('Invalid choice!')
            continue

        run_analysis(query, name)


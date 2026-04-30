from __future__ import annotations

from io import BytesIO
from typing import Any

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
except ImportError:
    ApplicationBuilder = None
    CommandHandler = None
    CallbackQueryHandler = None
    ContextTypes = None
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    MessageHandler = None
    filters = None

from analysis import build_analysis_result, build_next_week_agp_forecast, generate_3day_forecast
from charts import create_agp_figure, create_distribution_figure, create_forecast_agp_figure, create_forecast_chart, figure_to_png_bytes
from config import load_config
from db import load_raw_data, load_historical_periods
from periods import build_all_time_query, build_last_days_query, build_month_query
import time

HELP_TEXT = (
    'Available commands:\n'
    '/start - Show main menu\n'
    '/last24 - last 24 hours\n'
    '/last7 - last 7 days\n'
    '/last30 - last 30 days\n'
    '/month MM.YYYY - select month\n'
    '/all - all-time statistics\n'
    '/forecast - Predict next 3 days based on past 3 years'
)


def _message_or_none(update: Any):
    if hasattr(update, 'callback_query') and update.callback_query:
        return update.callback_query.message
    return getattr(update, 'message', None)


def get_main_menu_keyboard():
    if InlineKeyboardButton is None:
        return None
    keyboard = [
        [InlineKeyboardButton("Last 24 hours", callback_data='last24')],
        [InlineKeyboardButton("Last 7 days", callback_data='last7')],
        [InlineKeyboardButton("Last 30 days", callback_data='last30')],
        [InlineKeyboardButton("All-time statistics", callback_data='all')],
        [InlineKeyboardButton("Forecast next 3 days", callback_data='forecast')],
        [InlineKeyboardButton("Specific Month", callback_data='month_help')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_forecast_options_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Just last 3 weeks", callback_data='forecast_exec_0')],
        [InlineKeyboardButton("Past 1 year (same period)", callback_data='forecast_exec_1')],
        [InlineKeyboardButton("Past 2 years (same period)", callback_data='forecast_exec_2')],
        [InlineKeyboardButton("Past 3 years (same period)", callback_data='forecast_exec_3')],
    ]
    return InlineKeyboardMarkup(keyboard)


async def _send_report(update: Any, query, period_name: str, include_charts: bool = True):
    message = _message_or_none(update)
    if message is None:
        return

    raw_data = load_raw_data(query)
    if not raw_data:
        await message.reply_text(f'No data found for {period_name}.')
        return

    result = build_analysis_result(raw_data, period_name)
    if result.clean_count == 0:
        await message.reply_text(f'No clean records for {period_name}.')
        return

    lines = [
        f'Results: {result.period_name}',
        f'Records analyzed: {result.clean_count}',
        f'Average glucose: {result.avg_mmol:.2f} mmol/L',
        '',
        'Segments:',
    ]
    for _, row in result.segment_table.iterrows():
        lines.append(f"- {row['segment']}: {int(row['count'])} ({row['percent']:.2f}%)")

    await message.reply_text('\n'.join(lines))

    if not include_charts:
        return

    agp_fig = create_agp_figure(result)
    if agp_fig is not None:
        agp_png = figure_to_png_bytes(agp_fig)
        await message.reply_photo(photo=BytesIO(agp_png), caption='AGP chart')

    dist_fig = create_distribution_figure(result)
    if dist_fig is not None:
        dist_png = figure_to_png_bytes(dist_fig)
        await message.reply_photo(photo=BytesIO(dist_png), caption='Value distribution')


async def start_command(update: Any, context: Any):
    message = _message_or_none(update)
    if message is not None:
        await message.reply_text(
            'Nightscout statistics bot\n\nChoose an option below:',
            reply_markup=get_main_menu_keyboard()
        )


async def button_handler(update: Any, context: Any):
    query_cb = update.callback_query
    await query_cb.answer()
    
    choice = query_cb.data
    if choice == 'last24':
        q, name = build_last_days_query(1)
        await _send_report(update, q, name)
    elif choice == 'last7':
        q, name = build_last_days_query(7)
        await _send_report(update, q, name)
    elif choice == 'last30':
        q, name = build_last_days_query(30)
        await _send_report(update, q, name)
    elif choice == 'all':
        q, name = build_all_time_query()
        await _send_report(update, q, name)
    elif choice == 'forecast':
        await query_cb.message.reply_text('Choose dataset timeframe for forecast:', reply_markup=get_forecast_options_keyboard())
    elif choice.startswith('forecast_exec_'):
        years_back = int(choice.split('_')[-1])
        await execute_forecast(update, years_back)
    elif choice == 'month_help':
        await query_cb.message.reply_text('To get stats for a specific month, just type the month and year (e.g., 04.2026)')


async def execute_forecast(update: Any, years_back: int):
    message = _message_or_none(update)
    if message is None:
        return

    await message.reply_text(f'Loading data (years back: {years_back}) and generating 3-day forecast using Linear Regression...')

    now_ms = int(time.time() * 1000)
    
    raw_data = load_historical_periods(now_ms, window_days=21, years_back=years_back)
    if not raw_data:
        await message.reply_text(f'No historical data found for the past {years_back} years.')
        return

    forecast_df = generate_3day_forecast(raw_data, now_ms)
    if forecast_df is None or forecast_df.empty:
        await message.reply_text('Failed to generate forecast (not enough clean records).')
        return
        
    png_bytes = create_forecast_chart(forecast_df)
    await message.reply_photo(photo=BytesIO(png_bytes), caption=f'3-Day Glucose Forecast (Linear Regression, Dataset: {years_back} years back)')


async def handle_text(update: Any, context: Any):
    message = _message_or_none(update)
    if message is None or not message.text:
        return

    text = message.text.strip()
    import re
    if re.match(r'^\d{2}\.\d{4}$', text):
        try:
            query, name = build_month_query(text)
        except Exception as exc:
            await message.reply_text(f'Format error: {exc}')
            return
        await _send_report(update, query, name)


async def last24_command(update: Any, context: Any):
    query, name = build_last_days_query(1)
    await _send_report(update, query, name)


async def last7_command(update: Any, context: Any):
    query, name = build_last_days_query(7)
    await _send_report(update, query, name)


async def last30_command(update: Any, context: Any):
    query, name = build_last_days_query(30)
    await _send_report(update, query, name)


async def all_command(update: Any, context: Any):
    query, name = build_all_time_query()
    await _send_report(update, query, name)


async def month_command(update: Any, context: Any):
    message = _message_or_none(update)
    if message is None:
        return

    args = getattr(context, 'args', [])
    if not args:
        await message.reply_text('Usage: /month MM.YYYY')
        return

    try:
        query, name = build_month_query(args[0])
    except Exception as exc:
        await message.reply_text(f'Format error: {exc}')
        return

    await _send_report(update, query, name)


async def forecast_command(update: Any, context: Any):
    message = _message_or_none(update)
    if message is None:
        return
    await message.reply_text('Choose dataset timeframe for forecast:', reply_markup=get_forecast_options_keyboard())


def main() -> None:
    if ApplicationBuilder is None or CommandHandler is None:
        raise RuntimeError(
            'python-telegram-bot is not installed. Install requirements.txt to run the bot.'
        )

    config = load_config()
    if not config.telegram_bot_token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN is not set.')

    application = ApplicationBuilder().token(config.telegram_bot_token).build()
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('last24', last24_command))
    application.add_handler(CommandHandler('last7', last7_command))
    application.add_handler(CommandHandler('last30', last30_command))
    application.add_handler(CommandHandler('month', month_command))
    application.add_handler(CommandHandler('all', all_command))
    application.add_handler(CommandHandler('forecast', forecast_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    if MessageHandler is not None and filters is not None:
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()


if __name__ == '__main__':
    main()


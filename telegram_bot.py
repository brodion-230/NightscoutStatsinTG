from __future__ import annotations

from io import BytesIO
from typing import Any

try:
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
except ImportError:
    ApplicationBuilder = None
    CommandHandler = None
    ContextTypes = None

from analysis import build_analysis_result
from charts import create_agp_figure, create_distribution_figure, figure_to_png_bytes
from config import load_config
from db import load_raw_data
from periods import build_all_time_query, build_last_days_query, build_month_query


HELP_TEXT = (
    'Available commands:\n'
    '/last24 - last 24 hours\n'
    '/last7 - last 7 days\n'
    '/last30 - last 30 days\n'
    '/month MM.YYYY - select month\n'
    '/all - all-time statistics'
)


def _message_or_none(update: Any):
    return getattr(update, 'message', None)


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
        await message.reply_text('Nightscout statistics bot\n\n' + HELP_TEXT)


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

    application.run_polling()


if __name__ == '__main__':
    main()



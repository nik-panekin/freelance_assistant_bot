"""Модуль, обеспечивающий отправку пользователям уведомлений о новых проектах:
сообщением в Telegram и (или) в виде e-mail.
"""
import sys
import logging
import asyncio
import time
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html import escape
from random import randint

from aiogram import Bot
from aiogram.types import Message, ParseMode

from emoticons import *
import fl_parser
import database
from config import (NOTIFY_PERIOD, SHUTDOWN_PERIOD, SMTP_PORT, SMTP_SERVER,
                    BOT_EMAIL, BOT_PASSWORD)

# Минимальное и максимальное значение задержки после получения данных от
# сервера биржи фриланса (секунды). Используется во избежание 'бана'
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 10

# Максимальное количество новых проектов в одном сообщении
MAX_JOB_COUNT = 10

HTML_BEGIN = """\
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8">
    <title>Новые проекты от биржи фриланса</title>
  </head>
  <body>
"""

HTML_END = """\
  </body>
</html>
"""

# Бесконечный цикл: периодически отправлять пользователям уведомления о новых
# проектах соответственно их настройкам фильтров
async def notify_users_task(bot: Bot):
    start_time = time.monotonic()

    while True:
        await asyncio.sleep(NOTIFY_PERIOD)

        try:
            if await notify_users(bot):
                logging.info('Уведомления отправлены.')
            else:
                logging.info('Уведомлений к отправке нет.')
        except Exception as e:
            logging.error(e)

        if SHUTDOWN_PERIOD and time.monotonic() - start_time > SHUTDOWN_PERIOD:
            logging.info('Плановое завершение работы.')
            sys.exit()

# Отправить всем пользователям уведомления о новых проектах
async def notify_users(bot: Bot, user_id=None) -> bool:
    """Возвращаемое значение:
    True, если сообщения фактически были кому-то отправлены;
    False, если никаких отправок не было (к обработке ошибок это не относится).
    """
    result = False

    if user_id:
        user = database.get_settings(user_id)
        if user:
            users = [user]
        else:
            users = []
    else:
        users = database.get_settings_all() or []

    for user in users:
        if not (user['active'] or user['email_active']):
            continue

        for host in fl_parser.HOSTS:
            final_jobs = []
            for query in ['keywords', 'categories']:
                job_filters = database.get_filters(
                    user_id=user['user_id'], host=host, query=query) or []

                if not job_filters:
                    continue

                jobs = fl_parser.get_jobs(
                    host=host,
                    category_ids=job_filters[0]['categories'],
                    subcategory_ids=job_filters[0]['subcategories'],
                    keywords=job_filters[0]['keywords'])

                jobs = fl_parser.get_recent_jobs(
                    jobs=jobs, last_job_url=job_filters[0]['last_job_url'])

                if not jobs:
                    continue

                database.save_filter(
                    user_id=user['user_id'],
                    host=host,
                    categories=job_filters[0]['categories'],
                    subcategories=job_filters[0]['subcategories'],
                    keywords=job_filters[0]['keywords'],
                    last_job_url=jobs[0]['url'])

                for job in jobs:
                    if len(final_jobs) >= MAX_JOB_COUNT:
                        break

                    append = True
                    for final_job in final_jobs:
                        if job['url'] == final_job['url']:
                            append = False
                            break
                    if append:
                        final_jobs.append(job)

                await asyncio.sleep(randint(REQUEST_DELAY_MIN,
                                            REQUEST_DELAY_MAX))

            if user['active'] and final_jobs:
                msg = ''
                for index, job in enumerate(final_jobs):
                    msg += (f'<b><a href="{job["url"]}">{job["title"]}</a></b>'
                            + f'\n{EMO_MONEY} <b>{job["price"]}</b>'
                            + f' {EMO_POINT_RIGHT} '
                            + f'<b>{fl_parser.host_to_hashtag(host)}</b>'
                            + f'\n{job["description"]}')

                    if index < len(final_jobs) - 1:
                        msg += '\n\n\n'

                try:
                    await bot.send_message(user['user_id'], msg,
                                           parse_mode=ParseMode.HTML,
                                           disable_web_page_preview=True)
                    result = True
                except Exception as e:
                    logging.error(e)

            if user['email_active'] and final_jobs:
                text = ''
                html = HTML_BEGIN

                for index, job in enumerate(final_jobs):
                    html += (
                        f'<p>\n<b><a href="{job["url"]}">'
                        + f'{escape(job["title"])}</a></b>'
                        + f'<br><b>Бюджет проекта:</b> {job["price"]}<br>'
                        + f'{escape(job["description"])}\n</p>\n')

                    text += (f'Заголовок проекта: {job["title"]}\n'
                             + f'Ссылка на страницу проекта: {job["url"]}\n'
                             + f'Бюджет: {job["price"]}\n'
                             + f'Описание:\n{job["description"]}')

                    if index < len(final_jobs) - 1:
                        html += '<p>--- + --- + --- + --- + --- + ---</p>\n'
                        text += '\n\n--- + --- + --- + --- + --- + ---\n\n'

                html += HTML_END

                send_email(email_receiver=user['email'],
                           email_subject=f'Новые проекты от {host}: '
                                         + f'{final_jobs[0]["title"]}',
                           text_content=text, html_content=html)
                result = True

    return result

# Отправить пользователю от имени бота сообщение по e-mail
def send_email(email_receiver: str, email_subject: str,
               text_content: str, html_content: str):
    """Входные параметры:
    email_receiver: str - адрес получателя сообщения;
    email_subject: str - тема письма;
    text_content: str - содержимое письма в формате обычного текста (utf-8);
    html_content: str - содержимое письма в формате HTML (utf-8).
    """
    message = MIMEMultipart('alternative')

    message['Subject'] = email_subject
    message['From'] = f'Freelance Assistant Bot<{BOT_EMAIL}>'
    message['To'] = email_receiver

    message.attach(MIMEText(text_content, 'plain', 'utf-8'))
    message.attach(MIMEText(html_content, 'html', 'utf-8'))

    context = ssl.create_default_context()
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls(context=context)
        server.login(BOT_EMAIL, BOT_PASSWORD)
        server.sendmail(BOT_EMAIL, email_receiver, message.as_string())
    except Exception as e:
        logging.error(e)
    finally:
        server.quit()

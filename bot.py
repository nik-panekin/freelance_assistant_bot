"""Главный модуль бота, предназначен для непосредственного запуска. Инициирует
бесконечный цикл опроса серверов Telegram и отправки сообщений пользователям
о новых проектах.

Все обработчики сообщений, приходящих от Telegram, находятся здесь.
"""
import logging
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command, Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from aiogram.utils import executor

from config import BOT_TOKEN
from emoticons import *
import fl_parser
import database
import menu
from notifier import notify_users, notify_users_task

KEYWORDS_RE = r'^\w{3,16}(,\w{3,16}){0,15}$'

# Конечный автомат (FSM) для навигации по меню
class Menu(StatesGroup):
    root = State()
    input_email = State()
    select_host = State()
    select_filter_type = State()
    select_category = State()
    select_subcategory = State()
    input_keywords = State()
    confirm_delete = State()
    info = State()

database.init()
fl_parser.init()

loop = asyncio.get_event_loop()
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, loop=loop, storage=storage)

# Возвратить ссылку на метод отправки или редактирования сообщения
async def _get_message_func(message: Message, edit_message=True):
    if edit_message:
        return message.edit_text
    else:
        return message.answer

# Отобразить меню: root
async def show_root(message: Message, user_id: str,
                    info_text='', edit_message=True):
    await Menu.first()
    message_func = await _get_message_func(message, edit_message)
    await message_func(
        text=f'{info_text}{EMO_POINT_RIGHT} Выберите <b>действие</b> '
              'из списка:',
        reply_markup=menu.get_root(user_id=user_id), parse_mode=ParseMode.HTML)

# Переход в меню: root
@dp.message_handler(Command('start'), state='*')
async def menu_root(message: Message, state: FSMContext):
    await show_root(message, message.from_user.id, edit_message=False)

# Действие: активировать отправку сообщений
@dp.callback_query_handler(text='enable', state=Menu.root)
async def menu_enable(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    database.save_settings(user_id, active=True)
    await call.message.edit_reply_markup(reply_markup=menu.get_root(user_id))
    await call.answer('Отправка оповещений активирована!')

# Действие: отключить отправку сообщений
@dp.callback_query_handler(text='disable', state=Menu.root)
async def menu_disable(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    database.save_settings(user_id, active=False)
    await call.message.edit_reply_markup(reply_markup=menu.get_root(user_id))
    await call.answer('Отправка оповещений отключена!')

# Действие: активировать сообщения по e-mail
@dp.callback_query_handler(text='email_enable', state=Menu.root)
async def menu_email_enable(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    database.save_settings(user_id, email_active=True)
    await call.message.edit_reply_markup(reply_markup=menu.get_root(user_id))
    await call.answer('Оповещения по e-mail активированы!')

# Действие: отключить сообщения по e-mail
@dp.callback_query_handler(text='email_disable', state=Menu.root)
async def menu_email_disable(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    database.save_settings(user_id, email_active=False)
    await call.message.edit_reply_markup(reply_markup=menu.get_root(user_id))
    await call.answer('Оповещения по e-mail отключены!')

# Отобразить меню: select_host
async def show_select_host(message: Message, edit_message=True):
    await Menu.select_host.set()
    message_func = await _get_message_func(message, edit_message)
    await message_func(
        text=f'{EMO_POINT_RIGHT} Выберите <b>биржу фриланса</b> из списка:',
        reply_markup=menu.get_select_host(), parse_mode=ParseMode.HTML)

# Переход в меню: select_host
@dp.callback_query_handler(text='select_host', state=Menu.root)
async def menu_select_host(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_select_host(call.message)

# Переход в состояние: input_email
@dp.callback_query_handler(text='input_email', state=Menu.root)
async def menu_input_email(call: CallbackQuery, state: FSMContext):
    await call.answer()

    settings = database.get_settings(call.from_user.id) or {}
    if settings.get('email'):
        msg = f'Текущий e-mail: <b>{settings["email"]}</b>.'
    else:
        msg = 'Текущий e-mail <b>не задан</b>.'

    msg += '\n\nВведите <b>e-mail</b> для оповещений о новых проектах:'

    await Menu.input_email.set()
    await call.message.edit_text(text=msg, reply_markup=menu.get_back(),
                                 parse_mode=ParseMode.HTML)

# Действие: сохранение e-mail для оповещений и обработка ошибки ввода
@dp.message_handler(state=Menu.input_email)
async def input_email(message: Message, state: FSMContext):
    if message.entities:
        for entity in message.entities:
            if entity['type'] == 'email':
                first = entity['offset']
                last = entity['offset'] + entity['length']
                database.save_settings(message.from_user.id,
                                       email=message.text[first:last])
                await show_root(
                    message, message.from_user.id,
                    info_text=f'{EMO_INFORMATION} <i>E-mail для оповещений '
                               'сохранён!</i>\n\n', edit_message=False)
                return

    await message.answer(f'{EMO_NO_ENTRY} <i>Неправильный формат e-mail!</i>'
                         '\n\nПовторите ввод:', reply_markup=menu.get_back(),
                         parse_mode=ParseMode.HTML)

# Возврат из состояния: input_email
@dp.callback_query_handler(text='back', state=Menu.input_email)
async def return_from_input_email(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_root(call.message, call.from_user.id)

# Переходв в меню: confirm_delete
@dp.callback_query_handler(text='confirm_delete', state=Menu.root)
async def menu_confirm_delete(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await Menu.confirm_delete.set()
    await call.message.edit_text(
        text=f'{EMO_WARNING} <b>Внимание!</b> '
             'Удаление фильтров происходит <b>безвозвратно</b>.',
        reply_markup=menu.get_confirm_delete(), parse_mode=ParseMode.HTML)

# Действие: удаление всех фильтров оповещений
@dp.callback_query_handler(text='clear', state=Menu.confirm_delete)
async def confirm_delete(call: CallbackQuery, state: FSMContext):
    database.delete_filters(call.from_user.id)
    await show_root(call.message, call.from_user.id)
    await call.answer('Фильтры оповещений удалены!')

# Возврат из меню: confirm_delete
@dp.callback_query_handler(text='back', state=Menu.confirm_delete)
async def return_from_confirm_delete(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_root(call.message, call.from_user.id)

# Переход в состояние: info
@dp.callback_query_handler(text='info', state=Menu.root)
async def info(call: CallbackQuery, state: FSMContext):
    await call.answer()

    settings = database.get_settings(call.from_user.id) or {}

    msg = 'Отправка оповещений через Telegram '
    if settings.get('active'):
        msg += '<b>активирована</b>.'
    else:
        msg += '<b>отключена</b>.'

    msg += '\nТекущий e-mail: '
    if settings.get('email'):
        msg += f'<b>{settings["email"]}</b>.'
    else:
        msg += '<b>не задан</b>.'

    msg += '\nОтправка оповещений на e-mail '
    if settings.get('email_active'):
        msg += '<b>активирована</b>.'
    else:
        msg += '<b>отключена</b>.'

    for host in fl_parser.HOSTS:
        msg += '\n\n\n<b>Настройки фильтров для сайта '
        msg += f'{fl_parser.host_to_hashtag(host)}</b>.'

        job_filters = database.get_filters(user_id=call.from_user.id,
                                           host=host, query='keywords') or []
        msg += f'\n\n{EMO_KEY} Поиск по ключевым словам:\n'
        if len(job_filters) > 0:
            msg += ('<b>' + ', '.join(job_filters[0]['keywords'].split(','))
                    + '</b>.')
        else:
            msg += '<b>не настроен</b>.'

        job_filters = database.get_filters(user_id=call.from_user.id,
                                           host=host, query='categories') or []
        msg += f'\n\n{EMO_CLIPBOARD} Поиск по категориям:\n'
        if len(job_filters) > 0:
            titles = fl_parser.get_all_titles(host)
            cat_ids = (job_filters[0]['categories']
                       + job_filters[0]['subcategories'])
            msg += '<b>'
            msg += ', '.join([f'"{titles[cat_id]}"' for cat_id in cat_ids])
            msg += '</b>.'
        else:
            msg += '<b>не настроен</b>.'

    await Menu.info.set()
    await call.message.edit_text(text=msg, reply_markup=menu.get_back(),
                                 parse_mode=ParseMode.HTML)

# Возврат из состояния: info
@dp.callback_query_handler(text='back', state=Menu.info)
async def return_from_info(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_root(call.message, call.from_user.id)

# Отобразить меню: select_filter_type
async def show_select_filter_type(message: Message, user_id: str, host: str,
                                  info_text='', edit_message=True):
    await Menu.select_filter_type.set()
    message_func = await _get_message_func(message, edit_message)
    await message_func(
        text=f'{info_text}{EMO_POINT_RIGHT} Укажите <b>тип фильтра</b> '
              'уведомлений для проектов:',
        reply_markup=menu.get_select_filter_type(user_id=user_id, host=host),
        parse_mode=ParseMode.HTML)

# Переход в меню: select_filter_type
@dp.callback_query_handler(lambda call: call.data != 'back',
                           state=Menu.select_host)
async def menu_select_filter_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    host = call.data
    await state.update_data(host=host)
    await show_select_filter_type(call.message, call.from_user.id, host)

# Возврат из меню: select_host
@dp.callback_query_handler(text='back', state=Menu.select_host)
async def return_from_select_host(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_root(call.message, call.from_user.id)

# Получить параметр host. При отказе вернуться в меню select_host
async def _get_host(message: Message, state: FSMContext, edit_message=True):
    host = dict(await state.get_data()).get('host')
    if host:
        return host
    else:
        await show_select_host(message, edit_message=edit_message)
        return False

# Отобразить меню: select_category
async def show_select_category(message: Message, user_id: str, host: str,
                               info_text='', edit_message=True):
    await Menu.select_category.set()
    message_func = await _get_message_func(message, edit_message)
    await message_func(
        text=f'{info_text}{EMO_POINT_RIGHT} Выберите <b>категорию</b> '
              'проектов для фильтра уведомлений:',
        reply_markup=menu.get_select_category(user_id=user_id, host=host),
        parse_mode=ParseMode.HTML)

# Переход в меню select_category или состояние input_keywords
@dp.callback_query_handler(lambda call: call.data != 'back',
                           state=Menu.select_filter_type)
async def menu_select_category(call: CallbackQuery, state: FSMContext):
    await call.answer()

    host = await _get_host(call.message, state)
    if not host:
        return

    if call.data == 'keywords':
        job_filters = database.get_filters(user_id=call.from_user.id,
                                           host=host, query='keywords') or []
        if len(job_filters) > 0:
            msg = ('Текущий список ключевых слов: <b>' +
                   ', '.join(job_filters[0]['keywords'].split(',')) + '</b>.')
        else:
            msg = 'Текущий список ключевых слов <b>пуст</b>.'

        msg += ('\n\nВведите <b>ключевые слова</b> для поиска '
                '(через запятую без пробелов):')

        await Menu.input_keywords.set()
        await call.message.edit_text(text=msg, reply_markup=menu.get_back(),
                                     parse_mode=ParseMode.HTML)
    else:
        await show_select_category(call.message, call.from_user.id, host)

# Действие: сохранение ключевых слов
@dp.message_handler(regexp=KEYWORDS_RE, state=Menu.input_keywords)
async def input_keywords(message: Message, state: FSMContext):
    host = await _get_host(message, state, edit_message=False)
    if not host:
        return

    job_filters = database.get_filters(user_id=message.from_user.id,
                                       host=host, query='keywords') or []
    if len(job_filters) > 0:
        last_job_url = job_filters[0]['last_job_url']
    else:
        last_job_url = ''

    database.save_filter(user_id=message.from_user.id, host=host,
                         keywords=message.text.lower(),
                         last_job_url=last_job_url)

    await show_select_filter_type(
        message, message.from_user.id, host,
        info_text=f'{EMO_INFORMATION} <i>Ключевые слова выбраны!</i>\n\n',
        edit_message=False)

# Действие: повторный запрос ключевых слов
@dp.message_handler(state=Menu.input_keywords)
async def input_keywords_error(message: Message, state: FSMContext):
    await message.answer(
        f'{EMO_NO_ENTRY} <i>Неправильный формат запроса по ключевым словам!'
        '\nКлючевые слова следует вводить через запятую без пробелов. \n'
        'Длина ключевого слова от 3 до 16 символов (букв, цифр и символа "_").'
        '\nКоличество ключевых слов - от 1 до 16.</i>'
        '\n\nПовторите ввод:',
        reply_markup=menu.get_back(), parse_mode=ParseMode.HTML)

# Возврат в меню: select_filter_type
async def back_to_select_filter_type(call: CallbackQuery, state: FSMContext):
    host = await _get_host(call.message, state)
    if not host:
        return

    await show_select_filter_type(call.message, call.from_user.id, host)

# Возврат из состояния: input_keywords
@dp.callback_query_handler(text='back', state=Menu.input_keywords)
async def return_from_input_keywords(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await back_to_select_filter_type(call, state)

# Возврат из меню: select_filter_type
@dp.callback_query_handler(text='back', state=Menu.select_filter_type)
async def return_from_select_host(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_select_host(call.message)

# Отобразить меню: select_subcategory
async def show_select_subcategory(
        message: Message, user_id: str, host: str, category_id: str,
        info_text='', edit_message=True):
    await Menu.select_subcategory.set()
    message_func = await _get_message_func(message, edit_message)
    await message_func(
        text=f'{info_text}{EMO_POINT_RIGHT} Выберите <b>подкатегории</b> '
              'проектов для фильтра уведомлений:',
        reply_markup=menu.get_select_subcategory(
            user_id=user_id, host=host, category_id=category_id),
        parse_mode=ParseMode.HTML)

# Переход в меню: select_subcategory
@dp.callback_query_handler(lambda call: call.data != 'back',
                           state=Menu.select_category)
async def menu_select_subcategory(call: CallbackQuery, state: FSMContext):
    await call.answer()

    host = await _get_host(call.message, state)
    if not host:
        return

    category_id = call.data
    await state.update_data(category_id=category_id)
    await show_select_subcategory(
        call.message, call.from_user.id, host, category_id)

# Возврат из меню: select_category
@dp.callback_query_handler(text='back', state=Menu.select_category)
async def return_from_select_category(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await back_to_select_filter_type(call, state)

# Получить параметр category_id. При отказе вернуться в меню select_category
async def _get_category_id(call: CallbackQuery, state: FSMContext, host: str):
    category_id = dict(await state.get_data()).get('category_id')
    if category_id:
        return category_id
    else:
        await show_select_category(call.message, call.from_user.id, host)
        return False

# Действие: выбор/отмена выбора подкатегорий
@dp.callback_query_handler(lambda call: call.data != 'back',
                           state=Menu.select_subcategory)
async def add_subcategory(call: CallbackQuery, state: FSMContext):
    await call.answer()

    host = await _get_host(call.message, state)
    if not host:
        return

    category_id = await _get_category_id(call, state, host)
    if not category_id:
        return

    job_filters = database.get_filters(user_id=call.from_user.id,
                                       host=host,
                                       query='categories') or []
    if len(job_filters) > 0:
        job_filter = job_filters[0]
    else:
        job_filter = {
            'categories': [],
            'subcategories': [],
            'last_job_url': '',
        }

    modified = False
    if call.data.isdigit():
        if category_id in job_filter['categories']:
            job_filter['categories'].remove(category_id)

            # Если ранее была выбрана вся категория целиком, то список
            # подкатегорий заведомо пуст, и его надо построить заново
            job_filter['subcategories'] += fl_parser.get_cat_ids(
                fl_parser.get_subcatlist(host, category_id))

            job_filter['subcategories'].remove(call.data)
        else:
            if call.data in job_filter['subcategories']:
                job_filter['subcategories'].remove(call.data)
            else:
                job_filter['subcategories'].append(call.data)

        modified = True
    elif call.data == 'everything':
        if category_id not in job_filter['categories']:
            job_filter['categories'].append(category_id)
            modified = True
    elif call.data == 'nothing':
        if category_id in job_filter['categories']:
            job_filter['categories'].remove(category_id)
            modified = True
        else:
            for subcat in fl_parser.get_subcatlist(host, category_id):
                if subcat['id'] in job_filter['subcategories']:
                   job_filter['subcategories'].remove(subcat['id'])
                   modified = True

    if modified:
        job_filter['categories'], job_filter['subcategories'] = (
            fl_parser.assemble_catlist(host, job_filter['categories'],
                                       job_filter['subcategories']))

        if job_filter['categories'] or job_filter['subcategories']:
            database.save_filter(user_id=call.from_user.id, host=host,
                                 categories=job_filter['categories'],
                                 subcategories=job_filter['subcategories'],
                                 last_job_url=job_filter['last_job_url'])
        else:
            database.delete_filters(user_id=call.from_user.id, host=host,
                                    query='categories')

        await call.message.edit_reply_markup(
            reply_markup=menu.get_select_subcategory(user_id=call.from_user.id,
                                                     host=host,
                                                     category_id=category_id))

# Возврат из меню: select_subcategory
@dp.callback_query_handler(text='back', state=Menu.select_subcategory)
async def return_from_select_category(call: CallbackQuery, state: FSMContext):
    await call.answer()

    host = await _get_host(call.message, state)
    if not host:
        return

    await show_select_category(call.message, call.from_user.id, host)

# Обработчик для всех не предусмотренных команд и сообщений
@dp.message_handler(content_types=types.ContentTypes.ANY, state='*')
async def unknown_command(message: Message, state: FSMContext):
    await message.answer('Введите команду /start для вызова меню.')

# Обработчик некорректного callback-запроса
@dp.callback_query_handler(state='*')
async def error(call: CallbackQuery, state: FSMContext):
    await call.message.answer('Введите команду /start для перезапуска бота.')
    await call.answer('При попытке выполнить операцию произошёл сбой!')

if __name__ == '__main__':
    loop.create_task(notify_users_task(bot))
    executor.start_polling(dp, skip_updates=True)

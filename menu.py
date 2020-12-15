"""Данный модуль предназначен для конструирования статических и динамических
инлайн-меню, используемых в диалогах с ботом.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from emoticons import *
import fl_parser
import database

# Начальное (корневое) меню
def get_root(user_id: str) -> InlineKeyboardMarkup:
    settings = database.get_settings(user_id) or {}

    markup = InlineKeyboardMarkup()

    if settings.get('active'):
        markup.row(InlineKeyboardButton(
            text=f'{EMO_BELL} Отключить отправку оповещений',
            callback_data='disable'))
    else:
        markup.row(InlineKeyboardButton(
            text=f'{EMO_NO_BELL} Активировать отправку оповещений',
            callback_data='enable'))

    markup.row(InlineKeyboardButton(
        text=f'{EMO_MEMO} Добавить фильтры оповещений',
        callback_data='select_host'))

    if settings.get('email'):
        markup.row(InlineKeyboardButton(
            text=f'{EMO_EMAIL} Изменить e-mail для оповещений',
            callback_data='input_email'))
    else:
        markup.row(InlineKeyboardButton(
            text=f'{EMO_EMAIL} Ввести e-mail для оповещений',
            callback_data='input_email'))

    if settings.get('email_active'):
        markup.row(InlineKeyboardButton(
            text=f'{EMO_BELL} Отключить оповещения по e-mail',
            callback_data='email_disable'))
    else:
        markup.row(InlineKeyboardButton(
            text=f'{EMO_NO_BELL} Активировать оповещения по e-mail',
            callback_data='email_enable'))

    markup.row(InlineKeyboardButton(
        text=f'{EMO_CROSS_MARK} Удалить все фильтры оповещений',
        callback_data='confirm_delete'))

    markup.row(InlineKeyboardButton(
        text=f'{EMO_INFORMATION} Информация о настройках',
        callback_data='info'))

    return markup

# Кнопка 'Возврат' (меню с единственных пунктом)
def get_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f'{EMO_REWIND} Возврат',
                                     callback_data='back'),
            ],
        ]
    )

# Меню подтверждения очистки всех оповещений
def get_confirm_delete() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f'{EMO_CROSS_MARK} Подтвердить удаление оповещений',
                    callback_data='clear'),
            ],
            [
                InlineKeyboardButton(text=f'{EMO_REWIND} Отменить операцию',
                                     callback_data='back'),
            ],
        ]
    )

# Меню выбора сайта биржи фриланса
def get_select_host() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f'{EMO_RUSSIA} Заказы на FL.ru',
                                     callback_data=fl_parser.HOST_FL_RU),
            ],
            [
                InlineKeyboardButton(
                    text=f'{EMO_UKRAINE} Заказы на Freelance.ua',
                    callback_data=fl_parser.HOST_FL_UA),
            ],
            [
                InlineKeyboardButton(text=f'{EMO_REWIND} Возврат',
                                     callback_data='back'),
            ],
        ]
    )

# Меню выбора типа фильтра проектов (ключевые слова или категории)
def get_select_filter_type(user_id: str, host: str) -> InlineKeyboardMarkup:
    sel_cat = sel_kw = ''
    job_filters = database.get_filters(user_id=user_id, host=host) or []
    for job_filter in job_filters:
        if job_filter.get('keywords'):
            sel_kw = f'{EMO_CHECK_MARK} '
        else:
            sel_cat = f'{EMO_CHECK_MARK} '

    sel_cat = sel_cat or f'{EMO_MEMO} '
    sel_kw = sel_kw or f'{EMO_KEY} '

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f'{sel_cat}Выбор категорий',
                                     callback_data='categories'),
            ],
            [
                InlineKeyboardButton(text=f'{sel_kw}Выбор ключевых слов',
                                     callback_data='keywords'),
            ],
            [
                InlineKeyboardButton(text=f'{EMO_REWIND} Возврат',
                                     callback_data='back'),
            ],
        ]
    )

# Получить категории и подкатегории соответствующего фильтра проектов
def _get_cat_filter(user_id: str, host: str) -> tuple:
    job_filters = database.get_filters(user_id=user_id, host=host,
                                       query='categories') or []
    if len(job_filters) > 0:
        categories = job_filters[0].get('categories', [])
        subcategories = job_filters[0].get('subcategories', [])
    else:
        categories = []
        subcategories = []

    return (categories, subcategories)

# Меню выбора категории проектов для фильтрации
def get_select_category(user_id: str, host: str) -> InlineKeyboardMarkup:
    categories, subcategories = _get_cat_filter(user_id=user_id, host=host)

    markup = InlineKeyboardMarkup()

    # Выстраиваем категории в два вертикальных ряда
    catlist = fl_parser.get_catlist(host)
    for index, category in enumerate(catlist):
        if index % 2 != 0:
            continue

        row = []
        cats = [category]
        if index < len(catlist) - 1:
            cats.append(catlist[index + 1])

        for cat in cats:
            title = cat['title']

            if cat['id'] in categories:
                title = f'{EMO_CHECK_MARK}{EMO_CHECK_MARK} {title}'
            else:
                for subcat_id in subcategories:
                    if fl_parser.is_category_child(host, cat['id'], subcat_id):
                        title = f'{EMO_CHECK_MARK} {title}'
                        break

            row.append(InlineKeyboardButton(text=title,
                                            callback_data=cat['id']))
        markup.row(*row)

    markup.row(InlineKeyboardButton(text=f'{EMO_REWIND} Возврат',
                                    callback_data='back'))

    return markup

# Меню выбора подкатегорий проектов для фильтрации
def get_select_subcategory(user_id: str, host: str,
                           category_id: str) -> InlineKeyboardMarkup:
    categories, subcategories = _get_cat_filter(user_id=user_id, host=host)

    if category_id in categories:
        selected = True
    else:
        selected = False

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(
        text=f'{EMO_CHECK_MARK}{EMO_CHECK_MARK} Выбрать всё',
        callback_data='everything'))

    # Выстраиваем подкатегории в два вертикальных ряда
    subcatlist = fl_parser.get_subcatlist(host, category_id)
    for index, subcategory in enumerate(subcatlist):
        if index % 2 != 0:
            continue

        row = []
        subcats = [subcategory]
        if index < len(subcatlist) - 1:
            subcats.append(subcatlist[index + 1])

        for subcat in subcats:
            title = subcat['title']

            if selected or (subcat['id'] in subcategories):
                title = f'{EMO_CHECK_MARK} {title}'

            row.append(InlineKeyboardButton(text=title,
                                            callback_data=subcat['id']))
        markup.row(*row)

    markup.row(InlineKeyboardButton(text=f'{EMO_CROSS_MARK} Отменить выбор',
                                    callback_data='nothing'))
    markup.row(InlineKeyboardButton(text=f'{EMO_REWIND} Возврат',
                                    callback_data='back'))

    return markup

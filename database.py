"""Модуль, обеспечивающий высокоуровневое взаимодействие с базой данных, где
хранятся пользовательские настройки и фильтры проектов.
"""
import logging
import os
import sqlite3

from config import DB_NAME

SQL_CREATE_DB = """\
CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 0,
    email TEXT DEFAULT '',
    email_active INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_filter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    host TEXT DEFAULT '',
    categories TEXT DEFAULT '',
    subcategories TEXT DEFAULT '',
    keywords TEXT DEFAULT '',
    last_job_url TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_user_id
ON job_filter (user_id);
"""

SQL_USER_INSERT = """\
INSERT INTO user (user_id, active, email, email_active)
VALUES (:user_id, :active, :email, :email_active);
"""

SQL_USER_UPDATE = """\
UPDATE user
SET active = :active, email = :email, email_active = :email_active
WHERE user_id = :user_id;
"""

SQL_USER_SELECT = """\
SELECT active, email, email_active
FROM user
WHERE user_id = :user_id;
"""

SQL_USER_SELECT_ALL = """\
SELECT user_id, active, email, email_active
FROM user;
"""

SQL_USER_DELETE = """\
DELETE FROM user
WHERE user_id = :user_id;
"""

SQL_FILTER_INSERT = """\
INSERT INTO job_filter (user_id, host, categories, subcategories,
                        keywords, last_job_url)
VALUES (:user_id, :host, :categories, :subcategories,
        :keywords, :last_job_url);
"""

SQL_FILTER_UPDATE_KW = """\
UPDATE job_filter
SET keywords = :keywords, categories = '', subcategories = '',
    last_job_url = :last_job_url
WHERE user_id = :user_id AND host = :host AND keywords <> '';
"""

SQL_FILTER_UPDATE_CATS = """\
UPDATE job_filter
SET categories = :categories, subcategories = :subcategories,
    last_job_url = :last_job_url
WHERE user_id = :user_id AND host = :host AND keywords = '';
"""

SQL_FILTER_SELECT = """\
SELECT host, categories, subcategories, keywords, last_job_url
FROM job_filter
WHERE user_id = :user_id;
"""

SQL_FILTER_SELECT_HOST = """\
SELECT categories, subcategories, keywords, last_job_url
FROM job_filter
WHERE user_id = :user_id AND host = :host;
"""

SQL_FILTER_SELECT_KW = """\
SELECT keywords, last_job_url
FROM job_filter
WHERE user_id = :user_id AND host = :host AND keywords <> '';
"""

SQL_FILTER_SELECT_CATS = """\
SELECT categories, subcategories, last_job_url
FROM job_filter
WHERE user_id = :user_id AND host = :host AND keywords = '';
"""

SQL_FILTER_DELETE_KW = """\
DELETE FROM job_filter
WHERE user_id = :user_id AND host = :host AND keywords <> '';
"""

SQL_FILTER_DELETE_CATS = """\
DELETE FROM job_filter
WHERE user_id = :user_id AND host = :host AND keywords = '';
"""

SQL_FILTER_DELETE = """\
DELETE FROM job_filter
WHERE user_id = :user_id;
"""

# Специальная функция для формирования словаря вместо списка в sql-запросах
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# Создание базы данных (если не существует)
def create_database() -> bool:
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        with con:
            cur.executescript(SQL_CREATE_DB)
    except (sqlite3.DatabaseError, OSError):
        logging.error('Не удалось создать базу данных.')
        result = False
    else:
        result = True

    cur.close()
    con.close()
    return result

# Удаление базы данных
def remove_database() -> bool:
    try:
        os.remove(DB_NAME)
    except OSError:
        logging.error('Не удалось удалить базу данных.')
        return False
    else:
        return True

# Сохранение настроек пользователя
def save_settings(user_id: str, active=None,
                  email=None, email_active=None) -> bool:
    """Входные параметры:
    user_id: str - строковый идентификатор пользователя Telegram;
    active: bool - флаг рассылки уведомлений в Telegram;
    email: str - e-mail пользователя для рассылки уведомлений;
    email_active: bool - флаг рассылки уведомлений по e-mail.
    """
    settings = get_settings(user_id) or {}

    if settings:
        sql = SQL_USER_UPDATE
    else:
        sql = SQL_USER_INSERT

    params = {'user_id': int(user_id)}

    if active is None:
        params['active'] = settings.get('active', 0)
    else:
        params['active'] = int(active)

    if email is None:
        params['email'] = settings.get('email', '')
    else:
        params['email'] = email

    if email_active is None:
        params['email_active'] = settings.get('email_active', 0)
    else:
        params['email_active'] = int(email_active)

    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        with con:
            cur.execute(sql, params)
    except sqlite3.DatabaseError:
        logging.error('Не удалось сохранить настройки пользователя.')
        result = False
    else:
        result = True

    cur.close()
    con.close()
    return result

# Прочитать из базы настройки всех пользователей
def get_settings_all() -> []:
    """Возвращаемое значение:
    [
        dict('user_id': str,
             'active': bool,
             'email': str,
             'email_active': bool),
        ... ... ...
    ]

    Смысловые значения ключей - см. save_settings()
    """
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        cur.execute(SQL_USER_SELECT_ALL)
        rows = cur.fetchall()
    except sqlite3.DatabaseError:
        logging.error('Не удалось прочитать данные о пользователях.')
        result = False
    else:
        result = []
        for row in rows:
            result.append({
                'user_id': str(row[0]),
                'active': bool(row[1]),
                'email': row[2],
                'email_active': bool(row[3]),
            })

    cur.close()
    con.close()
    return result

# Получить настройки заданного пользователя
def get_settings(user_id: str) -> dict:
    """Входной параметр:
    user_id: str - строковый идентификатор пользователя Telegram.

    Возвращаемое значение:
    dict('user_id': str,
         'active': bool,
         'email': str,
         'email_active': bool)

    Смысловые значения ключей - см. save_settings().
    """
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        cur.execute(SQL_USER_SELECT, {'user_id': int(user_id)})
        row = cur.fetchone()
    except sqlite3.DatabaseError:
        logging.error('Не удалось прочитать настройки пользователя.')
        result = False
    else:
        if row:
            result = {
                'user_id': user_id,
                'active': bool(row[0]),
                'email': row[1],
                'email_active': bool(row[2]),
            }
        else:
            result = {}

    cur.close()
    con.close()
    return result

# Сохранить фильтр проектов для уведомлений
def save_filter(user_id: str, host: str, categories=[], subcategories=[],
                keywords='', last_job_url='') -> bool:
    """Входные параметры:
    user_id: str - строковый идентификатор пользователя Telegram;
    host: str - адрес сайта биржи фриланса;
    categories: list - список строковых идентификаторов категорий проектов;
    subcategories: list - список строковых идентификаторов подкатегорий
    проектов;
    keywords: str - ключевые слова для поиска (через запятую без пробелов);
    last_job_url: str - url-адрес страницы последнего (самого "свежего")
    проекта в уведомлении.

    Если задан параметр keywords, то параметры categories и subcategories
    игнорируются, поскольку будет сохранён фильтр по ключевым словам. Иначе
    сохраняется фильтр по категориям (где нет ключевых слов).

    Замечание: для каждой категории из списка categories подразумевается, что
    все её подкатегории тоже выбраны. Поэтому не следует указывать дочерние
    подкатегории в списке subcategories.
    """
    params = {
        'user_id': int(user_id),
        'host': host,
        'keywords': keywords,
        'last_job_url': last_job_url,
        'categories': '',
        'subcategories': '',
    }

    if keywords:
        query = 'keywords'
    else:
        query = 'categories'

        if categories:
            params['categories'] = ','.join(categories)

        if subcategories:
            params['subcategories'] = ','.join(subcategories)

    if get_filters(user_id, host=host, query=query):
        if keywords:
            sql = SQL_FILTER_UPDATE_KW
        else:
            sql = SQL_FILTER_UPDATE_CATS
    else:
        sql = SQL_FILTER_INSERT

    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        with con:
            cur.execute(sql, params)
    except sqlite3.DatabaseError:
        logging.error('Не удалось сохранить фильтр для уведомлений.')
        result = False
    else:
        result = True

    cur.close()
    con.close()
    return result

# Прочитать из базы фильтры проектов для уведомлений
def get_filters(user_id: str, host='', query=None) -> []:
    """Входные параметры:
    user_id: str - строковый идентификатор пользователя Telegram;
    host: str - адрес сайта биржи фриланса;
    query: str - тип фильтра, одно из значений: None (возвращает все фильтры),
    'keywords' (по ключевым словам) или 'categories' (по категориям).

    Возвращаемое значение:
    [
        dict('user_id': str,
             'host': str,
             'categories': list,
             'subcategories': list,
             'keywords': str,
             'last_job_url': str),
        ... ... ...
    ]

    Смысловые значения ключей - см. save_filter().
    """
    params = {
        'user_id': int(user_id),
        'host': host,
    }

    if host:
        if query == 'keywords':
            sql = SQL_FILTER_SELECT_KW
        elif query == 'categories':
            sql = SQL_FILTER_SELECT_CATS
        else:
            sql = SQL_FILTER_SELECT_HOST
    else:
        sql = SQL_FILTER_SELECT

    con = sqlite3.connect(DB_NAME)
    con.row_factory = dict_factory
    cur = con.cursor()

    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
    except sqlite3.DatabaseError:
        logging.error('Не удалось прочитать фильтр для уведомлений.')
        result = False
    else:
        result = []
        for row in rows:
            job_filter = {
                'user_id': user_id,
                'host': row.get('host', host),
                'categories': [],
                'subcategories': [],
                'last_job_url': row.get('last_job_url', ''),
            }

            job_filter['keywords'] = row.get('keywords', '')

            categories = row.get('categories')
            if categories:
                job_filter['categories'] = categories.split(',')

            subcategories = row.get('subcategories')
            if subcategories:
                job_filter['subcategories'] = subcategories.split(',')

            result.append(job_filter)

    cur.close()
    con.close()
    return result

# Удалить фильтры проектов для уведомлений
def delete_filters(user_id: str, host=None, query=None) -> bool:
    """Входные параметры:
    user_id: str - строковый идентификатор пользователя Telegram;
    host: str - адрес сайта биржи фриланса; если не указан, то будут удалены
    все фильтры для user_id;
    query: str - тип удаляемого фильтра, одно из значений: None (удаляет все
    фильтры для user_id), 'keywords' (удаляет фильтр по ключевым словам) или
    'categories'(удаляет фильтр по категориям); данный параметр актуален
    только при заданном host.
    """
    params = {'user_id': int(user_id)}

    sql = SQL_FILTER_DELETE

    if host:
        params['host'] = host

        if query == 'keywords':
            sql = SQL_FILTER_DELETE_KW
        elif query == 'categories':
            sql = SQL_FILTER_DELETE_CATS

    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        with con:
            cur.execute(sql, params)
    except sqlite3.DatabaseError:
        logging.error('Не удалось удалить фильтры уведомлений.')
        result = False
    else:
        result = True

    cur.close()
    con.close()
    return result

# Удалить настройки и все фильтры уведомлений для заданного пользователя
def delete_settings(user_id: str) -> bool:
    """Входной параметр:
    user_id: str - строковый идентификатор пользователя Telegram.
    """
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        with con:
            cur.execute(SQL_FILTER_DELETE, {'user_id': int(user_id)})
            cur.execute(SQL_USER_DELETE, {'user_id': int(user_id)})
    except sqlite3.DatabaseError:
        logging.error('Не удалось удалить настройки пользователя.')
        result = False
    else:
        result = True

    cur.close()
    con.close()
    return result

# Произвести дефрагментацию базы данных
def vacuum() -> bool:
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    try:
        with con:
            cur.executescript('VACUUM;')
    except sqlite3.DatabaseError:
        logging.error('Не удалось произвести дефрагментацию базы данных.')
        result = False
    else:
        result = True

    cur.close()
    con.close()
    return result

# Создание базы данных (при необходимости) и её дефрагментация
def init():
    if create_database():
        logging.info('БД успешно создана или уже существует.')

    if vacuum():
        logging.info('Дефрагментация БД выполнена.')

"""Данный модуль реализует парсинг (добычу данных) сайтов бирж фриланса с целью
получения новых проектов на основе поисковых фильтров пользователя.
"""
import logging
import time
import re
from html import unescape

import requests
from bs4 import BeautifulSoup

# Время ожидания ответа от веб-сервера (секунды)
TIMEOUT = 5

# Число попыток выполнить http-запрос при возникновении сбоя
MAX_RETRIES = 3

# Опциональная задержка после выполнения http-запроса (секунды)
SLEEP_TIME = 1

# Заголовки http-запроса
HEADERS = {
    'user-agent': ('Mozilla/5.0 (Windows NT 6.1; rv:82.0) Gecko/20100101 '
                   'Firefox/82.0'),
    'accept': '*/*',
}

"""Далее следует блок URL-адресов сайтов бирж фриланса.
"""
URL_JOBS_FL_RU = 'https://www.fl.ru/projects/'
HOST_FL_RU = 'https://www.fl.ru'
URL_JOBS_FL_UA = 'https://freelance.ua/orders/'
HOST_FL_UA = 'https://freelance.ua'
HOSTS = [HOST_FL_RU, HOST_FL_UA]

"""Структура категорий для проектов биржи фриланса в общем случае имеет вид:
[
    {
        'id': str - уникальный идентификатор категории;
        'title': str - заголовок категории;
        'children': list - список подкатегорий;
    },
    ... ... ...
]

Каждая подкатегория представляет собой словарь следующей структуры:
{
    'id': str - уникальный идентификатор подкатегории;
    'title': str - заголовок подкатегории;
    'keyword': str - ключевое слово для подкатегории (опционально).
}
"""
categories_fl_ru = [
    {'id': '2', 'title': 'Разработка сайтов', 'children': []},
    {'id': '8', 'title': 'Тексты', 'children': []},
    {'id': '3', 'title': 'Дизайн и Арт', 'children': []},
    {'id': '5', 'title': 'Программирование', 'children': []},
    {'id': '11', 'title': 'Аудио/Видео', 'children': []},
    {'id': '12', 'title': 'Реклама и Маркетинг', 'children': []},
    {'id': '13', 'title': 'Аутсорсинг и консалтинг', 'children': []},
    {'id': '16', 'title': 'Разработка игр', 'children': []},
    {'id': '7', 'title': 'Переводы', 'children': []},
    {'id': '19', 'title': 'Анимация и флеш', 'children': []},
    {'id': '10', 'title': 'Фотография', 'children': []},
    {'id': '9', 'title': '3D Графика', 'children': []},
    {'id': '20', 'title': 'Инжиниринг', 'children': []},
    {'id': '6', 'title': 'Оптимизация (SEO)', 'children': []},
    {'id': '22', 'title': 'Обучение и консультации', 'children': []},
    {'id': '14', 'title': 'Архитектура/Интерьер', 'children': []},
    {'id': '17', 'title': 'Полиграфия', 'children': []},
    {'id': '1', 'title': 'Менеджмент', 'children': []},
    {'id': '23', 'title': 'Мобильные приложения', 'children': []},
    {'id': '24', 'title': 'Сети и инфосистемы', 'children': []},
]

categories_fl_ua = []

CATEGORY_RE = re.compile(r'filter_specs\[(\d+)\]=\[(\[[^;]+\])\]')
SUBCAT_RE = re.compile(r'\[([^\[\]]+)\]')
PRICE_RE = re.compile(
    r'<script.+<div class="b-post__price.+>(.+)</div>.+</script>')
DESCRIPTION_RE = re.compile(
    r'<script.+<div class="b-post__txt[^<]+>([^<]+)</div>.+</script>')

# Преобразовать URL сайта в хештег для Telegram
def host_to_hashtag(host: str) -> str:
    return ('#' + host.replace('https://', '').replace('http://', '').
            replace('www.', '').replace('.', '_'))

# Заменить все пробельные символы и их повторы на обычный пробел
def clean_text(text: str) -> str:
    return ' '.join(text.split())

# Удалить все пробельные символы из текста
def remove_spaces(text: str) -> str:
    return ''.join(text.split())

# Получить текстовый контент web-страницы
def get_html(url: str, params: dict=None, data: dict=None,
             delay: bool=False) -> str:
    """Входные параметры:
    url: str - полный адрес web-страницы;
    params: dict - словарь с параметрами для GET-запроса;
    data: dict - словарь с параметрами для POST-запроса;
    delay: bool - флаг задержки: если установлен в True, то после выполнения
    запроса будет сделана задержка в SLEEP_TIME секунд.

    Замечание: если параметр data имеет непустое значение, то будет выполнен
    POST-запрос. В противном случае выполнится запрос GET.
    """
    for attempt in range(0, MAX_RETRIES):
        try:
            if data:
                r = requests.post(url, headers=HEADERS, timeout=TIMEOUT,
                                  data=data)
            else:
                r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                                 params=params)
        except requests.exceptions.RequestException:
            time.sleep(SLEEP_TIME)
        else:
            if delay:
                time.sleep(SLEEP_TIME)
            break

    if not r:
        logging.error('Не удалось выполнить http-запрос.')
        return False

    if r.status_code != requests.codes.ok:
        logging.error(f'Ошибка {r.status_code} при обращении к web-странице.')
        return False

    return r.text

"""Назначение двух последующих функций в том, чтобы преодолеть проблему
неуникальности идентификатора подкатегории самого по себе. Эта особенность
характерна как для FL.ru, так и для Freelance.ua.
"""

# Скомбинировать идентификаторы категории и подкатегории в один уникальный
# строково-цифровой идентификатор
def combine_cat_ids(category_id: str, subcategory_id: str) -> str:
    return ('0' * (4 - len(category_id)) + category_id
            + '0' * (4 - len(subcategory_id)) + subcategory_id)

# Распаковать из ранее скомбинированного строково-цифрового идентификатора
# два других: идентификаторы категории и подкатегории
def split_cat_ids(combined_ids: str) -> dict:
    return {
        'category_id': str(int(combined_ids[:4])),
        'subcategory_id': str(int(combined_ids[4:]))
    }

# Построить структуру категорий (и подкатегорий) для сайта FL.ru, записав её
# в глобальную переменную categories_fl_ru
def build_catlist_fl_ru() -> bool:
    html = get_html(URL_JOBS_FL_RU)

    if not html:
        logging.error(f'Нет доступа к странице проектов {URL_JOBS_FL_RU}.')
        return False

    search_results = re.findall(CATEGORY_RE, html)
    for result in search_results:
        for category in categories_fl_ru:
            if category['id'] == result[0]:
                category['children'] = []
                subsearch_results = re.findall(SUBCAT_RE, result[1])
                for subresult in subsearch_results:
                    id_, title = subresult.split(',', 1)
                    id_ = combine_cat_ids(category_id=category['id'],
                                          subcategory_id=id_.strip())
                    category['children'].append({
                        'id': id_,
                        'title': title.replace("'", '').strip()
                    })
                continue

    return True

# Построить структуру категорий (и подкатегорий) для сайта Freelance.ua,
# записав её в глобальную переменную categories_fl_ua
def build_catlist_fl_ua() -> bool:
    html = get_html(URL_JOBS_FL_UA)

    if not html:
        logging.error(f'Нет доступа к странице проектов {URL_JOBS_FL_UA}.')
        return False

    categories_fl_ua.clear()
    soup = BeautifulSoup(html, 'html.parser')

    left_catlist = soup.find(
        'ul', class_='l-left-categories l-inside visible-md visible-lg')
    if left_catlist:
        categories = left_catlist.findChildren('li', recursive=False) or []
        for category in categories:
            new_cat = {
                'id': category.get('data-id', ''),
                'title': '',
                'children': []
            }
            title = category.find('span', class_='j-cat-title')
            if title:
                new_cat['title'] = title.get_text().strip()
            children_ul = category.find('ul') or []
            if children_ul:
                children = children_ul.findChildren('li',
                                                    recursive=False) or []
                for child_item in children:
                    child = child_item.find('span', class_='j-spec')
                    if child:
                        id_ = combine_cat_ids(
                            category_id=child.get('data-cat', ''),
                            subcategory_id=child.get('data-id', ''))

                        new_child = {
                            'id': id_,
                            'title': child.get_text().strip(),
                            'keyword': child.get('data-keyword', ''),
                        }
                        new_cat['children'].append(new_child)

            categories_fl_ua.append(new_cat)

    return True

# Получить список категорий верхнего уровня для сайта FL.ru
def get_catlist_fl_ru() -> list:
    """Возвращаемое значение:
    [{'id': str, 'title': str},...]
    """
    return [{'id': cat['id'], 'title': cat['title']}
            for cat in categories_fl_ru]

# Получить список подкатегорий для заданной категории сайта FL.ru
def get_subcatlist_fl_ru(category_id: str) -> list:
    """Возвращаемое значение:
    [{'id': str, 'title': str},...]
    """
    for category in categories_fl_ru:
        if category['id'] == category_id:
            return [{'id': cat['id'], 'title': cat['title']}
                    for cat in category['children']]
    return []

# Получить список категорий верхнего уровня для сайта Freelance.ua
def get_catlist_fl_ua() -> list:
    """Возвращаемое значение:
    [{'id': str, 'title': str},...]
    """
    return [{'id': cat['id'], 'title': cat['title']}
            for cat in categories_fl_ua]

# Получить список подкатегорий для заданной категории сайта Freelance.ua
def get_subcatlist_fl_ua(category_id: str) -> list:
    """Возвращаемое значение:
    [{'id': str, 'title': str, 'keyword': str},...]
    """
    for category in categories_fl_ua:
        if category['id'] == category_id:
            return [{
                'id': cat['id'],
                'title': cat['title'],
                'keyword': cat['keyword']
                } for cat in category['children']]
    return []

# Получить список категорий верхнего уровня для сайта host
def get_catlist(host: str) -> list:
    if host == HOST_FL_RU:
        return get_catlist_fl_ru()
    elif host == HOST_FL_UA:
        return get_catlist_fl_ua()
    else:
        return False

# Получить список подкатегорий для заданной категории сайта host
def get_subcatlist(host: str, category_id: str) -> list:
    if host == HOST_FL_RU:
        return get_subcatlist_fl_ru(category_id)
    elif host == HOST_FL_UA:
        return get_subcatlist_fl_ua(category_id)
    else:
        return False

# Проверить, является ли подкатегория дочерней для указанной категории
def is_category_child(host: str, category_id: str,
                      subcategory_id: str) -> bool:
    """Входные параметры:
    host: str - адрес сайта биржи фриланса;
    category_id: str - строковый уникальный идентификатор категории верхнего
    уровня;
    subcategory_id: str - строковый уникальный идентификатор подкатегории.

    Возвращаемое значение:
    True - подкатегория является дочерней для указанной категории верхнего
    уровня. False - в противном случае.
    """
    if host == HOST_FL_RU:
        subcatlist = get_subcatlist_fl_ru(category_id)
    elif host == HOST_FL_UA:
        subcatlist = get_subcatlist_fl_ua(category_id)
    else:
        return False

    for cat in subcatlist:
        if cat['id'] == subcategory_id:
            return True

    return False

# Возвратить список всех идентификаторов для указанного списка категорий.
# Структура списка категорий приведена в начале данного модуля
def get_cat_ids(categories: list) -> list:
    return [cat['id'] for cat in categories]

# Возвратить список всех заголовков категорий и подкатегорий для сайта host
def get_all_titles(host: str) -> dict:
    """Возвращаемое значение:
    {
        'category_id_1': 'category_title_1',
        'category_id_2': 'category_title_2',
        ... ... ...
        'category_id_n': 'category_title_n'
    }
    Ключи и значения строковые.
    """
    result = {}

    for cat in get_catlist(host):
        result[cat['id']] = cat['title']
        for subcat in get_subcatlist(host, cat['id']):
            result[subcat['id']] = subcat['title']

    return result

# Скомпоновать подкатегории в одну категорию верхнего уровня
def assemble_catlist(host: str, category_ids: list,
                     subcategory_ids: list) -> tuple:
    """Входные параметры:
    host: str - адрес сайта биржи фриланса;
    category_ids: list - список строковых уникальных идентификаторов категорий
    верхнего уровня;
    subcategory_ids: list - список строковых уникальных идентификаторов
    подкатегорий.

    Возвращаемое значение:
    ([category_id_1, category_id_2,..., category_id_n],
     [subcategory_id_1, subcategory_id_2,..., subcategory_id_n])
    Все значения строковые.

    Подкатегории, скомпоновавшие категорию верхнего уровня, не добавляются в
    новый список подкатегорий.
    """
    cat_ids = category_ids[:]
    subcat_ids = subcategory_ids[:]
    for cat in get_catlist(host):
        # Пропустить категорию, если она уже присутствует в списке category_ids
        if cat['id'] in cat_ids:
            continue

        # Проверить, смогут ли подкатегории из списка subcategory_ids
        # сформировать категорию верхнего уровня
        append = True
        for subcat in get_subcatlist(host, cat['id']):
            if subcat['id'] not in subcat_ids:
                append = False
                break
        if append:
            cat_ids.append(cat['id'])

    # Удаление из списка подкатегорий, сформировавших категорию верхнего уровня
    for cat_id in cat_ids:
        for subcat in get_subcatlist(host, cat_id):
            index = -1
            for i, subcat_id in enumerate(subcat_ids):
                if subcat_id == subcat['id']:
                    index = i
                    break
            if index > -1:
                del subcat_ids[index]

    return (cat_ids, subcat_ids)

# Получить список новых проектов с сайта FL.ru
def get_jobs_fl_ru(category_ids: list=[], subcategory_ids: list=[],
                   keywords: str='') -> list:
    """Входные параметры:
    category_ids: list - список строковых уникальных идентификаторов категорий
    верхнего уровня;
    subcategory_ids: list - список строковых уникальных идентификаторов
    подкатегорий;
    keywords: str - ключевые слова для поиска (через запятую без пробелов).

    Возвращаемое значение:
    [
        {
            'pinned': bool - является ли проект "прикреплённым";
            'title': str - заголовок проекта;
            'url': str - web-адрес страницы проекта;
            'price': str - бюджет проекта;
            'description': str - описание проекта;
        },
        ... ... ...
    ]
    """
    payload = {
        'action': 'postfilter',
        'kind': '5',
    }

    for cat_id in category_ids:
        payload[f'pf_categofy[0][{cat_id}]'] = '1'

    for subcat_id in subcategory_ids:
        # Идентификатор подкатегории сначала необходимо "распаковать"
        subcat_id = split_cat_ids(subcat_id)['subcategory_id']
        payload[f'pf_categofy[1][{subcat_id}]'] = '1'

    if keywords:
        payload['pf_keywords'] = keywords

    html = get_html(URL_JOBS_FL_RU, data=payload)
    if html:
        jobs = []
        soup = BeautifulSoup(html, 'html.parser')
        posts = soup.find_all('div', class_='b-post') or []
        for post in posts:
            job = {}

            if post.find('h2', class_='b-post__pin'):
                job['pinned'] = True

            title = post.find('a', class_='b-post__link')
            if title:
                job['title'] = title.get_text(strip=True)
                job['url'] = HOST_FL_RU + title.get('href', '')

            scripts = post.find_all('script', type='text/javascript')
            if scripts:
                multiscript = '\n'.join([str(script) for script in scripts])

                search_results = re.findall(PRICE_RE, multiscript)
                if search_results:
                    job['price'] = unescape(search_results[0]).strip()

                search_results = re.findall(DESCRIPTION_RE, multiscript)
                if search_results:
                    job['description'] = unescape(search_results[0]).strip()

            jobs.append(job)
        return jobs
    else:
        return []

# Получить строку с ключевыми словами для заданной уникальным идентификатором
# подкатегории (актуально только для Freelance.ua)
def get_keyword(subcategory_id: str) -> str:
    for cat in categories_fl_ua:
        for subcat in cat['children']:
            if subcategory_id == subcat['id']:
                return subcat['keyword']

    return False

# Получить список новых проектов с сайта Freelance.ua
def get_jobs_fl_ua(category_ids: list=[], subcategory_ids: list=[],
                   keywords: str='') -> list:
    """Входные параметры и возвращаемый результат - см. get_jobs_fl_ru().
    """
    params = {
        'page': '1',
        'pc': '1',
    }

    if keywords:
        params['q'] = keywords
    else:
        subcat_ids = subcategory_ids[:]

        for cat_id in category_ids:
            for subcat in get_subcatlist_fl_ua(cat_id):
                subcat_ids.append(subcat['id'])

        subcat_keywords = [get_keyword(subcat_id) for subcat_id in subcat_ids]
        if subcat_keywords:
            params['orders'] = ','.join(subcat_keywords)

    html = get_html(URL_JOBS_FL_UA, params=params)
    if html:
        jobs = []
        soup = BeautifulSoup(html, 'html.parser')
        root = soup.find('ul', class_='l-projectList')
        if root:
            items = root.findChildren('li', recursive=False) or []
            for item in items:
                job = {}

                project_title = item.find('header', class_='l-project-title')
                if project_title:
                    if project_title.find('i', class_='c-icon-fixed'):
                        job['pinned'] = True

                    title_link = project_title.findChild('a', recursive=False)
                    if title_link:
                        job['title'] = title_link.get_text().strip()
                        job['url'] = title_link.get('href', '')

                project_head = item.find('div', class_='l-project-head')
                if project_head:
                    price = project_head.findChild('span', recursive=False)
                    if price:
                        job['price'] = price.get_text().strip()

                article = item.find('article')
                if article:
                    description = article.findChild('p', recursive=False)
                    job['description'] = clean_text(description.get_text())

                jobs.append(job)
        return jobs
    else:
        return []

# Получить список проектов, более новых, чем указанный
def get_recent_jobs(jobs: list, last_job_url: str) -> list:
    """Входные параметры:
    jobs: list - исходный список проектов; структура данного списка повторяет
    возвращаемый результат функции get_jobs_fl_ru();
    last_job_url - адрес web-страницы проекта, после которого (включая и его)
    другие проекты из начального списка добавляться в выходной список не будут.
    остальные параметры те же, что и у get_jobs_fl_ru().

    Возвращаемый результат:
    список проектов, более новых, чем проект с адресом last_job_url; структура
    списка та же, что и возвращаемая get_jobs_fl_ru(). "Прикреплённые" проекты
    игнорируются.
    """
    recent_jobs = []
    for job in jobs:
        if job.get('pinned', False):
            continue
        if job['url'] == last_job_url:
            break
        recent_jobs.append(job)
    return recent_jobs

# Получить список новых проектов с сайта заданной биржи фриланса
def get_jobs(host: str, category_ids: list=[], subcategory_ids: list=[],
             keywords: str='') -> list:
    """Входные параметры:
    host: str - адрес сайта биржи фриланса;
    остальные параметры те же, что и у get_jobs_fl_ru().

    Возвращаемый результат:
    список проектов - аналогичен результату, возвращаемому get_jobs_fl_ru().
    """
    if host == HOST_FL_RU:
        return get_jobs_fl_ru(category_ids, subcategory_ids, keywords)
    elif host == HOST_FL_UA:
        return get_jobs_fl_ua(category_ids, subcategory_ids, keywords)
    else:
        return False

# Динамически построить структуры категорий проектов для бирж фриланса. Это
# необходимо для дальнейшего получения новых проектов с сайтов
def init():
    if build_catlist_fl_ru() and build_catlist_fl_ua():
        logging.info('Структура категорий построена.')

    # Проверка фактической наполненности дерева категорий
    for host in HOSTS:
        catlist = get_catlist(host)
        if catlist:
            for cat in catlist:
                if not get_subcatlist(host, cat['id']):
                    logging.warning(f'Категория проектов сайта {host} '
                                    'не содержит подкатегорий!')
        else:
            logging.warning(f'Список категорий сайта {host} пуст!')

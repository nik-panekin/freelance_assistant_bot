"""В данном модуле хранятся основные (но не все) настройки для бота
и выполняется инициализация подсистемы ведения журнала ошибок (logging).
"""
import os
import logging

from dotenv import load_dotenv

# Имя файла базы данных
DB_NAME = 'settings.db'

# Имя файла журнала ошибок и уведомлений
LOG_NAME = 'bot.log'

# Период проверки обновлений и отправки сообщений (в секундах)
NOTIFY_PERIOD = 60

# Номер порта SMTP для STARTTLS службы GMail
SMTP_PORT = 587

# Сервер, с которого бот будет рассылать сообщения по e-mail
SMTP_SERVER = 'smtp.gmail.com'

# E-mail бота, с которого будет производиться рассылка сообщений
BOT_EMAIL = 'freelance.assistant.bot@gmail.com'

load_dotenv()

# API TOKEN бота (получают у @BotFather). Не рекомендуется хранить в тексте
# исходного кода, поэтому считывается из переменной окружения BOT_TOKEN
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Пароль от e-mail бота. Не рекомендуется хранить в тексте исходного кода,
# поэтому считывается из переменной окружения BOT_PASSWORD
BOT_PASSWORD = os.getenv('BOT_PASSWORD')

"""Далее следует настройка логгирования (журнала ошибок и уведомлений).
"""
logFormatter = logging.Formatter(fmt='[%(asctime)s] %(filename)s:%(lineno)d '
                                     '%(levelname)s - %(message)s',
                                 datefmt='%d.%m.%Y %H:%M:%S')
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.INFO)

fileHandler = logging.FileHandler(LOG_NAME, mode='w')
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

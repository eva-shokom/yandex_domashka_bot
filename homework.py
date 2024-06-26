import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import HttpStatusException


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

RETRY_PERIOD = 600
ONE_WEEK_TIME = 604800
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    token_names = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for name in token_names:
        if not name:
            logger.critical(f'Отсутствует обязательная переменная окружения '
                            f'"{name}". Программа принудительно остановлена.')
            sys.exit()


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение в Telegram успешно отправлено')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(timestamp):
    """
    Делает запрос к эндпоинту API-сервиса.

    В случае успешного запроса возвращает ответ API
    в формате типа данных Python.
    """
    try:
        payload = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logger.error(
                f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен.'
            )
            raise HttpStatusException()
    except requests.RequestException:
        logger.error(
            f'Возникла проблема при запросе к эндпоинту {ENDPOINT}'
        )
        raise HttpStatusException()
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        error_text = 'Ответ не является словарём'
        logger.error(error_text)
        raise TypeError(error_text)
    if 'homeworks' not in response:
        error_text = 'В словаре отсутсвует ключ "homework"'
        logger.error(error_text)
        raise KeyError(error_text)
    if not isinstance(response['homeworks'], list):
        error_text = 'Значение ключа "homework" не является списком'
        logger.error(error_text)
        raise TypeError(error_text)
    if 'current_date' not in response:
        error_text = 'В словаре отсутсвует ключ "current_date"'
        logger.error(error_text)
        raise KeyError(error_text)
    if len(response['homeworks']) == 0:
        logger.error('Список домашних работ пуст')
    return response['homeworks'][0]


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
        if status not in HOMEWORK_VERDICTS:
            logger.error('Неожиданный статус домашней работы, '
                         'обнаруженный в ответе API')
        verdict = HOMEWORK_VERDICTS[status]
    except Exception:
        logger.error('Проблема с извлечением статуса домашней работы')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time() - ONE_WEEK_TIME)

    prev_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if message != prev_message:
                prev_message = message
                send_message(bot, message)
            else:
                logger.debug('Отсутсвует новый статус домашней работы')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != prev_message:
                prev_message = message
                send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

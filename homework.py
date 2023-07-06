import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s --- %(levelname)s --- %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяем наличие всех токенов в .env."""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ]
    if not all(tokens):
        logging.critical('Отсутствуют обязательные переменные окружения.')
        sys.exit()


def send_message(bot, message):
    """Отправляем сообщение в Telegram."""
    try:
        logging.debug(f'Сообщение "{message}" готово к отправке.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение "{message}" успешно отправлено.')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}.')
        return 'failed'


def get_api_answer(payload):
    """Получаем ответ от API."""
    message = (
        f'Ошибка при запросе к API с параметрами:'
        f'\nurl = {ENDPOINT}'
        f'\nheader = {HEADERS}'
        f'\nparams = {payload}'
    )
    try:
        logging.debug('Отправляем запрос к API.')
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        logging.debug('Ответ от API получен.')
        if response.status_code != HTTPStatus.OK:
            error = response.status_code
            logging.error(f'{message}. \nОшибка: {error}')
            raise Exception(f'{message}. \nОшибка: {error}')
        return response.json()
    except Exception as error:
        logging.error(f'Ошибка: {error}')
        raise Exception(error)


def check_response(response):
    """Проверяем ответ от API на валидность."""
    if not isinstance(response, dict):
        logging.error('Тип ответа от API не словарь.')
        raise TypeError('Тип ответа от API не словарь.')
    try:
        if type(response['homeworks']) != list:
            logging.error('Ответа от API не содержит список домашек.')
            raise TypeError('Ответа от API не содержит список домашек.')
    except KeyError as error:
        logging.error(f'В cловаре ответа API нет ключа "{error.args[0]}".')
        raise KeyError(error)


def parse_status(homework):
    """Проверяем, что статус работы изменился, готовим сообщение для бота."""
    try:
        homework_name = homework['homework_name']
        verdict = HOMEWORK_VERDICTS[homework['status']]
        message = (f'Изменился статус проверки работы "{homework_name}".'
                   f'\n{verdict}')
        return message
    except KeyError as error:
        logging.error(f'Отсутствует ключ {error.args[0]}.')
        raise KeyError(error)


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    last_message = ''
    previous_homework = ''
    timestamp = int(time.time())
    payload = {'from_date': timestamp}
    while True:
        try:
            response = get_api_answer(payload)
            check_response(response)
            homework = response['homeworks'][0]
            if homework != previous_homework:
                message = parse_status(homework)
                if message != last_message:
                    if send_message(bot, message) != 'failed':
                        last_message = message
                        previous_homework = homework
            else:
                logging.debug('Статус проверки работы не изменился.')
        except Exception as error:
            send_message(bot, f'Сбой в работе программы: {error}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

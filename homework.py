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
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s --- %(levelname)s --- %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

last_msg = ''
previous_status = ''


def check_tokens():
    """Проверяем наличие всех токенов в .env."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    if None in tokens.values() or '' in tokens.values():
        for token, value in tokens.items():
            if value is None or not value:
                logging.critical(
                    f'Отсутствие обязательных переменных окружения:'
                    f'{token} = {value}'
                )
        sys.exit()


def send_message(bot, message):
    """Отправляем сообщение в Telegram."""
    global last_msg
    if last_msg != message:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message)
            last_msg = message
            logging.debug(f'Сообщение "{message}" успешно отправлено.')
        except Exception as error:
            logging.error(f'Сбой при отправке сообщения в Telegram: {error}.')


def get_api_answer(timestamp):
    """Получаем ответ от API."""
    message = 'Ошибка при запросе к API, статус: {}'
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
        if response.status_code == HTTPStatus.NO_CONTENT:
            error = response.status_code
            logging.error(message.format(error))
            raise Exception(message.format(error))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        logging.error(message.format(error))


def check_response(response):
    """Проверяем ответ от API на валидность."""
    if type(response) != dict:
        logging.error('Тип ответа от API не словарь.')
        raise TypeError('Тип ответа от API не словарь.')
    else:
        try:
            response['homeworks']
            if type(response['homeworks']) != list:
                logging.error('Словарь "homeworks" не содержит список.')
                raise TypeError('Словарь "homeworks" не содержит список.')
        except KeyError('homeworks'):
            logging.error('В cловаре ответа API нет ключа "homeworks"')


def parse_status(homework):
    """Проверяем, что статус работы изменился, готовим сообщение для бота."""
    global previous_status
    try:
        homework_name = homework['homework_name']
        verdict = HOMEWORK_VERDICTS[homework['status']]
        message = (f'Изменился статус проверки работы "{homework_name}".'
                   f'\n{verdict}')
        if previous_status != homework['status']:
            previous_status = homework['status']
            return message
        logging.debug('Статус проверки работы не изменился')
        return message
    except KeyError('homework_name'):
        reason = 'Отсутствует ключ "homework_name".'
        logging.error(reason)
        return reason


def main():
    """Основная логика работы бота."""
    check_tokens()
    timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            payload = {'from_date': timestamp}
            response = get_api_answer(payload)
            check_response(response)
            homework = response['homeworks'][0]
            send_message(bot, parse_status(homework))
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logging.error(message)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

import time
import json
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, Update
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import requests
from collections import defaultdict

# Токен бота Telegram
TOKEN = '7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4'

# Храним cookies пользователей по chat_id
user_cookies = defaultdict(list)  # chat_id -> cookies

# Храним экземпляры драйверов для каждого пользователя
user_drivers = defaultdict(lambda: None)  # chat_id -> WebDriver

# Функция отправки уведомлений в Telegram
def send_notification(context: CallbackContext, message: str, chat_id: int):
    context.bot.send_message(chat_id=chat_id, text=message)

# Функция для старта бота
def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    # Если cookies уже сохранены для пользователя
    if user_cookies[chat_id]:
        update.message.reply_text("Ваши cookies успешно сохранены! Бот готов к работе.")
    else:
        update.message.reply_text("Привет! Пожалуйста, отправьте мне ваши cookies в формате JSON для авторизации.")

# Функция для обработки входных сообщений с cookies
def handle_cookies(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    try:
        # Получаем текст с cookies от пользователя
        cookies_json = update.message.text
        
        # Пробуем преобразовать в формат JSON
        user_cookies[chat_id] = json.loads(cookies_json)
        
        # Проверка на правильность структуры (проверим на наличие ключей)
        if not all(isinstance(cookie, dict) and "name" in cookie and "value" in cookie for cookie in user_cookies[chat_id]):
            raise ValueError("Некоторые cookies не содержат обязательных полей 'name' или 'value'.")

        # Подтверждаем, что cookies получены
        update.message.reply_text("Cookies успешно получены и сохранены!")

    except Exception as e:
        # Если произошла ошибка, сообщаем об этом
        update.message.reply_text(f"Ошибка при обработке cookies: {e}")

# Инициализация Selenium с использованием cookies
def init_driver_with_cookies(chat_id):
    if not user_cookies[chat_id]:
        print(f"Ошибка: cookies не заданы для пользователя {chat_id}!")
        return None

    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Запуск в фоновом режиме
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Указание пути к Chrome и драйверу
    driver = webdriver.Chrome(options=chrome_options)

    # Открываем сайт mpets.mobi
    driver.get('https://mpets.mobi')

    # Загружаем cookies из глобальной переменной для текущего пользователя
    for cookie in user_cookies[chat_id]:
        # Преобразуем cookie в формат, который может быть принят Selenium
        selenium_cookie = {
            'domain': cookie['domain'],
            'name': cookie['name'],
            'value': cookie['value'],
            'path': cookie['path'],
            'secure': cookie.get('secure', False),
            'httpOnly': cookie.get('httpOnly', False),
            'sameSite': cookie.get('sameSite', 'Lax'),
        }

        # Добавляем cookie в браузер
        driver.add_cookie(selenium_cookie)

    # Перезагружаем страницу, чтобы cookies вступили в силу
    driver.refresh()

    return driver

# Функция для кормления питомца
def feed_pet(driver):
    driver.get('https://mpets.mobi/?action=food')
    time.sleep(2)
    print("Питомец покормлен!")

# Функция для игры с питомцем
def play_pet(driver):
    driver.get('https://mpets.mobi/?action=play')
    time.sleep(2)
    print("Питомец поиграл!")

# Функция для отправки питомца на выставку
def send_pet_to_exhibition(driver):
    driver.get('https://mpets.mobi/show')
    time.sleep(2)
    print("Питомец отправлен на выставку!")

# Функция для выкапывания семян
def dig_seeds(driver):
    driver.get('https://mpets.mobi/glade_dig')
    time.sleep(2)
    print("Выкапывание семян завершено!")

# Функция для прогулки
def walk_pet(driver):
    # Прогулка по ссылке https://mpets.mobi/go_travel?id=X, где X от 10 до 1
    for time_value in range(10, 0, -1):  # Прогулка от 10 до 1
        driver.get(f'https://mpets.mobi/go_travel?id={time_value}')
        time.sleep(2)
        print(f"Прогулка питомца на {time_value} часов завершена!")

# Функция для выполнения всех действий с питомцем
def perform_tasks(chat_id):
    # Инициализируем драйвер с куками
    driver = init_driver_with_cookies(chat_id)

    if driver:
        # Запуск автоматических действий
        feed_pet(driver)
        play_pet(driver)
        send_pet_to_exhibition(driver)
        dig_seeds(driver)
        walk_pet(driver)

        # Закрываем драйвер после выполнения задач
        driver.quit()

# Планирование задач
def scheduled_tasks():
    # Пройдем по всем пользователям и запустим для каждого задачи
    for chat_id in user_cookies:
        perform_tasks(chat_id)

# Основная функция для запуска бота
def main():
    # Настройка Telegram-бота
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Обработчик команды /start
    dispatcher.add_handler(CommandHandler('start', start))

    # Обработчик для получения cookies
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_cookies))

    # Планирование задач (например, раз в день)
    updater.job_queue.run_daily(scheduled_tasks, time=time(8, 0))  # Запуск задач в 8 утра

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

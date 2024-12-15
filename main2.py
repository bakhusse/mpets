import time
import requests
import logging
import json
import asyncio
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] - %(levelname)s - %(message)s')

# Глобальная переменная для сессии
session = None

# Функция для выполнения перехода по URL
async def visit_url(url):
    try:
        response = session.get(url)
        if response.status_code == 200:
            logging.info(f"Успешно перешли по ссылке: {url}")
        else:
            logging.error(f"Ошибка при переходе по ссылке {url}. Статус: {response.status_code}")
    except Exception as e:
        logging.error(f"Ошибка при запросе к {url}: {e}")

# Асинхронная функция для перехода по ссылке с числами от 10 до 1 (с задержкой 1 секунда)
async def travel_ids():
    for i in range(10, 0, -1):
        url = f"https://mpets.mobi/go_travel?id={i}"
        await visit_url(url)
        await asyncio.sleep(1)  # Пауза 1 секунда между переходами

# Основная функция для автоматических переходов
async def automate_actions():
    global session
    
    # Ссылки для выполнения переходов
    action_urls = [
        "https://mpets.mobi/?action=food",
        "https://mpets.mobi/?action=play",
        "https://mpets.mobi/show",
        "https://mpets.mobi/glade_dig",
        "https://mpets.mobi/show_coin_get"
    ]
    
    # Основной цикл, который выполняет переходы каждую минуту
    while True:
        if session:
            # Переходы по действиям
            for url in action_urls:
                for _ in range(6):
                    await visit_url(url)
                    await asyncio.sleep(1)  # Переход через 1 секунду

            # Переход по ссылке с ID от 10 до 1
            await travel_ids()

            # Пауза 1 минута между полными циклами
            await asyncio.sleep(60)

# Функция для старта автоматизации
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Привет! Пожалуйста, отправь куки для авторизации.")

# Функция для получения и установки кук
def set_cookies(update: Update, context: CallbackContext):
    global session
    
    try:
        # Получаем куки из сообщения
        cookies_str = update.message.text
        cookies = json.loads(cookies_str)  # Преобразуем строку в список куков
        
        # Устанавливаем куки в сессию
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
        
        # Подтверждаем, что куки получены
        update.message.reply_text("Куки успешно получены и сессия авторизована!")

        # Запускаем автоматические действия
        update.message.reply_text("Автоматические действия начнутся сейчас.")
        asyncio.run(automate_actions())  # Запуск автоматизации в асинхронном режиме

    except Exception as e:
        logging.error(f"Ошибка при обработке куков: {e}")
        update.message.reply_text("Произошла ошибка при обработке куков. Попробуйте снова.")

# Основная функция для запуска бота
def main():
    updater = Updater("7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4", use_context=True)
    dispatcher = updater.dispatcher

    # Команды бота
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, set_cookies))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

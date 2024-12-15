import time
import requests
import logging
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
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
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Пожалуйста, отправь куки для авторизации.")

# Функция для получения и установки кук
async def set_cookies(update: Update, context: CallbackContext):
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
        await update.message.reply_text("Куки успешно получены и сессия авторизована!")

        # Запускаем автоматические действия
        await update.message.reply_text("Автоматические действия начнутся сейчас.")
        await automate_actions()  # Запуск автоматизации в асинхронном режиме

    except Exception as e:
        logging.error(f"Ошибка при обработке куков: {e}")
        await update.message.reply_text("Произошла ошибка при обработке куков. Попробуйте снова.")

# Основная функция для запуска бота
def main():
    application = Application.builder().token("7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4").build()

    # Команды бота
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_cookies))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()

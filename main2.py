import time
import requests
import logging
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from bs4 import BeautifulSoup
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

# Функция для получения статистики питомца
async def get_pet_stats():
    url = "https://mpets.mobi/profile"
    response = session.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Извлекаем нужные данные
        pet_name = soup.find('a', class_='darkgreen_link').text.strip()  # Имя питомца
        pet_level = soup.find('div', class_='stat_item').text.split(' ')[-2]  # Уровень питомца
        exp = soup.find_all('div', class_='stat_item')[3].text.strip().split(' ')[-2:]  # Опыт питомца
        beauty = soup.find_all('div', class_='stat_item')[4].text.strip().split(' ')[-1]  # Красота
        coins = soup.find_all('div', class_='stat_item')[6].text.strip().split(' ')[-1]  # Монеты
        hearts = soup.find_all('div', class_='stat_item')[7].text.strip().split(' ')[-1]  # Сердечки
        vip = soup.find_all('div', class_='stat_item')[1].text.strip().split(':')[-1].strip()  # VIP/Премиум

        stats = f"""
        Никнейм и уровень: {pet_name}, {pet_level} уровень
        Опыт: {exp[0]} / {exp[1]}
        Красота: {beauty}
        Монеты: {coins}
        Сердечки: {hearts}
        VIP-аккаунт/Премиум-аккаунт: {vip}
        """
        
        return stats
    else:
        logging.error(f"Ошибка при получении профиля питомца. Статус: {response.status_code}")
        return "Не удалось получить информацию о питомце."

# Команда /stats для получения статистики питомца
async def stats(update: Update, context: CallbackContext):
    if session:
        stats = await get_pet_stats()  # Получаем статистику
        await update.message.reply_text(stats)  # Отправляем статистику пользователю
    else:
        await update.message.reply_text("Сессия не авторизована. Пожалуйста, отправьте куки для авторизации.")

# Функция для старта бота
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

    except Exception as e:
        logging.error(f"Ошибка при обработке куков: {e}")
        await update.message.reply_text("Произошла ошибка при обработке куков. Попробуйте снова.")

# Основная функция для запуска бота
def main():
    application = Application.builder().token("7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4").build()

    # Команды бота
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))  # Команда /stats
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_cookies))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()

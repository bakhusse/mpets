import requests
from bs4 import BeautifulSoup
import time
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Глобальная переменная для сессии
session = None

# Функция для получения статистики питомца
async def get_pet_stats(session):
    url = "https://mpets.mobi/profile"
    response = session.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Извлекаем данные из HTML страницы с проверкой на None
        pet_name_and_level = soup.find('div', class_='stat_item')
        pet_name_and_level_text = pet_name_and_level.text if pet_name_and_level else ""
        pet_name = pet_name_and_level_text.split(",")[0].strip()  # Имя питомца
        pet_level = pet_name_and_level_text.split(",")[1].strip() if len(pet_name_and_level_text.split(",")) > 1 else "Неизвестно"  # Уровень питомца
        
        # Опыт: Разделяем текущий опыт и максимальный опыт
        exp_item = soup.find('div', class_='stat_item', string=lambda text: text and "Опыт" in text)
        if exp_item:
            exp_text = exp_item.text.split(":")[-1].strip()
            current_exp, max_exp = exp_text.split(" / ")
            current_exp = current_exp.strip()  # Текущий опыт
            max_exp = max_exp.strip()  # Максимальный опыт
        else:
            current_exp, max_exp = "Неизвестно", "Неизвестно"
        
        # Красота
        beauty_item = soup.find('div', class_='stat_item', string=lambda text: text and "Красота" in text)
        beauty = beauty_item.text.split(":")[-1].strip() if beauty_item else "Неизвестно"
        
        # Монеты
        coins_item = soup.find('div', class_='stat_item', string=lambda text: text and "Монеты" in text)
        coins = coins_item.text.split(":")[-1].strip() if coins_item else "Неизвестно"
        
        # Сердечки
        hearts_item = soup.find('div', class_='stat_item', string=lambda text: text and "Сердечки" in text)
        hearts = hearts_item.text.split(":")[-1].strip() if hearts_item else "Неизвестно"
        
        # VIP/Премиум-аккаунт
        vip_item = soup.find('div', class_='stat_item', string=lambda text: text and "VIP-аккаунт" in text)
        vip = vip_item.text.split(":")[-1].strip() if vip_item else "Неизвестно"

        # Формируем сообщение с результатами
        stats = f"""
        Никнейм и уровень: {pet_name}, {pet_level} уровень
        Опыт: {current_exp} / {max_exp}
        Красота: {beauty}
        Монеты: {coins}
        Сердечки: {hearts}
        VIP-аккаунт/Премиум-аккаунт: {vip}
        """
        
        return stats
    else:
        return "Не удалось получить информацию о питомце."

# Функция для перехода по ссылкам
async def auto_actions():
    global session

    # Список ссылок для автоматических действий
    urls = [
        "https://mpets.mobi/?action=food",
        "https://mpets.mobi/?action=play",
        "https://mpets.mobi/show",
        "https://mpets.mobi/glade_dig",
        "https://mpets.mobi/wakeup"
    ]
    
    # Переход по ссылкам
    for url in urls:
        for _ in range(6):  # Переходить 6 раз по каждой ссылке
            if session:
                response = session.get(url)
                if response.status_code == 200:
                    logging.info(f"Переход по ссылке {url} успешен.")
                else:
                    logging.error(f"Ошибка при запросе к {url}: {response.status_code}")
            time.sleep(1)  # Задержка 1 секунда между переходами

# Функция для старта бота
async def start(update: Update, context):
    update.message.reply_text("Привет! Отправь мне куки для авторизации.")

# Функция для остановки сессии
async def stop(update: Update, context):
    global session
    session = None  # Останавливаем сессию
    update.message.reply_text("Сессия остановлена. Отправьте новые куки для другого аккаунта.")

# Функция для обработки /stats
async def stats(update: Update, context):
    if session is None:
        update.message.reply_text("Сессия не установлена. Пожалуйста, отправьте куки.")
        return
    
    stats = await get_pet_stats(session)  # Получаем статистику
    update.message.reply_text(stats)

# Функция для обработки куки от пользователя
async def set_cookies(update: Update, context):
    global session
    
    cookies_input = update.message.text  # Получаем куки от пользователя
    cookies_list = eval(cookies_input)  # Преобразуем строку в список словарей
    
    session = requests.Session()  # Создаем новую сессию
    for cookie in cookies_list:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])  # Добавляем куки в сессию
    
    update.message.reply_text("Куки успешно установлены. Сессия готова к работе.")
    
    # Запуск автоматических действий
    asyncio.create_task(auto_actions())  # Запуск автоматических действий

# Настройка бота
def main():
    application = Application.builder().token("YOUR_BOT_API_TOKEN").build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_cookies))

    # Запуск бота
    application.run_polling()

# Запуск бота
if __name__ == '__main__':
    main()

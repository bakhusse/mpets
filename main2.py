import requests
import logging
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] - %(levelname)s - %(message)s')

# Глобальная переменная для хранения сессий пользователей
user_sessions = {}

# Функция для выполнения перехода по URL
async def visit_url(session, url):
    try:
        response = session.get(url)
        if response.status_code == 200:
            logging.info(f"Успешно перешли по ссылке: {url}")
        else:
            logging.error(f"Ошибка при переходе по ссылке {url}. Статус: {response.status_code}")
    except Exception as e:
        logging.error(f"Ошибка при запросе к {url}: {e}")

# Функция для получения статистики питомца
async def get_pet_stats(session):
    url = "https://mpets.mobi/profile"
    response = session.get(url)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Извлекаем нужные данные с проверкой на None
        pet_name = soup.find('a', class_='darkgreen_link')
        pet_name = pet_name.text.strip() if pet_name else "Неизвестно"

        pet_level = soup.find('div', class_='stat_item')
        pet_level = pet_level.text.split(' ')[-2] if pet_level else "Неизвестно"
        
        exp_item = soup.find_all('div', class_='stat_item')[3] if len(soup.find_all('div', class_='stat_item')) > 3 else None
        exp = exp_item.text.strip().split(' ')[-2:] if exp_item else ["Неизвестно", "Неизвестно"]
        
        beauty_item = soup.find_all('div', class_='stat_item')[4] if len(soup.find_all('div', class_='stat_item')) > 4 else None
        beauty = beauty_item.text.strip().split(' ')[-1] if beauty_item else "Неизвестно"
        
        coins_item = soup.find_all('div', class_='stat_item')[6] if len(soup.find_all('div', class_='stat_item')) > 6 else None
        coins = coins_item.text.strip().split(' ')[-1] if coins_item else "Неизвестно"
        
        hearts_item = soup.find_all('div', class_='stat_item')[7] if len(soup.find_all('div', class_='stat_item')) > 7 else None
        hearts = hearts_item.text.strip().split(' ')[-1] if hearts_item else "Неизвестно"
        
        vip_item = soup.find_all('div', class_='stat_item')[1] if len(soup.find_all('div', class_='stat_item')) > 1 else None
        vip = vip_item.text.strip().split(':')[-1].strip() if vip_item else "Неизвестно"

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

# Функция для старта бота
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Пожалуйста, отправь куки для авторизации.")

# Функция для получения и установки кук
async def set_cookies(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    try:
        # Получаем куки из сообщения
        cookies_str = update.message.text
        cookies = json.loads(cookies_str)  # Преобразуем строку в список куков
        
        # Создаем уникальную сессию для пользователя
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
        
        # Сохраняем сессию для пользователя
        user_sessions[user_id] = session
        
        # Подтверждаем, что куки получены
        await update.message.reply_text("Куки успешно получены и сессия авторизована!")
        
        # Запускаем автоматические действия для этого пользователя
        await auto_actions(user_id)

    except Exception as e:
        logging.error(f"Ошибка при обработке куков: {e}")
        await update.message.reply_text("Произошла ошибка при обработке куков. Попробуйте снова.")

# Функция для автоматических переходов по ссылкам
async def auto_actions(user_id):
    session = user_sessions.get(user_id)
    if not session:
        logging.error(f"Сессия для пользователя {user_id} не найдена.")
        return
    
    while True:
        # Перейти по ссылке /food
        await visit_url(session, "https://mpets.mobi/?action=food")
        # Перейти по ссылке /play
        await visit_url(session, "https://mpets.mobi/?action=play")
        # Перейти по ссылке /show
        await visit_url(session, "https://mpets.mobi/show")
        # Перейти по ссылке /glade_dig
        await visit_url(session, "https://mpets.mobi/glade_dig")
        # Переход по ссылке /wakeup
        await visit_url(session, "https://mpets.mobi/wakeup")
        # Переход по ссылке /show_coin_get (один раз)
        await visit_url(session, "https://mpets.mobi/show_coin_get")
        
        # Переход по ссылке go_travel с числами от 10 до 1
        for i in range(10, 0, -1):
            url = f"https://mpets.mobi/go_travel?id={i}"
            await visit_url(session, url)

        # Задержка 1 минута (для выполнения каждый раз через минуту)
        await asyncio.sleep(60)

# Команда /stats для получения статистики питомца
async def stats(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in user_sessions:
        session = user_sessions[user_id]
        stats = await get_pet_stats(session)  # Получаем статистику
        await update.message.reply_text(stats)  # Отправляем статистику пользователю
    else:
        await update.message.reply_text("Сессия не авторизована. Пожалуйста, отправьте куки для авторизации.")

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

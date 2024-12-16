import asyncio
import logging
import json
import os
from aiohttp import ClientSession, CookieJar
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from bs4 import BeautifulSoup
import nest_asyncio

# Активируем nest_asyncio для работы с асинхронными задачами в Google Colab
nest_asyncio.apply()

# Установите ваш токен бота
TOKEN = "7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4"

# Путь к файлу сессий
USERS_FILE = "users.txt"

# Разрешенные пользователи по ID
ALLOWED_USER_IDS = [1811568463, 630965641]

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Глобальная переменная для хранения сессий пользователей
user_sessions = {}

# Функция для отправки сообщений
async def send_message(update: Update, text: str):
    await update.message.reply_text(text)

# Команда старт для начала работы с ботом
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Управляй сессиями с помощью команд:\n"
                                    "/add - добавить новую сессию\n"
                                    "/del - удалить сессию\n"
                                    "/list - посмотреть все сессии\n"
                                    "/on - активировать сессию\n"
                                    "/off - деактивировать сессию\n"
                                    "/stats <имя_сессии> - проверить статистику питомца\n"
                                    "/get_user <имя_сессии> - узнать владельца сессии и куки\n"
                                    "Отправьте куки в формате JSON для авторизации.")

# Функция для чтения данных из файла
def read_from_file(session_name):
    if not os.path.exists(USERS_FILE):
        return None

    with open(USERS_FILE, "r") as file:
        lines = file.readlines()

    for line in lines:
        session_data = line.strip().split(" | ")

        # Проверка на наличие всех данных
        if len(session_data) != 3:
            logging.warning(f"Некорректная строка в файле: {line.strip()}")
            continue

        if session_data[0] == session_name:
            owner = session_data[1]
            try:
                cookies = json.loads(session_data[2])  # Пробуем распарсить куки
            except json.JSONDecodeError:
                logging.error(f"Ошибка при парсинге JSON для сессии {session_name}: {session_data[2]}")
                return None  # Возвращаем None, если JSON не валиден
            return {"session_name": session_data[0], "owner": owner, "cookies": cookies}

    return None

# Функция для записи данных в файл
def write_to_file(session_name, owner, cookies):
    with open(USERS_FILE, "a") as file:
        cookies_json = json.dumps(cookies)
        file.write(f"{session_name} | {owner} | {cookies_json}\n")
    logging.info(f"Сессия {session_name} добавлена в файл.")

# Команда для добавления новой сессии
async def add_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Использование: /add <имя_сессии> <куки в формате JSON>")
            return

        session_name = context.args[0]
        cookies_json = " ".join(context.args[1:])
        
        cookies = json.loads(cookies_json)
        if not cookies:
            await update.message.reply_text("Пожалуйста, отправьте куки в правильном формате JSON.")
            return

        # Создаём объект CookieJar для хранения и отправки куков
        jar = CookieJar()
        for cookie in cookies:
            jar.update_cookies({cookie['name']: cookie['value']})

        session = ClientSession(cookie_jar=jar)
        await session.__aenter__()

        # Сохраняем сессию и куки для пользователя
        if user_id not in user_sessions:
            user_sessions[user_id] = {}

        if session_name in user_sessions[user_id]:
            await update.message.reply_text(f"Сессия с именем {session_name} уже существует.")
        else:
            user_sessions[user_id][session_name] = {
                "session": session,
                "active": False,
                "owner": update.message.from_user.username,
                "cookies": cookies
            }

            # Записываем данные в файл
            write_to_file(session_name, update.message.from_user.username, cookies)
            await update.message.reply_text(f"Сессия {session_name} успешно добавлена!")
            logging.info(f"Сессия {session_name} добавлена для пользователя {update.message.from_user.username}.")

    except json.JSONDecodeError:
        await update.message.reply_text("Невозможно распарсить куки. Убедитесь, что они в формате JSON.")
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {e}")

# Команда для удаления сессии
async def remove_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /del <имя_сессии>")
        return

    session_name = context.args[0]

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        session = user_sessions[user_id].pop(session_name)
        await session["session"].__aexit__(None, None, None)
        await update.message.reply_text(f"Сессия {session_name} удалена.")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для отображения всех сессий пользователя
async def list_sessions(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in user_sessions and user_sessions[user_id]:
        session_list = "\n".join([f"{name} - {'Активна' if session['active'] else 'Неактивна'}"
                                 for name, session in user_sessions[user_id].items()])
        await update.message.reply_text(f"Ваши активные сессии:\n{session_list}")
    else:
        await update.message.reply_text("У вас нет активных сессий.")

# Команда для активации сессии
async def activate_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /on <имя_сессии>")
        return

    session_name = context.args[0]

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        user_sessions[user_id][session_name]["active"] = True
        await update.message.reply_text(f"Сессия {session_name} активирована!")

        # Автоматически начать действия после активации сессии
        asyncio.create_task(auto_actions(user_sessions[user_id][session_name]["session"], session_name))
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для деактивации сессии
async def deactivate_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /off <имя_сессии>")
        return

    session_name = context.args[0]

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        user_sessions[user_id][session_name]["active"] = False
        await update.message.reply_text(f"Сессия {session_name} деактивирована.")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Функция для получения статистики питомца
async def get_pet_stats(session: ClientSession):
    url = "https://mpets.mobi/?action=show"
    async with session.get(url) as response:
        if response.status != 200:
            logging.warning(f"Ошибка при запросе статистики: {response.status}")
            return "Не удалось получить статистику."
        page = await response.text()

    soup = BeautifulSoup(page, 'html.parser')
    stat_items = soup.find_all('div', class_='stat_item')

    if not stat_items:
        return "Не удалось найти элементы статистики."

    pet_name = stat_items[0].find('a', class_='darkgreen_link')
    pet_name = pet_name.text.strip() if pet_name else "Не найдено"
    
    stats = f"Никнейм: {pet_name}"
    return stats

# Функция для выполнения автоматических действий по ссылкам
async def auto_actions(session, session_name):
    actions = [
        "https://mpets.mobi/?action=food",
        "https://mpets.mobi/?action=play",
        "https://mpets.mobi/show",
        "https://mpets.mobi/glade_dig",
        "https://mpets.mobi/show_coin_get"
    ]
    
    # Количество переходов для каждой ссылки
    action_counts = [6, 6, 6, 6, 1]

    for action, count in zip(actions, action_counts):
        for _ in range(count):
            try:
                # Выполняем запрос по каждой ссылке
                async with session.get(action) as response:
                    if response.status != 200:
                        logging.warning(f"Ошибка при переходе по ссылке {action}: {response.status}")
                    else:
                        logging.info(f"Успешно перешли по ссылке {action} для сессии {session_name}")
            except Exception as e:
                logging.error(f"Ошибка при выполнении действия для сессии {session_name}: {e}")

# Главная функция для запуска бота
async def main():
    application = Application.builder().token(TOKEN).build()

    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_session))
    application.add_handler(CommandHandler("del", remove_session))
    application.add_handler(CommandHandler("list", list_sessions))
    application.add_handler(CommandHandler("on", activate_session))
    application.add_handler(CommandHandler("off", deactivate_session))

    # Запуск бота
    await application.run_polling()

# Запуск асинхронной задачи
if __name__ == "__main__":
    asyncio.run(main())

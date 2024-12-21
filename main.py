import asyncio
import logging
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from aiohttp import ClientSession, CookieJar
from bs4 import BeautifulSoup

# Установите ваш токен бота
TOKEN = "7689453735:AAHI8OfNGZzOM3fy9RQrXCjYRBHUKCXZAUY"

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

# Чтение сессий из файла
async def load_sessions_from_file():
    if not os.path.exists(USERS_FILE):
        logging.info("Файл с сессиями не найден. Начинаем с пустого набора сессий.")
        return

    with open(USERS_FILE, "r") as file:
        lines = file.readlines()

    for line in lines:
        session_data = line.strip().split(" | ")

        # Проверка на корректность данных
        if len(session_data) != 3:
            logging.warning(f"Некорректная строка в файле: {line.strip()}")
            continue

        session_name = session_data[0]
        owner = session_data[1]
        cookies_json = session_data[2]

        try:
            cookies = json.loads(cookies_json)
        except json.JSONDecodeError:
            logging.error(f"Ошибка при парсинге JSON для сессии {session_name}: {cookies_json}")
            continue  # Пропускаем эту сессию, если куки невалидны

        # Создаем сессию из cookies
        jar = CookieJar()
        for cookie in cookies:
            jar.update_cookies({cookie['name']: cookie['value']})

        session = await ClientSession(cookie_jar=jar).__aenter__()

        # Добавляем сессию в глобальную переменную
        user_sessions[owner] = user_sessions.get(owner, {})
        user_sessions[owner][session_name] = {
            "session": session,
            "active": False,
            "owner": owner,
            "cookies": cookies
        }

        logging.info(f"Сессия {session_name} загружена для пользователя {owner}.")

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
        session = user_sessions[user_id][session_name]
        session["active"] = True
        await update.message.reply_text(f"Сессия {session_name} активирована.")
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
        session = user_sessions[user_id][session_name]
        session["active"] = False
        await update.message.reply_text(f"Сессия {session_name} деактивирована.")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для получения информации о пользователе и его сессии
async def get_user(update: Update, context: CallbackContext):
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /get_user <имя_сессии>")
        return

    session_name = context.args[0]
    user_id = update.message.from_user.id

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        session = user_sessions[user_id][session_name]
        owner = session["owner"]
        cookies = session["cookies"]
        cookies_info = "\n".join([f"{cookie['name']}: {cookie['value']}" for cookie in cookies])
        await update.message.reply_text(f"Сессия: {session_name}\n"
                                       f"Владелец: {owner}\n"
                                       f"Куки:\n{cookies_info}")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для получения статистики питомца
async def stats(update: Update, context: CallbackContext):
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /stats <имя_сессии>")
        return

    session_name = context.args[0]
    user_id = update.message.from_user.id

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        session = user_sessions[user_id][session_name]

        # Здесь вы можете вставить логику для получения статистики питомца через API или веб-скрейпинг
        # Пример для скрейпинга данных с сайта питомца

        async with session["session"] as s:
            # Пример использования BeautifulSoup для парсинга страницы с питомцем
            url = "https://example.com/stats"  # Укажите нужный URL
            async with s.get(url) as response:
                if response.status == 200:
                    page_content = await response.text()
                    soup = BeautifulSoup(page_content, "html.parser")
                    # Пример получения статистики
                    pet_name = soup.find("div", {"class": "pet-name"}).text
                    pet_stats = soup.find("div", {"class": "pet-stats"}).text
                    await update.message.reply_text(f"Статистика питомца {pet_name}:\n{pet_stats}")
                else:
                    await update.message.reply_text(f"Не удалось получить статистику питомца для сессии {session_name}.")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Стартовая асинхронная функция
async def main():
    application = Application.builder().token(TOKEN).build()

    # Загрузка сессий
    await load_sessions_from_file()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_session))
    application.add_handler(CommandHandler("del", remove_session))
    application.add_handler(CommandHandler("list", list_sessions))
    application.add_handler(CommandHandler("on", activate_session))
    application.add_handler(CommandHandler("off", deactivate_session))
    application.add_handler(CommandHandler("get_user", get_user))
    application.add_handler(CommandHandler("stats", stats))

    # Запуск бота
    await application.run_polling()

# Запуск бота без asyncio.run()
if __name__ == "__main__":
    asyncio.run(main())

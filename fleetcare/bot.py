from datetime import datetime
import os
from dotenv import load_dotenv
import httpx
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import logging, re

logging.basicConfig(level=logging.INFO)
load_dotenv()
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000/api")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Ключи callback_data для маршрутизации
CB_BOOK = "BOOK"
CB_CANCEL = "CANCEL"
CB_INFO = "INFO"
CB_BOOK_DATE = "BOOK_DATE"  # BOOK_DATE|2025-09-25
CB_BOOK_TIME = "BOOK_TIME"  # BOOK_TIME|slot_id
CB_CANCEL_PICK = "CANCEL_PICK"  # CANCEL_PICK|ap_id
CB_INFO_PICK = "INFO_PICK"  # INFO_PICK|last|next

# Храним телефон пользователя в памяти (для простоты)
# В проде - можно хранить в БД
AUTH = {}  # tele_user_id -> phone


# Отправляет GET-запрос к серверу Django и возвращает данные в виде JSON
# (используется для получения информации)
async def api_get(path: str, params: dict = None):
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        r = await client.get(f"{API_BASE}{path}", params=params or {})
        r.raise_for_status()
        return r.json()


# Отправляет POST-запрос на сервер
# (создание новых записей, например, при записи на ТО)
async def api_post(path: str, json: dict = None):
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        r = await client.post(f"{API_BASE}{path}", json=json or {})
        r.raise_for_status()
        return r.json()


# Отправляет PATCH-запрос для частичного обновления данных
# (например, сохранение chat_id водителя)
async def api_patch(path: str, json: dict = None):
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        r = await client.patch(f"{API_BASE}{path}", json=json or {})
        r.raise_for_status()
        return r.json()


# Нормализация номера тел.
def normalize_user_phone(text: str) -> str:
    digits = re.sub(r"\D+", "", text or "")
    return digits


# Хелперы интерфейса
def main_menu_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Запись на ТО", callback_data=CB_BOOK),
            ],
            [
                InlineKeyboardButton("Отменить запись", callback_data=CB_CANCEL),
            ],
            [
                InlineKeyboardButton("Информация о ТО", callback_data=CB_INFO),
            ],
        ]
    )


# Кнопки да/нет
def yes_no_kb(yes_cb, no_cb):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Да, отменить", callback_data=yes_cb),
                InlineKeyboardButton("Нет, вернуться", callback_data=no_cb),
            ]
        ]
    )


# Авторизация (/start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Просим контакт с телефона (кнопка Телефон появляется только на мобильном Telegram)
    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("Поделиться номером телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Здравствуйте! Для входа отправьте, пожалуйста, свой номер телефона.\n"
        "Нажмите кнопку ниже или введите номер вручную в формате +79991234567.",
        reply_markup=kb,
    )


# Передача номера по кнопке
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Пользователь поделился контактом
    phone = update.message.contact.phone_number
    await auth_by_phone(update, context, phone)


# Передача номера через ввод
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # Пробуем извлечь номер из текста
    digits = normalize_user_phone(text)
    if digits:
        await auth_by_phone(update, context, digits)
    else:
        await update.message.reply_text(
            "Пожалуйста, пришлите номер телефона или нажмите кнопку «Поделиться номером».",
            reply_markup=ReplyKeyboardRemove(),
        )


# Вход по номеру
async def auth_by_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    tele_id = update.effective_user.id
    chat_id = update.effective_chat.id
    try:
        driver = await api_get("/drivers/by_phone/", {"phone": phone})
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await update.message.reply_text(
                "Номер не найден в системе. Обратитесь к менеджеру, чтобы вас добавили.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        # Сообщим пользователю и залогируем
        logging.exception("API error during auth")
        await update.message.reply_text(
            f"Временная ошибка авторизации ({e.response.status_code}). Попробуйте позже.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    except Exception as e:
        logging.exception("Unexpected error during auth")
        await update.message.reply_text(
            "Не удалось связаться с сервером. Проверьте, что веб-приложение запущено.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Добавим PATCH для записи chat_id
    try:
        await api_patch(f"/drivers/{driver['id']}/", {"chat_id": chat_id})
    except Exception as e:
        print(f"Не удалось сохранить chat_id для {driver['phone']}: {e}")
    AUTH[tele_id] = driver.get("phone") or phone
    full_name = f"{driver['last_name']} {driver['first_name']}"
    car = driver.get("car")
    car_str = f"{car['make']} {car['model']} ({car['plate_number']})" if car else "—"
    await update.message.reply_text(
        f"Добро пожаловать, {full_name}!\nВаш автомобиль: {car_str}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text("Выберите действие:", reply_markup=main_menu_kb())


# Декоратор, проверяющий, что пользователь авторизован в боте
def ensure_auth(fn):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        tele_id = update.effective_user.id
        if tele_id not in AUTH:
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.message.reply_text(
                    "Сначала выполните /start и авторизуйтесь."
                )
            else:
                await update.message.reply_text(
                    "Сначала выполните /start и авторизуйтесь."
                )
            return
        return await fn(update, context)

    return wrapper


# Проверка связи между ботом и сервером
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        _ = await api_get("/slots/free_dates/", {"days": 1})
        await update.message.reply_text("Пинг ок - бот видит API.")
    except Exception:
        logging.exception("Ping failed")
        await update.message.reply_text("Пинг не прошёл - API недоступен.")


# Обработчики меню
@ensure_auth
async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cb = q.data

    if cb == CB_BOOK:

        # Проверим, есть ли привязанный автомобиль
        phone = AUTH[update.effective_user.id]
        drv = await api_get("/drivers/by_phone/", {"phone": phone})
        if not drv.get("car"):
            await q.edit_message_text(
                "Для записи нужен привязанный автомобиль. Обратитесь к менеджеру.",
                reply_markup=main_menu_kb(),
            )
            return

        # Список свободных дат на ближайшую неделю
        dates = await api_get("/slots/free_dates/", {"days": 7})
        if not dates:
            await q.edit_message_text(
                "Нет свободных дат на ближайшую неделю.", reply_markup=main_menu_kb()
            )
            return

        # Словарь русских месяцев
        MONTHS_RU = {
            1: "января",
            2: "февраля",
            3: "марта",
            4: "апреля",
            5: "мая",
            6: "июня",
            7: "июля",
            8: "августа",
            9: "сентября",
            10: "октября",
            11: "ноября",
            12: "декабря",
        }

        # Показать клавиатуру дат
        rows = []
        for d in dates:
            dt = datetime.fromisoformat(d)
            caption = f"{dt.day} {MONTHS_RU[dt.month]}"
            rows.append(
                [InlineKeyboardButton(caption, callback_data=f"{CB_BOOK_DATE}|{d}")]
            )
        await q.edit_message_text(
            "Выберите дату:", reply_markup=InlineKeyboardMarkup(rows)
        )
        return

    if cb == CB_CANCEL:

        # Активные записи пользователя
        phone = AUTH[update.effective_user.id]
        items = await api_get("/appointments/active_by_phone/", {"phone": phone})
        if not items:
            await q.edit_message_text(
                "У вас нет активных записей на ТО.", reply_markup=main_menu_kb()
            )
            return
        rows = []
        for it in items:
            label = f"ТО на {it['date']} в {it['time']} ({it['car_plate']})"
            rows.append(
                [
                    InlineKeyboardButton(
                        label, callback_data=f"{CB_CANCEL_PICK}|{it['id']}"
                    )
                ]
            )
        await q.edit_message_text(
            "Ваши активные записи. Выберите для отмены:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if cb == CB_INFO:

        # Две уточняющие кнопки
        rows = [
            [
                InlineKeyboardButton(
                    "Последнее ТО", callback_data=f"{CB_INFO_PICK}|last"
                ),
                InlineKeyboardButton(
                    "Следующее ТО", callback_data=f"{CB_INFO_PICK}|next"
                ),
            ]
        ]
        await q.edit_message_text(
            "Какую информацию показать?", reply_markup=InlineKeyboardMarkup(rows)
        )
        return


# Выбор даты -> показываем время
@ensure_auth
async def on_pick_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, iso_date = q.data.split("|", 1)
    slots = await api_get("/slots/", {"date": iso_date})
    if not slots:
        await q.edit_message_text(
            "На выбранную дату времени нет. Попробуйте другую дату.",
            reply_markup=main_menu_kb(),
        )
        return

    # Кнопки времени
    rows = []
    for s in slots:
        btn = InlineKeyboardButton(
            datetime.strptime(s["time"], "%H:%M:%S").strftime("%H:%M"),
            callback_data=f"{CB_BOOK_TIME}|{s['id']}",
        )
        rows.append([btn])
    await q.edit_message_text(
        f"Выберите время на {iso_date}:", reply_markup=InlineKeyboardMarkup(rows)
    )


# Выбор времени -> создаём запись (POST /appointments/)
@ensure_auth
async def on_pick_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, slot_id_str = q.data.split("|", 1)
    slot_id = int(slot_id_str)
    phone = AUTH[update.effective_user.id]

    # Получим водителя и его авто
    drv = await api_get("/drivers/by_phone/", {"phone": phone})
    if not drv.get("car"):
        await q.edit_message_text(
            "Нет привязанного автомобиля. Обратитесь к менеджеру.",
            reply_markup=main_menu_kb(),
        )
        return

    payload = {
        "slot_id": slot_id,
        "driver": drv["id"],
        "car": drv["car"]["id"],
        "status": "active",
    }
    try:
        ap = await api_post("/appointments/", payload)
    except httpx.HTTPStatusError as e:
        await q.edit_message_text(
            f"Не удалось создать запись: {e.response.text}", reply_markup=main_menu_kb()
        )
        return

    # Подтверждение
    slot = ap["slot"]
    when = f"{slot['date']} {slot['time'][:5]}"
    plate = drv["car"]["plate_number"]
    await q.edit_message_text(
        f"Отлично! Вы записаны на ТО {when}.\nНомер записи: #{ap['id']} для автомобиля {plate}.",
        reply_markup=main_menu_kb(),
    )


# Отмена записи (подтверждение)
@ensure_auth
async def on_cancel_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, ap_id = q.data.split("|", 1)
    yes_cb = f"{CB_CANCEL_PICK}|YES|{ap_id}"
    no_cb = f"{CB_CANCEL_PICK}|NO|{ap_id}"
    await q.edit_message_text(
        "Вы уверены, что хотите отменить выбранную запись?",
        reply_markup=yes_no_kb(yes_cb, no_cb),
    )


# Отмена
@ensure_auth
async def on_cancel_yes_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, yn, ap_id = q.data.split("|", 2)
    if yn == "NO":
        await q.edit_message_text("Отмена прервана.", reply_markup=main_menu_kb())
        return

    # POST /appointments/{id}/cancel_user/
    try:
        await api_post(f"/appointments/{ap_id}/cancel_user/", {})
    except httpx.HTTPStatusError as e:
        await q.edit_message_text(
            f"Не удалось отменить: {e.response.text}", reply_markup=main_menu_kb()
        )
        return
    await q.edit_message_text("Запись отменена.", reply_markup=main_menu_kb())


# Информация о ТО
@ensure_auth
async def on_info_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()  # подтверждаем нажатие (может таймаутиться)
    except TimedOut:
        # не критично - продолжаем без подтверждения
        pass
    _, kind = q.data.split("|", 1)
    phone = AUTH[update.effective_user.id]
    drv = await api_get("/drivers/by_phone/", {"phone": phone})
    car = drv.get("car")
    if not car:
        await q.edit_message_text(
            "Нет привязанного автомобиля. Обратитесь к менеджеру.",
            reply_markup=main_menu_kb(),
        )
        return
    make_model = f"{car['make']} {car['model']} ({car['plate_number']})"
    if kind == "last":
        await q.edit_message_text(
            f"Ваш автомобиль {make_model} последний раз проходил ТО на пробеге "
            f"{car['last_service_mileage']} км.",
            reply_markup=main_menu_kb(),
        )
    else:
        await q.edit_message_text(
            f"Следующее ТО для автомобиля {make_model} запланировано на пробеге "
            f"{car['next_service_mileage']} км.",
            reply_markup=main_menu_kb(),
        )


# Справка о доступных командах бота
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды: /start - авторизация; меню - через кнопки ниже."
    )


# Главная функция
def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # Авторизация: контакт или текст
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Кнопки главного меню
    app.add_handler(
        CallbackQueryHandler(on_menu, pattern=f"^{CB_BOOK}$|^{CB_CANCEL}$|^{CB_INFO}$")
    )

    # Последовательности бронирования
    app.add_handler(CallbackQueryHandler(on_pick_date, pattern=f"^{CB_BOOK_DATE}\|"))
    app.add_handler(CallbackQueryHandler(on_pick_time, pattern=f"^{CB_BOOK_TIME}\|"))

    # Отмена
    app.add_handler(
        CallbackQueryHandler(on_cancel_pick, pattern=f"^{CB_CANCEL_PICK}\|(?!.+\|)")
    )
    app.add_handler(
        CallbackQueryHandler(
            on_cancel_yes_no,
            pattern=f"^{CB_CANCEL_PICK}\|YES\||^{CB_CANCEL_PICK}\|NO\|",
        )
    )

    # Инфо
    app.add_handler(CallbackQueryHandler(on_info_pick, pattern=f"^{CB_INFO_PICK}\|"))

    # Проверка "жив" сервер или нет
    app.add_handler(CommandHandler("ping", ping))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


# Точка входа
if __name__ == "__main__":
    main()

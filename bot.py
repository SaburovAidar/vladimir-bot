import logging
import requests
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)
from config import BOT_TOKEN, CHARACTER_NAME, CHARACTER_DESCRIPTION, CHARACTER_IMAGE_URL, APPS_SCRIPT_URL

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_IDS = [7984349049, 8485739966, 8309928121]
ENTER, CHOOSE_SVC, CHOOSE_STS, GET_NAME, GET_PHONE = range(5)
GIBDD_URL = "https://xn----8sbgbnrbpzfdotgl5e9h.xn--p1ai/"

user_statuses = {}
source_stats = {}
analytics = {}
user_analytics = {}
quick_orders = []

STATUSES = [
    ("📥 Принято в работу",       "accepted"),
    ("⚙️ Оформляется",            "processing"),
    ("📝 Проводятся экзамены",    "exams"),
    ("📦 Документ отправлен",     "sent"),
    ("🏛 Добавление в Госуслуги", "gosuslugi"),
    ("✅ Готово",                  "done"),
]
STATUS_PROGRESS = {
    "accepted":   "▰▱▱▱▱▱  10%",
    "processing": "▰▰▰▱▱▱  40%",
    "exams":      "▰▰▰▰▱▱  60%",
    "sent":       "▰▰▰▰▰▱  80%",
    "gosuslugi":  "▰▰▰▰▰▰  95%",
    "done":       "▰▰▰▰▰▰ 100% ✅",
}
STATUS_LABELS = {code: label for label, code in STATUSES}

SERVICES = [
    ("s_vu",     "🪪  Водительские удостоверения"),
    ("s_trak",   "🚜  Тракторные права"),
    ("s_sts",    "📄  СТС"),
    ("s_pts",    "📋  ПТС"),
    ("s_avto",   "🏫  Документы автошколы"),
    ("s_med",    "🏥  Медицинские справки"),
    ("s_diplom", "🎓  Дипломы"),
]

SERVICE_INFO = {
    "s_vu":    {"emoji":"🪪", "title":"Водительские удостоверения", "days":"7–14 дней",  "docs":["Паспорт","Прописка","Фото 3×4","Фото подписи"]},
    "s_trak":  {"emoji":"🚜", "title":"Тракторные права",           "days":"до 15 дней", "docs":["Паспорт","Прописка","Фото 3×4"], "note":"Категории: A · B · C · D · E · F"},
    "s_sts":   {"emoji":"📄", "title":"СТС",                        "days":"5–10 дней",  "docs":["Паспорт владельца","ПТС автомобиля","Договор купли-продажи","Полис ОСАГО","Квитанция госпошлины"]},
    "s_pts":   {"emoji":"📋", "title":"ПТС",                        "days":"7–14 дней",  "docs":["Паспорт владельца","Прописка","VIN номер","Документ о праве собственности","Полис ОСАГО","Диагностическая карта"]},
    "s_avto":  {"emoji":"🏫", "title":"Документы автошколы",        "days":"5–10 дней",  "docs":["Паспорт","Прописка"]},
    "s_med":   {"emoji":"🏥", "title":"Медицинские справки",        "days":"1–3 дня",    "docs":["Паспорт","Прописка"]},
    "s_diplom":{"emoji":"🎓", "title":"Дипломы",                    "days":"7–14 дней",  "docs":["Паспорт","Прописка","СНИЛС","Фото 3×4"]},
}

SERVICE_PHOTOS = {
    "s_vu":   "https://i.postimg.cc/k5CxL9DX/1.png",
    "s_trak": "https://i.postimg.cc/XvgwbhyV/2.png",
    "s_sts":  "https://i.postimg.cc/KY5n2Vgj/3.png",
    "s_avto": "https://i.postimg.cc/g0KvW56c/5.png",
    "s_pts":  "https://i.postimg.cc/jjhzb9JK/4.png",
    "s_med":  "https://i.postimg.cc/k5yxmZtC/6.png",
}

ACTION_NAMES = {
    "services":"📋 Услуги", "s_vu":"🪪 Права", "s_trak":"🚜 Тракторные",
    "s_sts":"📄 СТС", "s_pts":"📋 ПТС", "s_avto":"🏫 Автошкола",
    "s_med":"🏥 Мед справка", "s_diplom":"🎓 Диплом",
    "contact":"📞 Связаться", "check":"🔍 Проверить права",
    "reviews":"⭐ Отзывы", "ref":"👥 Реферал", "status":"📊 Статус",
    "order":"📝 Быстрая заявка",
}

GREETINGS = [
    "Рад видеть вас, {name}! 👋",
    "Приветствую, {name}! 🤝",
    "{name}, добро пожаловать! ✨",
    "Здравствуйте, {name}! 🚔",
]

DIV = "─────────────────────"

def clean(text):
    if not text:
        return "—"
    for ch in ["*","_","`","[","]"]:
        text = text.replace(ch, "")
    return text

def get_greeting(name):
    h = datetime.now().hour
    tg = ("🌅 Доброе утро" if 5<=h<12 else
          "☀️ Добрый день" if 12<=h<18 else
          "🌆 Добрый вечер" if 18<=h<23 else
          "🌙 Доброй ночи")
    return random.choice(GREETINGS).format(name=name) + "\n" + tg + "!"

def track(action, uid=None):
    analytics[action] = analytics.get(action, 0) + 1
    if uid:
        u = str(uid)
        if u not in user_analytics:
            user_analytics[u] = {}
        user_analytics[u][action] = user_analytics[u].get(action, 0) + 1

def build_service_text(key):
    info = SERVICE_INFO.get(key, {})
    docs = "\n".join("   ◦ " + d for d in info.get("docs", []))
    note = ("\n🗂  " + info["note"] + "\n") if info.get("note") else "\n"
    return (
        info["emoji"] + "  " + info["title"] + "\n"
        + DIV + "\n"
        + note
        + "⏱  Срок оформления: " + info.get("days","") + "\n\n"
        + "📎  Необходимые документы:\n"
        + docs + "\n"
        + DIV + "\n"
        + "📱  @kuznecov_vl"
    )

def _post(data):
    try: requests.post(APPS_SCRIPT_URL, json=data, timeout=8)
    except Exception as e: logger.error(f"POST: {e}")

def _get(params=""):
    try:
        r = requests.get(APPS_SCRIPT_URL + params, timeout=10)
        return r.json()
    except Exception as e:
        logger.error(f"GET: {e}")
        return {}

def save_user(tg_id, username, first_name, last_name, ref_by=None, source=None):
    _post({"tg_id":str(tg_id),"username":username,"first_name":first_name,
           "last_name":last_name,"ref_by":str(ref_by) if ref_by else "","source":source or ""})

def save_source(source, tg_id):
    _post({"action":"add_source","source":source,"tg_id":str(tg_id)})

def get_subscribers():
    data = _get("?action=list")
    return data if isinstance(data, list) else []

def load_sources():
    data = _get("?action=sources")
    if isinstance(data, dict):
        source_stats.clear()
        source_stats.update(data)
    logger.info(f"Loaded {len(source_stats)} sources")

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋  Услуги",          callback_data="services"),
         InlineKeyboardButton("📊  Мой статус",      callback_data="status")],
        [InlineKeyboardButton("📝  Быстрая заявка",  callback_data="order"),
         InlineKeyboardButton("📞  Связаться",       callback_data="contact")],
        [InlineKeyboardButton("⭐  Отзывы",          callback_data="reviews"),
         InlineKeyboardButton("🔍  Проверить права", callback_data="check")],
        [InlineKeyboardButton("👥  Пригласить друга", callback_data="ref")],
    ])

def services_kb():
    rows = [[InlineKeyboardButton(label, callback_data=key)] for key, label in SERVICES]
    rows.append([InlineKeyboardButton("◀️  Назад", callback_data="back")])
    return InlineKeyboardMarkup(rows)

def service_order_kb(key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝  Оставить заявку", callback_data="order_" + key)],
        [InlineKeyboardButton("✍️  Написать напрямую", url="https://t.me/kuznecov_vl")],
        [InlineKeyboardButton("◀️  Назад", callback_data="services")],
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊  Статус клиента", callback_data="a_status"),
         InlineKeyboardButton("📢  Рассылка",       callback_data="a_broadcast")],
        [InlineKeyboardButton("👥  Подписчики",     callback_data="a_subs"),
         InlineKeyboardButton("📈  Статистика",     callback_data="a_stats")],
        [InlineKeyboardButton("📝  Заявки",         callback_data="a_orders"),
         InlineKeyboardButton("🔗  Ссылки",         callback_data="a_links")],
        [InlineKeyboardButton("❌  Закрыть",        callback_data="a_close")],
    ])

async def send_service(query, key):
    text = build_service_text(key)
    photo = SERVICE_PHOTOS.get(key)
    kb = service_order_kb(key)
    if photo:
        try:
            import telegram
            await query.edit_message_media(
                media=telegram.InputMediaPhoto(media=photo, caption=text),
                reply_markup=kb)
            return
        except: pass
    try: await query.edit_message_caption(caption=text, reply_markup=kb)
    except: await query.edit_message_text(text=text, reply_markup=kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref_by = None
    source = None

    if context.args:
        arg = context.args[0]
        if arg.startswith("SRC_"):
            source = arg[4:]
            if source not in source_stats: source_stats[source] = []
            uid = str(user.id)
            if uid not in source_stats[source]:
                source_stats[source].append(uid)
                asyncio.create_task(asyncio.to_thread(save_source, source, user.id))
        elif arg.startswith("REF_"):
            try:
                ref_by = int(arg[4:])
                if ref_by != user.id:
                    try:
                        await context.bot.send_message(chat_id=ref_by,
                            text="🎉 По вашей ссылке пришёл " + user.first_name + "!\n\nКогда он оформит заказ — вы получите кешбэк 5 000 руб 💰")
                    except: pass
                    for aid in ADMIN_IDS:
                        try:
                            await context.bot.send_message(chat_id=aid,
                                text="🔗 Реферал!\nПришёл: " + user.first_name + " (@" + (user.username or "—") + ") | " + str(user.id) + "\nПригласил: " + str(ref_by))
                        except: pass
            except: pass

    asyncio.create_task(asyncio.to_thread(
        save_user, user.id, user.username or "", user.first_name or "", user.last_name or "", ref_by, source))

    if context.job_queue:
        if not context.job_queue.get_jobs_by_name("rem_" + str(user.id)):
            context.job_queue.run_once(reminder_job, when=timedelta(days=1),
                data={"chat_id": user.id, "name": user.first_name}, name="rem_" + str(user.id))

    greeting = get_greeting(user.first_name)
    caption = (
        greeting + "\n\n"
        "Я  *" + CHARACTER_NAME + "*\n"
        + DIV + "\n"
        + CHARACTER_DESCRIPTION + "\n"
        + DIV + "\n"
        "Выберите что вас интересует 👇"
    )

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await asyncio.sleep(0.8)

    try:
        await update.message.reply_photo(photo=CHARACTER_IMAGE_URL, caption=caption,
            parse_mode="Markdown", reply_markup=main_kb())
    except:
        await update.message.reply_text(caption, parse_mode="Markdown", reply_markup=main_kb())

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.send_message(chat_id=d["chat_id"],
            text=("👋  " + d["name"] + ", добрый день!\n"
                  + DIV + "\n"
                  "Напоминаем — оформление документов\nзанимает от 7 дней.\n\n"
                  "Успейте подать заявку! ⚡\n"
                  + DIV + "\n"
                  "📱  @kuznecov_vl"),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✍️  Оформить сейчас", url="https://t.me/kuznecov_vl")
            ]]))
    except Exception as e: logger.error(f"Reminder: {e}")

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    track(q.data, user.id)

    if q.data == "back":
        greeting = get_greeting(user.first_name)
        caption = (
            greeting + "\n\n"
            "Я  *" + CHARACTER_NAME + "*\n"
            + DIV + "\n"
            + CHARACTER_DESCRIPTION + "\n"
            + DIV + "\n"
            "Выберите что вас интересует 👇"
        )
        try:
            import telegram
            await q.edit_message_media(
                media=telegram.InputMediaPhoto(media=CHARACTER_IMAGE_URL, caption=caption, parse_mode="Markdown"),
                reply_markup=main_kb())
        except:
            try: await q.edit_message_caption(caption=caption, parse_mode="Markdown", reply_markup=main_kb())
            except: pass

    elif q.data == "services":
        await q.edit_message_caption(
            caption="📋  Услуги Олега Сергеевича\n" + DIV + "\nВыберите интересующую услугу:",
            reply_markup=services_kb())

    elif q.data in SERVICE_INFO:
        await send_service(q, q.data)

    elif q.data.startswith("order_"):
        key = q.data[6:]
        info = SERVICE_INFO.get(key, {})
        context.user_data["order_service"] = info.get("emoji","") + "  " + info.get("title","")
        context.user_data["order_uid"] = str(user.id)
        context.user_data["order_uname"] = user.username or ""
        await q.edit_message_caption(
            caption="📝  Быстрая заявка\n" + DIV + "\n"
            "Услуга: " + info.get("emoji","") + "  " + info.get("title","") + "\n\n"
            "Введите ваше *имя*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌  Отмена", callback_data=q.data.replace("order_",""))]]))
        return

    elif q.data == "order":
        await q.edit_message_caption(
            caption="📝  Быстрая заявка\n" + DIV + "\n"
            "Оставьте заявку и мы свяжемся с вами в течение 15 минут!\n\n"
            "Введите ваше *имя*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌  Отмена", callback_data="back")]]))
        context.user_data["order_service"] = "Не указана"
        context.user_data["order_uid"] = str(user.id)
        context.user_data["order_uname"] = user.username or ""
        return

    elif q.data == "status":
        uid = str(user.id)
        if uid in user_statuses:
            s = user_statuses[uid]
            label = STATUS_LABELS.get(s["status"], s["status"])
            prog = STATUS_PROGRESS.get(s["status"], "")
            await q.edit_message_caption(
                caption=("📊  Статус вашей заявки\n" + DIV + "\n"
                    "🗂  Услуга:    " + s["service"] + "\n"
                    "📌  Статус:    " + label + "\n"
                    "📶  Прогресс:  " + prog + "\n"
                    "🕐  Обновлено: " + s["updated"] + "\n" + DIV),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️  Назад", callback_data="back")]]))
        else:
            await q.edit_message_caption(
                caption=("📊  Статус заявки\n" + DIV + "\n"
                    "У вас пока нет активных заявок.\n\n"
                    "Оформите заявку — и здесь появится статус!\n" + DIV + "\n"
                    "📱  @kuznecov_vl"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝  Оставить заявку", callback_data="order")],
                    [InlineKeyboardButton("◀️  Назад", callback_data="back")]]))

    elif q.data == "contact":
        await q.edit_message_caption(
            caption=("📞  Связаться\n" + DIV + "\n"
                "Отвечаем быстро — до 15 минут!\n\n"
                "Работаем: 24/7 🕐\n" + DIV),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️  Написать Олегу Сергеевичу", url="https://t.me/kuznecov_vl")],
                [InlineKeyboardButton("◀️  Назад", callback_data="back")]]))

    elif q.data == "reviews":
        await q.edit_message_caption(
            caption=("⭐  Отзывы\n" + DIV + "\n"
                "Работаю конфиденциально — отзывы\nпоказываю лично по запросу.\n\n"
                "Напишите мне и я всё покажу 👇\n" + DIV),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️  Написать Олегу Сергеевичу", url="https://t.me/kuznecov_vl")],
                [InlineKeyboardButton("◀️  Назад", callback_data="back")]]))

    elif q.data == "check":
        await q.edit_message_caption(
            caption=("🔍  Проверка водительских прав\n" + DIV + "\n"
                "Проверьте подлинность удостоверения\nна официальных сайтах:\n\n"
                "> гос-автоинспекция.net\n"
                "> gibdd.news\n"
                "> госавтоинспекция.org\n" + DIV),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 гос-автоинспекция.net", url="https://xn----8sbgbnrbpzfdotgl5e9h.net/")],
                [InlineKeyboardButton("🌐 gibdd.news", url="https://gibdd.news/")],
                [InlineKeyboardButton("🌐 госавтоинспекция.org", url="https://xn--80aebkobnwfcnsfk1e0h.org/")],
                [InlineKeyboardButton("◀️  Назад", callback_data="back")]]))

    elif q.data == "ref":
        bot_u = (await context.bot.get_me()).username
        link = "https://t.me/" + bot_u + "?start=REF_" + str(user.id)
        await q.edit_message_caption(
            caption=("👥  Пригласить друга\n" + DIV + "\n"
                "Поделитесь ссылкой — когда друг\nоформит заказ, вы получите:\n\n"
                "💰  Кешбэк 5 000 руб\n" + DIV + "\n"
                "Ваша ссылка:\n" + link),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️  Назад", callback_data="back")]]))

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_name"] = update.message.text.strip()
    await update.message.reply_text(
        "📞  Введите ваш номер телефона:\n\n/cancel — отмена")
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    name = context.user_data.get("order_name", "—")
    service = context.user_data.get("order_service", "Не указана")
    uid = context.user_data.get("order_uid", "")
    uname = context.user_data.get("order_uname", "")

    order = {"name": name, "phone": phone, "service": service, "uid": uid, "uname": uname,
             "time": datetime.now().strftime("%d.%m.%Y %H:%M")}
    quick_orders.append(order)

    await update.message.reply_text(
        "✅  Заявка принята!\n" + DIV + "\n"
        "Имя: " + name + "\n"
        "Телефон: " + phone + "\n"
        "Услуга: " + service + "\n" + DIV + "\n"
        "Олег Сергеевич свяжется с вами\nв течение 15 минут! ⚡",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✍️  Написать напрямую", url="https://t.me/kuznecov_vl")
        ]]))

    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=aid,
                text=("📝  Новая заявка!\n" + DIV + "\n"
                    "👤  Имя: " + name + "\n"
                    "📞  Телефон: " + phone + "\n"
                    "🗂  Услуга: " + service + "\n"
                    "🆔  ID: " + uid + "\n"
                    "📱  @" + (uname or "нет username") + "\n"
                    "🕐  " + order["time"] + "\n" + DIV))
        except: pass
    return ConversationHandler.END

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа.")
        return ConversationHandler.END
    load_sources()
    await update.message.reply_text("👮  Админ панель\n" + DIV + "\nВыберите действие:", reply_markup=admin_kb())
    return ENTER

async def admin_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "a_close":
        await q.edit_message_text("✅ Закрыто.")
        return ConversationHandler.END

    elif q.data == "a_status":
        await q.edit_message_text("👤 Введите числовой ID клиента:\n\n/cancel — отмена")
        context.user_data["act"] = "status"
        return ENTER

    elif q.data == "a_broadcast":
        await q.edit_message_text("📢 Рассылка\n" + DIV + "\nОтправьте фото или /skip\n\n/cancel — отмена")
        context.user_data["act"] = "bcast_photo"
        return ENTER

    elif q.data == "a_orders":
        if not quick_orders:
            await q.edit_message_text("📝 Заявок пока нет.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="a_close")]]))
            return ENTER
        text = "📝  Заявки\n" + DIV + "\n"
        for i, o in enumerate(quick_orders[-20:], 1):
            text += (str(i) + ". " + o["name"] + " | " + o["phone"] + "\n"
                     "   " + o["service"] + " | " + o["time"] + "\n\n")
        await q.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="a_close")]]))
        return ENTER

    elif q.data == "a_subs":
        await show_page(q, 0)
        return ENTER

    elif q.data.startswith("a_pg_"):
        await show_page(q, int(q.data[5:]))
        return ENTER

    elif q.data.startswith("a_usr_"):
        await show_user(q, q.data[6:])
        return ENTER

    elif q.data.startswith("a_set_"):
        tg_id = q.data[6:]
        context.user_data["target"] = tg_id
        kb = [[InlineKeyboardButton(label, callback_data="a_svc_" + str(i))] for i, (_, label) in enumerate(SERVICES)]
        kb.append([InlineKeyboardButton("❌ Отмена", callback_data="a_close")])
        await q.edit_message_text("Выберите услугу для " + tg_id + ":", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSE_SVC

    elif q.data == "a_search":
        await q.edit_message_text("🔍 Поиск\n" + DIV + "\nВведите TG ID или @username:\n\n/cancel — отмена")
        context.user_data["act"] = "search"
        return ENTER

    elif q.data == "a_links":
        load_sources()
        bot_info = await context.bot.get_me()
        kb = [[InlineKeyboardButton("📌 " + src + " — " + str(len(ids)) + " чел.", callback_data="a_lv_" + src)]
              for src, ids in source_stats.items()]
        kb.append([InlineKeyboardButton("➕ Создать ссылку", callback_data="a_link_new")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="a_close")])
        text = "🔗 Ссылки\n" + DIV + "\n" + ("Нет ссылок." if not source_stats else "Всего: " + str(len(source_stats)))
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return ENTER

    elif q.data == "a_link_new":
        await q.edit_message_text("➕ Введите название:\n(instagram, vk, kanal...)\n\n/cancel — отмена")
        context.user_data["act"] = "new_link"
        return ENTER

    elif q.data.startswith("a_lv_"):
        src = q.data[5:]
        bot_info = await context.bot.get_me()
        link = "https://t.me/" + bot_info.username + "?start=SRC_" + src
        count = len(source_stats.get(src, []))
        await q.edit_message_text(
            "📌 " + src + "\n" + DIV + "\nПереходов: " + str(count) + " чел.\n\nСсылка:\n" + link + "\n" + DIV,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К ссылкам", callback_data="a_links")]]))
        return ENTER

    elif q.data == "a_stats":
        subs = get_subscribers()
        sorted_a = sorted(analytics.items(), key=lambda x: x[1], reverse=True)
        a_text = "".join("  › " + ACTION_NAMES.get(k,k) + ": " + str(v) + "\n" for k,v in sorted_a[:10])
        src_text = "".join("  › " + s + ": " + str(len(ids)) + " чел.\n" for s,ids in source_stats.items())
        await q.edit_message_text(
            "📈 Статистика\n" + DIV + "\n"
            "👥 Подписчиков: " + str(len(subs)) + "\n"
            "📊 Активных заявок: " + str(len(user_statuses)) + "\n"
            "📝 Быстрых заявок: " + str(len(quick_orders)) + "\n"
            + DIV + "\n"
            "🔥 Топ действий:\n" + (a_text or "  Нет данных\n") +
            DIV + "\n"
            "🔗 Источники:\n" + (src_text or "  Нет данных\n") + DIV)
        return ConversationHandler.END

async def show_page(q, page):
    subs = get_subscribers()
    total = len(subs)
    per = 10
    pages = max(1, (total + per - 1) // per)
    page = max(0, min(page, pages - 1))
    chunk = subs[page*per:(page+1)*per]
    text = "👥 Подписчики: " + str(total) + "\n" + DIV + "\n"
    kb = []
    for i, s in enumerate(chunk, page*per + 1):
        name = clean((s.get("first_name","") + " " + s.get("last_name","")).strip())
        uname = "@" + s["username"] if s.get("username") else "—"
        text += str(i) + ". " + name + "  |  " + uname + "\n"
        kb.append([InlineKeyboardButton(str(i) + ". " + name[:20], callback_data="a_usr_" + str(s.get("tg_id","")))])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("◀️", callback_data="a_pg_" + str(page-1)))
    nav.append(InlineKeyboardButton(str(page+1) + "/" + str(pages), callback_data="a_pg_" + str(page)))
    if page < pages-1: nav.append(InlineKeyboardButton("▶️", callback_data="a_pg_" + str(page+1)))
    kb.append(nav)
    kb.append([InlineKeyboardButton("🔍 Поиск", callback_data="a_search")])
    kb.append([InlineKeyboardButton("◀️ В меню", callback_data="a_close")])
    await q.edit_message_text(text + DIV, reply_markup=InlineKeyboardMarkup(kb))

async def show_user(q, tg_id):
    subs = get_subscribers()
    sub = next((s for s in subs if str(s.get("tg_id","")) == tg_id), None)
    if not sub:
        await q.edit_message_text("❌ Не найден.")
        return
    name = clean((sub.get("first_name","") + " " + sub.get("last_name","")).strip() or "—")
    uname = "@" + sub["username"] if sub.get("username") else "—"
    source = clean(sub.get("source","") or "—")
    status = user_statuses.get(tg_id, {})
    status_text = STATUS_LABELS.get(status.get("status",""), "Нет заявки")
    acts = user_analytics.get(tg_id, {})
    a_text = "".join("  › " + ACTION_NAMES.get(k,k) + ": " + str(v) + " раз\n"
                     for k,v in sorted(acts.items(), key=lambda x: x[1], reverse=True)[:8]) if acts else "  Нет данных\n"
    kb = []
    if sub.get("username"):
        kb.append([InlineKeyboardButton("✍️ Написать", url="https://t.me/" + sub["username"])])
    kb.append([InlineKeyboardButton("📊 Изменить статус", callback_data="a_set_" + tg_id)])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="a_subs")])
    await q.edit_message_text(
        "👤 " + name + "  |  " + uname + "\n" + DIV + "\n"
        "ID: " + tg_id + "\n"
        "Дата: " + str(sub.get("date","—")) + "\n"
        "Источник: " + source + "\n"
        "Статус: " + status_text + "\n"
        + DIV + "\n"
        "Активность:\n" + a_text + DIV,
        reply_markup=InlineKeyboardMarkup(kb))

async def admin_enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    act = context.user_data.get("act","")
    text = update.message.text or ""

    if act == "bcast_photo":
        if update.message.photo:
            context.user_data["bcast_photo"] = update.message.photo[-1].file_id
            await update.message.reply_text("✅ Фото получено! Напишите текст:\n\n/cancel — отмена")
        else:
            await update.message.reply_text("📝 Напишите текст рассылки:\n\n/cancel — отмена")
        context.user_data["act"] = "bcast_text"
        return ENTER

    elif act == "bcast_text":
        photo = context.user_data.pop("bcast_photo", None)
        subs = get_subscribers()
        if not subs:
            await update.message.reply_text("❌ Нет подписчиков.")
            return ConversationHandler.END
        msg = await update.message.reply_text("📤 Отправляю " + str(len(subs)) + " подписчикам...")
        ok = fail = 0
        for s in subs:
            try:
                if photo:
                    await context.bot.send_photo(chat_id=int(s["tg_id"]), photo=photo,
                        caption="📢 Сообщение от Олега Сергеевича:\n" + DIV + "\n" + text)
                else:
                    await context.bot.send_message(chat_id=int(s["tg_id"]),
                        text="📢 Сообщение от Олега Сергеевича:\n" + DIV + "\n" + text)
                ok += 1
            except: fail += 1
        await msg.edit_text("✅ Готово!\n\n📨 Отправлено: " + str(ok) + "\n❌ Не доставлено: " + str(fail))
        return ConversationHandler.END

    elif act == "new_link":
        src = text.strip().lower().replace(" ","_")
        if src not in source_stats: source_stats[src] = []
        bot_info = await context.bot.get_me()
        link = "https://t.me/" + bot_info.username + "?start=SRC_" + src
        await update.message.reply_text(
            "✅ Ссылка создана!\n" + DIV + "\nИсточник: " + src + "\n" + DIV + "\n" + link,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К ссылкам", callback_data="a_links")]]))
        return ConversationHandler.END

    elif act == "search":
        q_text = text.strip().replace("@","")
        subs = get_subscribers()
        sub = next((s for s in subs if str(s.get("tg_id","")) == q_text or s.get("username","").lower() == q_text.lower()), None)
        if not sub:
            await update.message.reply_text("❌ Не найден.")
            return ENTER
        tg_id = str(sub.get("tg_id",""))
        name = clean((sub.get("first_name","") + " " + sub.get("last_name","")).strip() or "—")
        uname = "@" + sub["username"] if sub.get("username") else "—"
        source = clean(sub.get("source","") or "—")
        status = user_statuses.get(tg_id, {})
        status_text = STATUS_LABELS.get(status.get("status",""), "Нет заявки")
        acts = user_analytics.get(tg_id, {})
        a_text = "".join("  › " + ACTION_NAMES.get(k,k) + ": " + str(v) + " раз\n"
                         for k,v in sorted(acts.items(), key=lambda x: x[1], reverse=True)[:8]) if acts else "  Нет данных\n"
        kb = []
        if sub.get("username"):
            kb.append([InlineKeyboardButton("✍️ Написать", url="https://t.me/" + sub["username"])])
        kb.append([InlineKeyboardButton("📊 Изменить статус", callback_data="a_set_" + tg_id)])
        kb.append([InlineKeyboardButton("◀️ К подписчикам", callback_data="a_subs")])
        await update.message.reply_text(
            "👤 " + name + "  |  " + uname + "\n" + DIV + "\n"
            "ID: " + tg_id + "\nДата: " + str(sub.get("date","—")) + "\n"
            "Источник: " + source + "\nСтатус: " + status_text + "\n"
            + DIV + "\nАктивность:\n" + a_text + DIV,
            reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END

    else:
        context.user_data["target"] = text.strip().replace("@","")
        kb = [[InlineKeyboardButton(label, callback_data="a_svc_" + str(i))] for i,(_, label) in enumerate(SERVICES)]
        kb.append([InlineKeyboardButton("❌ Отмена", callback_data="a_close")])
        await update.message.reply_text("Клиент: " + context.user_data["target"] + "\n\nВыберите услугу:", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSE_SVC

async def admin_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "a_close":
        await q.edit_message_text("✅ Отменено.")
        return ConversationHandler.END
    idx = int(q.data[6:])
    context.user_data["service"] = SERVICES[idx][1]
    kb = [[InlineKeyboardButton(label, callback_data="a_sts_" + code)] for label, code in STATUSES]
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="a_close")])
    await q.edit_message_text("Услуга: " + context.user_data["service"] + "\n\nВыберите статус:", reply_markup=InlineKeyboardMarkup(kb))
    return CHOOSE_STS

async def admin_sts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "a_close":
        await q.edit_message_text("✅ Отменено.")
        return ConversationHandler.END
    code = q.data[6:]
    label = STATUS_LABELS.get(code, code)
    prog = STATUS_PROGRESS.get(code, "")
    target = context.user_data["target"]
    service = context.user_data["service"]
    user_statuses[target] = {"service": service, "status": code, "updated": datetime.now().strftime("%d.%m.%Y %H:%M")}
    try:
        chat_id = int(target) if target.isdigit() else target
        await context.bot.send_message(chat_id=chat_id,
            text=("🚔 Олег Сергеевич сообщает:\n" + DIV + "\n"
                  "Услуга: " + service + "\n"
                  "Статус: " + label + "\n"
                  "Прогресс: " + prog + "\n" + DIV + "\n"
                  "По вопросам: @kuznecov_vl"))
        notify = "✅ Клиент уведомлён!"
    except Exception as e:
        notify = "⚠️ Не удалось: " + str(e)
    await q.edit_message_text(
        "✅ Готово!\n" + DIV + "\n"
        "Клиент: " + target + "\nУслуга: " + service + "\nСтатус: " + label + "\n" + DIV + "\n" + notify)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("act") == "bcast_photo":
        context.user_data.pop("bcast_photo", None)
        context.user_data["act"] = "bcast_text"
        await update.message.reply_text("📝 Без фото. Напишите текст:\n\n/cancel — отмена")
        return ENTER
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in user_statuses:
        s = user_statuses[uid]
        label = STATUS_LABELS.get(s["status"], s["status"])
        prog = STATUS_PROGRESS.get(s["status"], "")
        await update.message.reply_text(
            "📊 Статус заявки\n" + DIV + "\n"
            "Услуга: " + s["service"] + "\nСтатус: " + label + "\nПрогресс: " + prog + "\nОбновлено: " + s["updated"])
    else:
        await update.message.reply_text("📊 Активных заявок нет.\n\n📱 @kuznecov_vl")

async def post_init(app):
    load_sources()
    await app.bot.set_my_commands([BotCommand("start","Главное меню"), BotCommand("status","Мой статус")])
    from telegram import BotCommandScopeChat
    for aid in ADMIN_IDS:
        try:
            await app.bot.set_my_commands([
                BotCommand("start","Главное меню"), BotCommand("status","Мой статус"), BotCommand("admin","Админ панель"),
            ], scope=BotCommandScopeChat(chat_id=aid))
        except: pass

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    order_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(btn, pattern="^order$"),
            CallbackQueryHandler(btn, pattern="^order_"),
        ],
        states={
            GET_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_cmd), CallbackQueryHandler(admin_btn, pattern="^a_")],
        states={
            ENTER: [MessageHandler(filters.PHOTO, admin_enter), MessageHandler(filters.TEXT & ~filters.COMMAND, admin_enter), CallbackQueryHandler(admin_btn, pattern="^a_")],
            CHOOSE_SVC: [CallbackQueryHandler(admin_svc, pattern="^a_svc_"), CallbackQueryHandler(admin_svc, pattern="^a_close")],
            CHOOSE_STS: [CallbackQueryHandler(admin_sts, pattern="^a_sts_"), CallbackQueryHandler(admin_sts, pattern="^a_close")],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("skip", skip)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(order_conv)
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(btn))

    logger.info("Бот v2 запущен ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

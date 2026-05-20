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
ADMIN_ENTER_USER, ADMIN_CHOOSE_SERVICE, ADMIN_CHOOSE_STATUS = range(3)

user_statuses = {}
source_stats = {}
analytics = {}
user_analytics = {}

STATUSES = [
    ("📥 Документы приняты в работу", "accepted"),
    ("⚙️ Документы оформляются", "processing"),
    ("📝 Проводятся экзамены", "exams"),
    ("📦 Документ отправлен", "sent"),
    ("🏛 Ожидается добавление в Госуслуги", "gosuslugi"),
    ("✅ Готово", "done"),
]
STATUS_PROGRESS = {
    "accepted":   "▓░░░░░ 10%",
    "processing": "▓▓▓░░░ 40%",
    "exams":      "▓▓▓▓░░ 60%",
    "sent":       "▓▓▓▓▓░ 80%",
    "gosuslugi":  "▓▓▓▓▓▓ 95%",
    "done":       "▓▓▓▓▓▓ 100% ✅",
}
STATUS_LABELS = {s[1]: s[0] for s in STATUSES}

ACTION_NAMES = {
    "services": "📋 Открыл услуги",
    "s_vu": "🪪 Водительские права",
    "s_traktor": "🚜 Тракторные права",
    "s_sts": "📄 СТС",
    "s_pts": "📋 ПТС",
    "s_avto": "🏫 Автошкола",
    "s_med": "🏥 Мед справка",
    "s_diplom": "🎓 Диплом",
    "contact": "📞 Связаться",
    "check_rights": "🔍 Проверить права",
    "reviews": "⭐ Отзывы",
    "referral": "👥 Реферал",
    "my_status": "📊 Мой статус",
}

SERVICES_LIST = [
    "🪪 Водительские удостоверения",
    "🚜 Тракторные права",
    "📄 СТС",
    "📋 ПТС",
    "🏫 Документы автошколы",
    "🏥 Медицинская справка",
    "🎓 Диплом",
]

SERVICE_PHOTOS = {
    "s_vu":      "https://i.postimg.cc/k5CxL9DX/1.png",
    "s_traktor": "https://i.postimg.cc/XvgwbhyV/2.png",
    "s_sts":     "https://i.postimg.cc/KY5n2Vgj/3.png",
    "s_pts":     "https://i.postimg.cc/jjhzb9JK/4.png",
    "s_avto":    "https://i.postimg.cc/g0KvW56c/5.png",
    "s_med":     "https://i.postimg.cc/k5yxmZtC/6.png",
}

SERVICE_TEXTS = {
    "s_vu": (
        "🪪 *Водительские удостоверения*\n"
        "━━━━━━━━━━━━━━━━\n"
        "⏱ Срок: *от 7 до 14 дней*\n\n"
        "📎 *Необходимые документы:*\n"
        "› Паспорт\n› Прописка\n› Фото 3x4\n› Фото подписи\n"
        "━━━━━━━━━━━━━━━━\n"
        "📱 @kuznecov_vl"
    ),
    "s_traktor": (
        "🚜 *Тракторные права*\n"
        "━━━━━━━━━━━━━━━━\n"
        "📋 Категории: *A - B - C - D - E - F*\n"
        "⏱ Срок: *до 15 дней*\n\n"
        "📎 *Необходимые документы:*\n"
        "› Паспорт\n› Прописка\n› Фото 3x4\n"
        "━━━━━━━━━━━━━━━━\n"
        "📱 @kuznecov_vl"
    ),
    "s_sts": (
        "📄 *СТС — Свидетельство о регистрации ТС*\n"
        "━━━━━━━━━━━━━━━━\n"
        "⏱ Срок: *от 5 до 10 дней*\n\n"
        "📎 *Необходимые документы:*\n"
        "› Паспорт владельца\n› ПТС автомобиля\n"
        "› Договор купли-продажи\n› Полис ОСАГО\n"
        "› Квитанция госпошлины\n"
        "━━━━━━━━━━━━━━━━\n"
        "📱 @kuznecov_vl"
    ),
    "s_pts": (
        "📋 *ПТС — Паспорт транспортного средства*\n"
        "━━━━━━━━━━━━━━━━\n"
        "⏱ Срок: *от 7 до 14 дней*\n\n"
        "📎 *Необходимые документы:*\n"
        "› Паспорт владельца\n› Прописка\n"
        "› VIN номер автомобиля\n"
        "› Документ о праве собственности\n"
        "› Полис ОСАГО\n› Диагностическая карта\n"
        "━━━━━━━━━━━━━━━━\n"
        "📱 @kuznecov_vl"
    ),
    "s_avto": (
        "🏫 *Документы автошколы*\n"
        "━━━━━━━━━━━━━━━━\n"
        "⏱ Срок: *от 5 до 10 дней*\n\n"
        "📎 *Необходимые документы:*\n"
        "› Паспорт\n› Прописка\n"
        "━━━━━━━━━━━━━━━━\n"
        "📱 @kuznecov_vl"
    ),
    "s_med": (
        "🏥 *Медицинские справки*\n"
        "━━━━━━━━━━━━━━━━\n"
        "⏱ Срок: *от 1 до 3 дней*\n\n"
        "📎 *Необходимые документы:*\n"
        "› Паспорт\n› Прописка\n"
        "━━━━━━━━━━━━━━━━\n"
        "📱 @kuznecov_vl"
    ),
    "s_diplom": (
        "🎓 *Дипломы — Высшее и Среднее образование*\n"
        "━━━━━━━━━━━━━━━━\n"
        "⏱ Срок: *от 7 до 14 дней*\n\n"
        "📎 *Необходимые документы:*\n"
        "› Паспорт\n› Прописка\n› СНИЛС\n› Фото 3x4\n"
        "━━━━━━━━━━━━━━━━\n"
        "📱 @kuznecov_vl"
    ),
}

GREETINGS = [
    "Рад видеть тебя, {name}!",
    "Привет, {name}! Обращайся — помогу!",
    "{name}, добро пожаловать!",
    "Здравствуй, {name}! Готов помочь.",
    "{name}, на связи Владимир Кузнецов!",
]

GIBDD_URL = "https://xn----8sbgbnrbpzfdotgl5e9h.xn--p1ai/"


def escape(text):
    if not text:
        return "—"
    for ch in ["*", "_", "`", "[", "]"]:
        text = text.replace(ch, "")
    return text


def track(action, user_id=None):
    analytics[action] = analytics.get(action, 0) + 1
    if user_id:
        uid = str(user_id)
        if uid not in user_analytics:
            user_analytics[uid] = {}
        user_analytics[uid][action] = user_analytics[uid].get(action, 0) + 1


def get_greeting(name):
    hour = datetime.now().hour
    if 5 <= hour < 12:
        time_g = "Доброе утро"
    elif 12 <= hour < 18:
        time_g = "Добрый день"
    elif 18 <= hour < 23:
        time_g = "Добрый вечер"
    else:
        time_g = "Доброй ночи"
    phrase = random.choice(GREETINGS).format(name=name)
    return phrase + "\n_" + time_g + "!_"


def save_user(tg_id, username, first_name, last_name, ref_by=None, source=None):
    try:
        requests.post(APPS_SCRIPT_URL, json={
            "tg_id": str(tg_id), "username": username,
            "first_name": first_name, "last_name": last_name,
            "ref_by": str(ref_by) if ref_by else "", "source": source or "",
        }, timeout=8)
    except Exception as e:
        logger.error(f"save_user error: {e}")


def save_source(source, tg_id):
    try:
        requests.post(APPS_SCRIPT_URL, json={
            "action": "add_source", "source": source, "tg_id": str(tg_id),
        }, timeout=8)
    except Exception as e:
        logger.error(f"save_source error: {e}")


def get_subscribers():
    try:
        r = requests.get(APPS_SCRIPT_URL + "?action=list", timeout=10)
        return r.json()
    except Exception as e:
        logger.error(f"get_subscribers error: {e}")
        return []


def load_sources():
    try:
        r = requests.get(APPS_SCRIPT_URL + "?action=sources", timeout=10)
        data = r.json()
        source_stats.clear()
        source_stats.update(data)
        logger.info(f"Loaded {len(source_stats)} sources")
    except Exception as e:
        logger.error(f"load_sources error: {e}")


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Услуги", callback_data="services"),
         InlineKeyboardButton("📊 Мой статус", callback_data="my_status")],
        [InlineKeyboardButton("📞 Связаться", callback_data="contact"),
         InlineKeyboardButton("⭐ Отзывы", callback_data="reviews")],
        [InlineKeyboardButton("🔍 Проверить права", callback_data="check_rights")],
        [InlineKeyboardButton("👥 Пригласить друга", callback_data="referral")],
    ])


def order_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Оформить сейчас", url="https://t.me/kuznecov_vl")],
        [InlineKeyboardButton("◀️ Назад", callback_data="services")],
    ])


async def send_service(query, key):
    text = SERVICE_TEXTS.get(key, "")
    photo = SERVICE_PHOTOS.get(key)
    if photo:
        try:
            import telegram
            await query.edit_message_media(
                media=telegram.InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
                reply_markup=order_kb())
            return
        except: pass
    try:
        await query.edit_message_caption(caption=text, parse_mode="Markdown", reply_markup=order_kb())
    except:
        await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=order_kb())


async def show_subs_page(query, page=0):
    subs = get_subscribers()
    total = len(subs)
    per_page = 10
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    page_subs = subs[start:start + per_page]

    text = "👥 Подписчики: " + str(total) + "\n─────────────────\n"
    kb = []
    for i, sub in enumerate(page_subs, start + 1):
        name = escape((sub.get("first_name", "") + " " + sub.get("last_name", "")).strip())
        username = "@" + sub["username"] if sub.get("username") else "—"
        text += str(i) + ". " + name + " | " + username + "\n"
        raw_name = (sub.get("first_name", "") + " " + sub.get("last_name", "")).strip() or "—"
        kb.append([InlineKeyboardButton(str(i) + ". " + raw_name[:18], callback_data="adm_usr_" + str(sub.get("tg_id", "")))])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data="adm_pg_" + str(page - 1)))
    nav.append(InlineKeyboardButton(str(page + 1) + "/" + str(total_pages), callback_data="adm_pg_" + str(page)))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data="adm_pg_" + str(page + 1)))
    kb.append(nav)
    kb.append([InlineKeyboardButton("🔍 Поиск по ID или @username", callback_data="adm_search")])
    kb.append([InlineKeyboardButton("◀️ В меню", callback_data="adm_close")])

    await query.edit_message_text(text + "─────────────────", reply_markup=InlineKeyboardMarkup(kb))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref_by = None
    source = None

    if context.args:
        arg = context.args[0]
        if arg.startswith("SRC_"):
            source = arg.replace("SRC_", "")
            if source not in source_stats:
                source_stats[source] = []
            uid = str(user.id)
            if uid not in source_stats[source]:
                source_stats[source].append(uid)
                asyncio.create_task(asyncio.to_thread(save_source, source, user.id))
        elif arg.startswith("REF_"):
            try:
                ref_by = int(arg.replace("REF_", ""))
                if ref_by != user.id:
                    try:
                        await context.bot.send_message(chat_id=ref_by,
                            text="🎉 По вашей реферальной ссылке пришёл " + user.first_name + "!\n\nКогда он оформит заказ — вы получите кешбэк *5000 руб* 💰",
                            parse_mode="Markdown")
                    except: pass
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(chat_id=admin_id,
                                text="🔗 *Реферал!*\nПришёл: " + user.first_name + " (@" + (user.username or "—") + ") | `" + str(user.id) + "`\nПригласил: `" + str(ref_by) + "`",
                                parse_mode="Markdown")
                        except: pass
            except: pass

    asyncio.create_task(asyncio.to_thread(save_user, user.id, user.username or "", user.first_name or "", user.last_name or "", ref_by, source))

    if context.job_queue:
        if not context.job_queue.get_jobs_by_name("reminder_" + str(user.id)):
            context.job_queue.run_once(reminder_job, when=timedelta(days=1),
                data={"chat_id": user.id, "name": user.first_name}, name="reminder_" + str(user.id))

    greeting = get_greeting(user.first_name)
    caption = (greeting + "\n\nЯ *" + CHARACTER_NAME + "*\n━━━━━━━━━━━━━━━━\n" +
               CHARACTER_DESCRIPTION + "\n━━━━━━━━━━━━━━━━\nВыберите что вас интересует 👇")
    try:
        await update.message.reply_photo(photo=CHARACTER_IMAGE_URL, caption=caption,
            parse_mode="Markdown", reply_markup=main_menu())
    except:
        await update.message.reply_text(caption, parse_mode="Markdown", reply_markup=main_menu())


async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.send_message(chat_id=d["chat_id"],
            text=("👋 " + d["name"] + ", добрый день!\n━━━━━━━━━━━━━━━━\n"
                  "Напоминаем — оформление документов занимает от 7 дней.\n\n"
                  "Успейте подать заявку сейчас!\n━━━━━━━━━━━━━━━━\n📱 @kuznecov_vl"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Оформить сейчас", url="https://t.me/kuznecov_vl")]]))
    except Exception as e:
        logger.error(f"Reminder error: {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    track(query.data, user.id)

    if query.data == "back":
        greeting = get_greeting(user.first_name)
        caption = (greeting + "\n\nЯ *" + CHARACTER_NAME + "*\n━━━━━━━━━━━━━━━━\n" +
                   CHARACTER_DESCRIPTION + "\n━━━━━━━━━━━━━━━━\nВыберите что вас интересует 👇")
        try:
            import telegram
            await query.edit_message_media(
                media=telegram.InputMediaPhoto(media=CHARACTER_IMAGE_URL, caption=caption, parse_mode="Markdown"),
                reply_markup=main_menu())
        except:
            try:
                await query.edit_message_caption(caption=caption, parse_mode="Markdown", reply_markup=main_menu())
            except: pass

    elif query.data == "services":
        kb = [
            [InlineKeyboardButton("🪪 Водительские удостоверения", callback_data="s_vu")],
            [InlineKeyboardButton("🚜 Тракторные права", callback_data="s_traktor")],
            [InlineKeyboardButton("📄 СТС", callback_data="s_sts"),
             InlineKeyboardButton("📋 ПТС", callback_data="s_pts")],
            [InlineKeyboardButton("🏫 Документы автошколы", callback_data="s_avto")],
            [InlineKeyboardButton("🏥 Медицинские справки", callback_data="s_med")],
            [InlineKeyboardButton("🎓 Дипломы", callback_data="s_diplom")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")],
        ]
        await query.edit_message_caption(
            caption="📋 *Услуги Владимира Кузнецова*\n━━━━━━━━━━━━━━━━\nВыберите интересующую услугу:",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data in SERVICE_TEXTS:
        await send_service(query, query.data)

    elif query.data == "my_status":
        uid = str(user.id)
        if uid in user_statuses:
            s = user_statuses[uid]
            status_text = STATUS_LABELS.get(s["status"], s["status"])
            progress = STATUS_PROGRESS.get(s["status"], "")
            await query.edit_message_caption(
                caption=("📊 *Статус вашей заявки*\n━━━━━━━━━━━━━━━━\n"
                    "🗂 Услуга: " + s["service"] + "\n"
                    "📌 Статус: " + status_text + "\n"
                    "📶 Прогресс: `" + progress + "`\n"
                    "🕐 Обновлено: " + s["updated"] + "\n━━━━━━━━━━━━━━━━"),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]]))
        else:
            await query.edit_message_caption(
                caption=("📊 *Статус заявки*\n━━━━━━━━━━━━━━━━\n"
                    "У вас пока нет активных заявок.\n\n"
                    "Оформите заявку — и здесь появится статус!\n━━━━━━━━━━━━━━━━\n📱 @kuznecov_vl"),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✍️ Оформить сейчас", url="https://t.me/kuznecov_vl")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif query.data == "contact":
        await query.edit_message_caption(
            caption=("📞 *Связаться*\n━━━━━━━━━━━━━━━━\n"
                "Напишите напрямую — отвечаем быстро!\n\n"
                "Среднее время ответа: *до 15 минут*\n━━━━━━━━━━━━━━━━"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️ Написать Владимиру Кузнецову", url="https://t.me/kuznecov_vl")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif query.data == "reviews":
        await query.edit_message_caption(
            caption=("⭐ *Отзывы*\n━━━━━━━━━━━━━━━━\n"
                "🤝 Работаю конфиденциально — отзывы показываю лично по запросу.\n\n"
                "Напишите мне 👇\n━━━━━━━━━━━━━━━━"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️ Написать Владимиру Кузнецову", url="https://t.me/kuznecov_vl")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif query.data == "check_rights":
        await query.edit_message_caption(
            caption=("🔍 *Проверка водительских прав*\n━━━━━━━━━━━━━━━━\n"
                "Проверьте подлинность удостоверения\nна официальных сайтах:\n\n"
                "› гос-автоинспекция.net\n"
                "› gibdd.news\n"
                "› госавтоинспекция.org\n━━━━━━━━━━━━━━━━"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 гос-автоинспекция.net", url="https://xn----8sbgbnrbpzfdotgl5e9h.net/")],
                [InlineKeyboardButton("🌐 gibdd.news", url="https://gibdd.news/")],
                [InlineKeyboardButton("🌐 госавтоинспекция.org", url="https://xn--80aebkobnwfcnsfk1e0h.org/")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif query.data == "referral":
        bot_username = (await context.bot.get_me()).username
        ref_link = "https://t.me/" + bot_username + "?start=REF_" + str(user.id)
        await query.edit_message_caption(
            caption=("👥 *Пригласить друга*\n━━━━━━━━━━━━━━━━\n"
                "Поделитесь ссылкой с другом!\n\n"
                "💰 Когда он оформит заказ —\nвы получите *кешбэк 5000 руб*\n"
                "━━━━━━━━━━━━━━━━\n🔗 Ваша ссылка:\n`" + ref_link + "`"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]]))


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа.")
        return ConversationHandler.END
    load_sources()
    kb = [
        [InlineKeyboardButton("📊 Статус клиента", callback_data="adm_status"),
         InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton("👥 Подписчики", callback_data="adm_subs"),
         InlineKeyboardButton("📈 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🔗 Ссылки", callback_data="adm_links")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="adm_close")],
    ]
    await update.message.reply_text("👮 *Админ панель*\n━━━━━━━━━━━━━━━━\nВыберите действие:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_ENTER_USER


async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "adm_close":
        await query.edit_message_text("✅ Панель закрыта.")
        return ConversationHandler.END

    elif query.data == "adm_status":
        await query.edit_message_text("👤 Введите числовой ID клиента:\n\n/cancel — отмена")
        context.user_data["admin_action"] = "status"
        return ADMIN_ENTER_USER

    elif query.data == "adm_broadcast":
        await query.edit_message_text(
            "📢 *Рассылка*\n━━━━━━━━━━━━━━━━\nОтправьте фото или /skip (без фото)\n\n/cancel — отмена",
            parse_mode="Markdown")
        context.user_data["admin_action"] = "broadcast_photo"
        return ADMIN_ENTER_USER

    elif query.data == "adm_subs":
        await show_subs_page(query, 0)
        return ADMIN_ENTER_USER

    elif query.data.startswith("adm_pg_"):
        page = int(query.data.replace("adm_pg_", ""))
        await show_subs_page(query, page)
        return ADMIN_ENTER_USER

    elif query.data.startswith("adm_usr_"):
        tg_id = query.data.replace("adm_usr_", "")
        subs = get_subscribers()
        sub = next((s for s in subs if str(s.get("tg_id", "")) == tg_id), None)
        if not sub:
            await query.edit_message_text("❌ Пользователь не найден.")
            return ADMIN_ENTER_USER
        name = escape((sub.get("first_name", "") + " " + sub.get("last_name", "")).strip() or "—")
        username = "@" + sub["username"] if sub.get("username") else "—"
        source = escape(sub.get("source", "") or "—")
        status = user_statuses.get(tg_id, {})
        status_text = STATUS_LABELS.get(status.get("status", ""), "Нет заявки")
        user_acts = user_analytics.get(tg_id, {})
        acts_text = ""
        if user_acts:
            for act_key, act_count in sorted(user_acts.items(), key=lambda x: x[1], reverse=True)[:8]:
                acts_text += "  › " + ACTION_NAMES.get(act_key, act_key) + ": " + str(act_count) + " раз\n"
        else:
            acts_text = "  Нет данных\n"
        kb = []
        if sub.get("username"):
            kb.append([InlineKeyboardButton("✍️ Написать", url="https://t.me/" + sub["username"])])
        kb.append([InlineKeyboardButton("📊 Изменить статус", callback_data="adm_setstatus_" + tg_id)])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_subs")])
        await query.edit_message_text(
            "👤 " + name + " | " + username + "\n─────────────────\n"
            "ID: " + tg_id + "\nДата: " + str(sub.get("date", "—")) + "\n"
            "Источник: " + source + "\nСтатус: " + status_text + "\n─────────────────\n"
            "Активность:\n" + acts_text + "─────────────────",
            reply_markup=InlineKeyboardMarkup(kb))
        return ADMIN_ENTER_USER

    elif query.data.startswith("adm_setstatus_"):
        tg_id = query.data.replace("adm_setstatus_", "")
        context.user_data["target"] = tg_id
        kb = [[InlineKeyboardButton(s, callback_data="admsvc_" + str(i))] for i, s in enumerate(SERVICES_LIST)]
        kb.append([InlineKeyboardButton("❌ Отмена", callback_data="adm_close")])
        await query.edit_message_text("🗂 Выберите услугу для клиента `" + tg_id + "`:",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return ADMIN_CHOOSE_SERVICE

    elif query.data == "adm_search":
        await query.edit_message_text(
            "🔍 Поиск подписчика\n─────────────────\n"
            "Введите TG ID или @username:\n\n/cancel — отмена")
        context.user_data["admin_action"] = "search_user"
        return ADMIN_ENTER_USER

    elif query.data == "adm_links":
        load_sources()
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        kb = []
        for src in source_stats:
            count = len(source_stats[src])
            kb.append([InlineKeyboardButton("📌 " + src + " — " + str(count) + " чел.", callback_data="adm_lv_" + src)])
        kb.append([InlineKeyboardButton("➕ Создать ссылку", callback_data="adm_link_create")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_close")])
        text = "🔗 *Ссылки для отслеживания*\n━━━━━━━━━━━━━━━━\n"
        text += "Ссылок пока нет.\n\nНажмите кнопку ниже!" if not source_stats else "Всего: *" + str(len(source_stats)) + "*\n\nВыберите ссылку:"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return ADMIN_ENTER_USER

    elif query.data == "adm_link_create":
        await query.edit_message_text(
            "➕ *Создать ссылку*\n━━━━━━━━━━━━━━━━\nВведите название источника:\n_(например: instagram, vk, kanal)_\n\n/cancel — отмена",
            parse_mode="Markdown")
        context.user_data["admin_action"] = "create_link"
        return ADMIN_ENTER_USER

    elif query.data.startswith("adm_lv_"):
        src = query.data.replace("adm_lv_", "")
        bot_info = await context.bot.get_me()
        link = "https://t.me/" + bot_info.username + "?start=SRC_" + src
        count = len(source_stats.get(src, []))
        await query.edit_message_text(
            "📌 *" + src + "*\n━━━━━━━━━━━━━━━━\n"
            "👥 Переходов: *" + str(count) + "* чел.\n\n🔗 Ссылка:\n`" + link + "`\n━━━━━━━━━━━━━━━━\n_Скопируйте и разместите где нужно_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К ссылкам", callback_data="adm_links")]]))
        return ADMIN_ENTER_USER

    elif query.data == "adm_stats":
        subs = get_subscribers()
        sorted_analytics = sorted(analytics.items(), key=lambda x: x[1], reverse=True)
        analytics_text = "".join("  › " + ACTION_NAMES.get(k, k) + ": " + str(v) + " раз\n" for k, v in sorted_analytics[:10])
        src_text = "".join("  › " + s + ": " + str(len(ids)) + " чел.\n" for s, ids in source_stats.items())
        await query.edit_message_text(
            "📈 *Статистика*\n━━━━━━━━━━━━━━━━\n"
            "👥 Подписчиков: *" + str(len(subs)) + "*\n"
            "📊 Активных заявок: *" + str(len(user_statuses)) + "*\n━━━━━━━━━━━━━━━━\n"
            "🔥 *Топ действий:*\n" + (analytics_text or "  Нет данных\n") +
            "━━━━━━━━━━━━━━━━\n🔗 *Источники:*\n" + (src_text or "  Нет данных\n") + "━━━━━━━━━━━━━━━━",
            parse_mode="Markdown")
        return ConversationHandler.END


async def admin_enter_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("admin_action")

    if action == "search_user":
        query_text = update.message.text.strip().replace("@", "")
        subs = get_subscribers()
        sub = next((s for s in subs if str(s.get("tg_id","")) == query_text or s.get("username","").lower() == query_text.lower()), None)
        if not sub:
            await update.message.reply_text("❌ Не найден. Попробуйте другой ID или @username.")
            return ADMIN_ENTER_USER
        tg_id = str(sub.get("tg_id", ""))
        name = escape((sub.get("first_name","") + " " + sub.get("last_name","")).strip() or "—")
        username = "@" + sub["username"] if sub.get("username") else "—"
        source = escape(sub.get("source","") or "—")
        status = user_statuses.get(tg_id, {})
        status_text = STATUS_LABELS.get(status.get("status",""), "Нет заявки")
        user_acts = user_analytics.get(tg_id, {})
        acts_text = ""
        if user_acts:
            for act_key, act_count in sorted(user_acts.items(), key=lambda x: x[1], reverse=True)[:8]:
                acts_text += "  › " + ACTION_NAMES.get(act_key, act_key) + ": " + str(act_count) + " раз\n"
        else:
            acts_text = "  Нет данных\n"
        kb = []
        if sub.get("username"):
            kb.append([InlineKeyboardButton("✍️ Написать", url="https://t.me/" + sub["username"])])
        kb.append([InlineKeyboardButton("📊 Изменить статус", callback_data="adm_setstatus_" + tg_id)])
        kb.append([InlineKeyboardButton("◀️ К подписчикам", callback_data="adm_subs")])
        await update.message.reply_text(
            "👤 " + name + " | " + username + "\n─────────────────\n"
            "ID: " + tg_id + "\nДата: " + str(sub.get("date","—")) + "\n"
            "Источник: " + source + "\nСтатус: " + status_text + "\n─────────────────\n"
            "Активность:\n" + acts_text + "─────────────────",
            reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END

    elif action == "broadcast_photo":
        if update.message.photo:
            context.user_data["broadcast_photo"] = update.message.photo[-1].file_id
            await update.message.reply_text("✅ Фото получено! Напишите текст:\n\n/cancel — отмена")
        else:
            await update.message.reply_text("📝 Напишите текст для рассылки:\n\n/cancel — отмена")
        context.user_data["admin_action"] = "broadcast_text"
        return ADMIN_ENTER_USER

    elif action == "broadcast_text":
        text = update.message.text
        photo = context.user_data.get("broadcast_photo")
        subs = get_subscribers()
        if not subs:
            await update.message.reply_text("❌ Нет подписчиков.")
            return ConversationHandler.END
        msg = await update.message.reply_text("📤 Отправляю " + str(len(subs)) + " подписчикам...")
        success = fail = 0
        for sub in subs:
            try:
                if photo:
                    await context.bot.send_photo(chat_id=int(sub["tg_id"]), photo=photo,
                        caption="📢 *Сообщение от Владимира Кузнецова:*\n━━━━━━━━━━━━━━━━\n" + text,
                        parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=int(sub["tg_id"]),
                        text="📢 *Сообщение от Владимира Кузнецова:*\n━━━━━━━━━━━━━━━━\n" + text,
                        parse_mode="Markdown")
                success += 1
            except: fail += 1
        context.user_data.pop("broadcast_photo", None)
        await msg.edit_text("✅ *Рассылка завершена!*\n\n📨 Отправлено: " + str(success) + "\n❌ Не доставлено: " + str(fail),
            parse_mode="Markdown")
        return ConversationHandler.END

    elif action == "create_link":
        source_name = update.message.text.strip().lower().replace(" ", "_")
        if source_name not in source_stats:
            source_stats[source_name] = []
        bot_info = await context.bot.get_me()
        link = "https://t.me/" + bot_info.username + "?start=SRC_" + source_name
        kb = [[InlineKeyboardButton("◀️ К ссылкам", callback_data="adm_links")]]
        await update.message.reply_text(
            "✅ *Ссылка создана!*\n━━━━━━━━━━━━━━━━\n"
            "📌 Источник: *" + source_name + "*\n"
            "👥 Переходов: *0*\n━━━━━━━━━━━━━━━━\n🔗 Ваша ссылка:\n`" + link + "`\n\n_Скопируйте и разместите где нужно_",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END

    else:
        context.user_data["target"] = update.message.text.strip().replace("@", "")
        kb = [[InlineKeyboardButton(s, callback_data="admsvc_" + str(i))] for i, s in enumerate(SERVICES_LIST)]
        kb.append([InlineKeyboardButton("❌ Отмена", callback_data="adm_close")])
        await update.message.reply_text("✅ Клиент: *" + context.user_data["target"] + "*\n\nВыберите услугу:",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return ADMIN_CHOOSE_SERVICE


async def admin_choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "adm_close":
        await query.edit_message_text("✅ Отменено.")
        return ConversationHandler.END
    idx = int(query.data.replace("admsvc_", ""))
    context.user_data["service"] = SERVICES_LIST[idx]
    kb = [[InlineKeyboardButton(label, callback_data="admsts_" + code)] for label, code in STATUSES]
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="adm_close")])
    await query.edit_message_text("🗂 Услуга: *" + context.user_data["service"] + "*\n\nВыберите статус:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_CHOOSE_STATUS


async def admin_choose_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "adm_close":
        await query.edit_message_text("✅ Отменено.")
        return ConversationHandler.END
    code = query.data.replace("admsts_", "")
    label = STATUS_LABELS.get(code, code)
    progress = STATUS_PROGRESS.get(code, "")
    target = context.user_data["target"]
    service = context.user_data["service"]
    user_statuses[target] = {"service": service, "status": code, "updated": datetime.now().strftime("%d.%m.%Y %H:%M")}
    try:
        chat_id = int(target) if target.isdigit() else target
        await context.bot.send_message(chat_id=chat_id,
            text=("🚔 *Владимир Кузнецов сообщает:*\n━━━━━━━━━━━━━━━━\n"
                  "🗂 Услуга: " + service + "\n📌 Статус: " + label + "\n📶 Прогресс: `" + progress + "`\n"
                  "━━━━━━━━━━━━━━━━\nПо вопросам: @kuznecov_vl"),
            parse_mode="Markdown")
        notify = "✅ Клиент уведомлён!"
    except Exception as e:
        notify = "⚠️ Не удалось уведомить: " + str(e)
    await query.edit_message_text(
        "✅ *Готово!*\n━━━━━━━━━━━━━━━━\n"
        "👤 Клиент: `" + target + "`\n🗂 Услуга: " + service + "\n📌 Статус: " + label + "\n📶 `" + progress + "`\n"
        "━━━━━━━━━━━━━━━━\n" + notify,
        parse_mode="Markdown")
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


async def admin_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("admin_action") == "broadcast_photo":
        context.user_data.pop("broadcast_photo", None)
        context.user_data["admin_action"] = "broadcast_text"
        await update.message.reply_text("📝 Без фото. Напишите текст:\n\n/cancel — отмена")
        return ADMIN_ENTER_USER
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


async def post_init(app):
    load_sources()
    await app.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
        BotCommand("status", "Мой статус"),
    ])
    from telegram import BotCommandScopeChat
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.set_my_commands([
                BotCommand("start", "Главное меню"),
                BotCommand("status", "Мой статус"),
                BotCommand("admin", "Админ панель"),
            ], scope=BotCommandScopeChat(chat_id=admin_id))
        except: pass


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_start),
            CallbackQueryHandler(admin_panel_handler, pattern="^adm_"),
        ],
        states={
            ADMIN_ENTER_USER: [
                MessageHandler(filters.PHOTO, admin_enter_user),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_enter_user),
                CallbackQueryHandler(admin_panel_handler, pattern="^adm_"),
            ],
            ADMIN_CHOOSE_SERVICE: [
                CallbackQueryHandler(admin_choose_service, pattern="^admsvc_"),
                CallbackQueryHandler(admin_choose_service, pattern="^adm_close"),
            ],
            ADMIN_CHOOSE_STATUS: [
                CallbackQueryHandler(admin_choose_status, pattern="^admsts_"),
                CallbackQueryHandler(admin_choose_status, pattern="^adm_close"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin_cancel),
            CommandHandler("skip", admin_skip),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот Владимира запущен ✅")
    app.run_polling(drop_pending_updates=True)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in user_statuses:
        s = user_statuses[uid]
        status_text = STATUS_LABELS.get(s["status"], s["status"])
        progress = STATUS_PROGRESS.get(s["status"], "")
        await update.message.reply_text(
            "📊 *Статус заявки*\n━━━━━━━━━━━━━━━━\n"
            "🗂 Услуга: " + s["service"] + "\n📌 Статус: " + status_text + "\n📶 `" + progress + "`\n🕐 " + s["updated"],
            parse_mode="Markdown")
    else:
        await update.message.reply_text("📊 Активных заявок нет.\n\n📱 @kuznecov_vl")


if __name__ == "__main__":
    main()

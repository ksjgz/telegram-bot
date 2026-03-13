# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN ="8683892648:AAE6Yys3bHvtnDlLWn_voUP7ygJGV7PIFd8"
ADMIN_ID = 6317422525
SUPPORT_USERNAME = "iraq_inhest_bot"
DATA_FILE = "users.json"

DAILY_REWARD_DEFAULT = 5
NORMAL_DAILY_TRANSFER_LIMIT = 30000
AGENT_MIN_TRANSFER = 50000
AGENT_MAX_TRANSFER = 5000000

# 8000 نقطة = 1000 دينار
# 132000 دينار = 100 دولار
DEFAULT_COUNTER_LEVELS = {
    "1": {"reward": 5, "upgrade_cost": 5000},
    "2": {"reward": 10, "upgrade_cost": 10000},
    "3": {"reward": 20, "upgrade_cost": 20000},
    "4": {"reward": 35, "upgrade_cost": 40000},
    "5": {"reward": 50, "upgrade_cost": 0},
}


def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "settings": {
                "agent_price": 100000,
                "counter_levels": DEFAULT_COUNTER_LEVELS
            },
            "users": {}
        }

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "settings" not in data:
            data["settings"] = {}

        if "agent_price" not in data["settings"]:
            data["settings"]["agent_price"] = 100000

        if "counter_levels" not in data["settings"]:
            data["settings"]["counter_levels"] = DEFAULT_COUNTER_LEVELS

        if "users" not in data:
            data["users"] = {}

        return data
    except Exception:
        return {
            "settings": {
                "agent_price": 100000,
                "counter_levels": DEFAULT_COUNTER_LEVELS
            },
            "users": {}
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_str():
    return datetime.now().isoformat()


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def reset_daily_transfer_if_needed(user):
    today = today_str()
    if user.get("transfer_day") != today:
        user["transfer_day"] = today
        user["daily_transfer_used"] = 0


def points_to_dinar(points):
    return int((points / 8000) * 1000)


def dinar_to_dollar(dinar):
    return round(dinar / 1320, 2)


def points_to_dollar(points):
    return dinar_to_dollar(points_to_dinar(points))


def format_points_value(points):
    dinar = points_to_dinar(points)
    dollars = points_to_dollar(points)
    return (
        f"💰 النقاط: {points}\n"
        f"💴 بالدينار: {dinar} د.ع\n"
        f"💵 بالدولار: {dollars}$"
    )


def get_main_keyboard(user_id: int):
    buttons = [
        ["💰 رصيدي", "🎁 المكافأة اليومية"],
        ["⏱ العداد", "📊 أسعار تطوير العداد"],
        ["🔁 تحويل نقاط", "🏷 التقديم على وكالة"],
        ["👥 عرض الوكلاء", "🔗 دعوة الأصدقاء"],
        ["💸 طلب سحب", "🛒 المتجر"],
        ["🧮 حاسبة النقاط", "📞 تواصل مع الدعم"],
    ]

    if user_id == ADMIN_ID:
        buttons.append(["🛠 لوحة المدير"])

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_counter_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🛒 متجر العدادات", "🎁 إهداء عداد"],
            ["⏱ الوقت المتبقي", "📊 أرباح العداد"],
            ["⬆️ تطوير الآن", "🔙 رجوع"],
        ],
        resize_keyboard=True
    )


def get_user(data, user_id, name=""):
    user_id = str(user_id)
    users = data["users"]

    if user_id not in users:
        users[user_id] = {
            "name": name,
            "points": 0,
            "referrals": 0,
            "daily_reward": DAILY_REWARD_DEFAULT,
            "last_daily_claim": "",
            "counter_level": 1,
            "last_counter_claim": now_str(),
            "pending_action": "",
            "is_agent": False,
            "agent_can_receive_points": False,
            "agent_transfer_limit_daily": 500000,
            "transfer_day": today_str(),
            "daily_transfer_used": 0,
            "agent_request_pending": False,
            "agent_name": "",
            "agent_phone": "",
            "agent_contact": "",
            "agent_payment_methods": "",
            "pending_withdraw_request": False,
        }

    if name:
        users[user_id]["name"] = name

    reset_daily_transfer_if_needed(users[user_id])
    return users[user_id]


def find_user_by_id(data, uid):
    return data["users"].get(str(uid))


def get_counter_levels(data):
    return data["settings"]["counter_levels"]


def get_counter_reward(user, data):
    level = str(user.get("counter_level", 1))
    levels = get_counter_levels(data)
    return levels.get(level, levels["1"])["reward"]


def get_counter_upgrade_cost(user, data):
    level = str(user.get("counter_level", 1))
    levels = get_counter_levels(data)
    return levels.get(level, levels["1"])["upgrade_cost"]


def get_next_level_data(user, data):
    current_level = user.get("counter_level", 1)
    next_level = current_level + 1
    levels = get_counter_levels(data)
    return next_level, levels.get(str(next_level))


def check_counter_reward(user, data):
    now = datetime.now()
    last_claim_str = user.get("last_counter_claim")

    if not last_claim_str:
        user["last_counter_claim"] = now.isoformat()
        return False, 0

    try:
        last_claim = datetime.fromisoformat(last_claim_str)
    except Exception:
        user["last_counter_claim"] = now.isoformat()
        return False, 0

    if now - last_claim >= timedelta(hours=24):
        reward = get_counter_reward(user, data)
        user["points"] = user.get("points", 0) + reward
        user["last_counter_claim"] = now.isoformat()
        return True, reward

    return False, 0


def get_counter_time_left(user):
    now = datetime.now()
    last_claim_str = user.get("last_counter_claim")

    if not last_claim_str:
        return "جاهز الآن ✅"

    try:
        last_claim = datetime.fromisoformat(last_claim_str)
    except Exception:
        return "جاهز الآن ✅"

    next_time = last_claim + timedelta(hours=24)
    remaining = next_time - now

    if remaining.total_seconds() <= 0:
        return "جاهز الآن ✅"

    total_seconds = int(remaining.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours} ساعة و {minutes} دقيقة"


def get_daily_reward_time_left(user):
    now = datetime.now()
    last_claim_str = user.get("last_daily_claim", "")

    if not last_claim_str:
        return "جاهزة الآن ✅"

    try:
        last_claim = datetime.fromisoformat(last_claim_str)
    except Exception:
        return "جاهزة الآن ✅"

    next_time = last_claim + timedelta(hours=24)
    remaining = next_time - now

    if remaining.total_seconds() <= 0:
        return "جاهزة الآن ✅"

    total_seconds = int(remaining.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours} ساعة و {minutes} دقيقة"


def claim_daily_reward(user):
    now = datetime.now()
    last_claim_str = user.get("last_daily_claim", "")

    if last_claim_str:
        try:
            last_claim = datetime.fromisoformat(last_claim_str)
            if now - last_claim < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - last_claim)
                total_seconds = int(remaining.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return False, f"⏳ لم يحن وقت المكافأة اليومية بعد.\nالمتبقي: {hours} ساعة و {minutes} دقيقة"
        except Exception:
            pass

    reward = user.get("daily_reward", DAILY_REWARD_DEFAULT)
    user["points"] = user.get("points", 0) + reward
    user["last_daily_claim"] = now.isoformat()
    return True, f"🎁 تم إضافة {reward} نقطة إلى رصيدك."


def clear_pending(user):
    user["pending_action"] = ""


def is_int_text(text):
    try:
        int(text)
        return True
    except Exception:
        return False


def format_user_profile(user, data):
    agent_price = data["settings"].get("agent_price", 100000)
    points = user.get("points", 0)
    dinar = points_to_dinar(points)
    dollars = points_to_dollar(points)

    return (
        f"👤 الاسم: {user.get('name', 'بدون اسم')}\n"
        f"💰 نقاطك الحالية: {points}\n"
        f"💴 رصيدك بالدينار: {dinar} د.ع\n"
        f"💵 رصيدك بالدولار: {dollars}$\n"
        f"👥 عدد الدعوات: {user.get('referrals', 0)}\n"
        f"🎯 مستوى العداد: {user.get('counter_level', 1)}\n"
        f"🎁 نقاط العداد القادمة: {get_counter_reward(user, data)}\n"
        f"⏰ الوقت المتبقي للعداد: {get_counter_time_left(user)}\n"
        f"🎁 وقت المكافأة اليومية: {get_daily_reward_time_left(user)}\n"
        f"🏷 حالة الوكالة: {'وكيل ✅' if user.get('is_agent') else 'ليس وكيل ❌'}\n"
        f"💵 سعر الوكالة الحالي: {agent_price} نقطة\n"
        f"🔁 حد تحويل المستخدم اليومي: {NORMAL_DAILY_TRANSFER_LIMIT}"
    )


def get_counter_panel_text(user, data):
    points = user.get("points", 0)
    dinar = points_to_dinar(points)
    dollars = points_to_dollar(points)
    reward = get_counter_reward(user, data)
    level = user.get("counter_level", 1)
    time_left = get_counter_time_left(user)

    return (
        "╔══════════════╗\n"
        f"💰 نقاطك: {points}\n"
        f"💴 الرصيد بالدينار: {dinar} د.ع\n"
        f"💵 الرصيد بالدولار: {dollars}$\n"
        "╚══════════════╝\n\n"
        "╔══════════════╗\n"
        f"📊 ربح العداد: {reward} نقطة يومياً\n"
        f"⏱ الوقت المتبقي: {time_left}\n"
        f"🎯 مستوى العداد: {level}\n"
        "╚══════════════╝"
    )


def format_counter_prices(data):
    levels = get_counter_levels(data)
    lines = ["📊 أسعار تطوير العداد:\n"]
    ordered = sorted(levels.items(), key=lambda x: int(x[0]))
    for level, info in ordered:
        reward = info["reward"]
        cost = info["upgrade_cost"]
        if cost == 0:
            lines.append(f"المستوى {level}: {reward} نقطة كل 24 ساعة — آخر مستوى ✅")
        else:
            lines.append(f"المستوى {level}: {reward} نقطة كل 24 ساعة — سعر التطوير: {cost}")
    return "\n".join(lines)


def format_agents_list(data):
    agents = []
    for uid, user in data["users"].items():
        if user.get("is_agent"):
            agents.append((uid, user))

    if not agents:
        return "❌ لا يوجد وكلاء معتمدون حالياً."

    lines = ["✅ قائمة الوكلاء المعتمدين:\n"]
    for uid, agent in agents:
        lines.append(
            f"👤 الاسم: {agent.get('agent_name') or agent.get('name', 'بدون اسم')}\n"
            f"📱 الرقم: {agent.get('agent_phone', 'غير مضاف')}\n"
            f"🆔 المعرف/الايدي: {agent.get('agent_contact', 'غير مضاف')}\n"
            f"💳 طرق الدفع: {agent.get('agent_payment_methods', 'غير مضافة')}\n"
            f"🔁 الحد اليومي: {agent.get('agent_transfer_limit_daily', 0)}\n"
            f"📥 استلام النقاط: {'مسموح' if agent.get('agent_can_receive_points') else 'ممنوع'}\n"
            "--------------------"
        )
    return "\n".join(lines)


async def admin_panel(update, data):
    total_users = len(data["users"])
    total_points = sum(u.get("points", 0) for u in data["users"].values())
    agent_count = sum(1 for u in data["users"].values() if u.get("is_agent"))
    pending_agents = sum(1 for u in data["users"].values() if u.get("agent_request_pending"))
    agent_price = data["settings"].get("agent_price", 100000)

    msg = (
        "🛠 لوحة المدير المخفية\n\n"
        "مرحباً بك في لوحة تحكم المدير 👑\n\n"
        "📊 الإحصائيات:\n"
        f"• 👥 عدد المستخدمين: {total_users}\n"
        f"• 💰 مجموع النقاط: {total_points}\n"
        f"• 🏷 عدد الوكلاء: {agent_count}\n"
        f"• 📥 طلبات الوكالة المعلقة: {pending_agents}\n"
        f"• 💵 سعر الوكالة الحالي: {agent_price}\n\n"
        "⚙️ أوامر الإدارة:\n"
        "• سعر الوكالة\n"
        "• مراجعة طلبات الوكالة\n"
        "• منح وكالة\n"
        "• سحب وكالة\n"
        "• حد الوكيل\n"
        "• صلاحية الوكيل\n"
        "• أسعار العدادات\n"
        "• رسالة جماعية\n"
        "• إضافة نقاط\n"
        "• خصم نقاط\n\n"
        "🔒 هذه اللوحة تظهر للمدير فقط."
    )
    await update.message.reply_text(msg)


async def handle_transfer_request(update, sender, data):
    sender_id = str(update.effective_user.id)
    reset_daily_transfer_if_needed(sender)

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) != 2:
        await update.message.reply_text(
            "❌ أرسل هكذا:\n"
            "ايدي_المستخدم المبلغ\n\n"
            "مثال:\n"
            "123456789 20000"
        )
        return

    target_id, amount_text = parts

    if not amount_text.isdigit():
        await update.message.reply_text("❌ المبلغ يجب أن يكون رقم فقط.")
        return

    amount = int(amount_text)
    target = find_user_by_id(data, target_id)

    if not target:
        await update.message.reply_text("❌ المستخدم المستلم غير موجود داخل البوت.")
        return

    if target_id == sender_id:
        await update.message.reply_text("❌ لا يمكنك التحويل إلى نفسك.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من صفر.")
        return

    if sender.get("points", 0) < amount:
        await update.message.reply_text("❌ ليس لديك نقاط كافية.")
        return

    sender_is_agent = sender.get("is_agent", False)
    target_is_agent = target.get("is_agent", False)

    if not sender_is_agent:
        if target_is_agent:
            if not target.get("agent_can_receive_points", False):
                await update.message.reply_text("❌ هذا الوكيل غير مسموح له باستلام النقاط حالياً.")
                return
            if amount < AGENT_MIN_TRANSFER or amount > AGENT_MAX_TRANSFER:
                await update.message.reply_text(
                    f"❌ التحويل إلى الوكيل يجب أن يكون بين {AGENT_MIN_TRANSFER} و {AGENT_MAX_TRANSFER} نقطة."
                )
                return
        else:
            used = sender.get("daily_transfer_used", 0)
            if used + amount > NORMAL_DAILY_TRANSFER_LIMIT:
                left = NORMAL_DAILY_TRANSFER_LIMIT - used
                if left < 0:
                    left = 0
                await update.message.reply_text(
                    f"❌ تجاوزت الحد اليومي للمستخدم العادي.\n"
                    f"المتبقي لك اليوم: {left} نقطة."
                )
                return
    else:
        agent_limit = sender.get("agent_transfer_limit_daily", 500000)
        used = sender.get("daily_transfer_used", 0)
        if used + amount > agent_limit:
            left = agent_limit - used
            if left < 0:
                left = 0
            await update.message.reply_text(
                f"❌ تجاوزت الحد اليومي للوكيل.\n"
                f"المتبقي لك اليوم: {left} نقطة."
            )
            return

    sender["points"] -= amount
    target["points"] = target.get("points", 0) + amount
    sender["daily_transfer_used"] = sender.get("daily_transfer_used", 0) + amount
    clear_pending(sender)

    await update.message.reply_text(
        f"✅ تم تحويل {amount} نقطة بنجاح.\n"
        f"💰 نقاطك الحالية: {sender.get('points', 0)}"
    )


async def handle_admin_actions(update, context, admin_user, data):
    text = update.message.text.strip()
    action = admin_user.get("pending_action", "")

    if action == "set_agent_price":
        if not is_int_text(text):
            await update.message.reply_text("❌ أرسل رقم فقط.")
            return
        price = int(text)
        if price <= 0:
            await update.message.reply_text("❌ السعر يجب أن يكون أكبر من صفر.")
            return
        data["settings"]["agent_price"] = price
        clear_pending(admin_user)
        await update.message.reply_text(f"✅ تم تحديث سعر الوكالة إلى {price} نقطة.")
        return

    if action == "grant_agent":
        if not is_int_text(text):
            await update.message.reply_text("❌ أرسل ايدي المستخدم فقط.")
            return
        target = find_user_by_id(data, text)
        if not target:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            return
        target["is_agent"] = True
        target["agent_can_receive_points"] = True
        target["agent_request_pending"] = False
        if not target.get("agent_transfer_limit_daily"):
            target["agent_transfer_limit_daily"] = 500000
        clear_pending(admin_user)
        await update.message.reply_text("✅ تم منح الوكالة بنجاح.")
        try:
            await context.bot.send_message(
                chat_id=int(text),
                text="✅ تمت الموافقة على طلب الوكالة الخاص بك."
            )
        except Exception:
            pass
        return

    if action == "remove_agent":
        if not is_int_text(text):
            await update.message.reply_text("❌ أرسل ايدي المستخدم فقط.")
            return
        target = find_user_by_id(data, text)
        if not target:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            return
        target["is_agent"] = False
        target["agent_can_receive_points"] = False
        clear_pending(admin_user)
        await update.message.reply_text("✅ تم سحب الوكالة.")
        return

    if action == "set_agent_limit":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ أرسل هكذا:\nايدي_الوكيل الحد_اليومي")
            return

        uid, limit_text = parts
        if not uid.isdigit() or not limit_text.isdigit():
            await update.message.reply_text("❌ الايدي والحد يجب أن يكونا أرقام.")
            return

        target = find_user_by_id(data, uid)
        if not target:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            return

        if not target.get("is_agent"):
            await update.message.reply_text("❌ هذا المستخدم ليس وكيلاً.")
            return

        limit_value = int(limit_text)
        if limit_value <= 0:
            await update.message.reply_text("❌ الحد يجب أن يكون أكبر من صفر.")
            return

        target["agent_transfer_limit_daily"] = limit_value
        clear_pending(admin_user)
        await update.message.reply_text(f"✅ تم تحديث حد الوكيل اليومي إلى {limit_value}.")
        return

    if action == "set_agent_permission":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ أرسل هكذا:\n"
                "ايدي_الوكيل 1\n"
                "أو\n"
                "ايدي_الوكيل 0"
            )
            return

        uid, flag = parts
        if not uid.isdigit() or flag not in ["0", "1"]:
            await update.message.reply_text("❌ البيانات غير صحيحة.")
            return

        target = find_user_by_id(data, uid)
        if not target:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            return

        if not target.get("is_agent"):
            await update.message.reply_text("❌ هذا المستخدم ليس وكيلاً.")
            return

        target["agent_can_receive_points"] = flag == "1"
        clear_pending(admin_user)
        await update.message.reply_text(
            f"✅ تم تحديث صلاحية استلام الوكيل إلى: {'مسموح' if flag == '1' else 'ممنوع'}"
        )
        return

    if action == "broadcast":
        count = 0
        for uid in data["users"]:
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"📢 رسالة من الإدارة:\n\n{text}"
                )
                count += 1
            except Exception:
                pass
        clear_pending(admin_user)
        await update.message.reply_text(f"✅ تم إرسال الرسالة إلى {count} مستخدم.")
        return

    if action == "set_counter_price":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ أرسل هكذا:\n"
                "رقم_المستوى السعر\n\n"
                "مثال:\n"
                "2 15000"
            )
            return

        level_text, price_text = parts
        if not level_text.isdigit() or not price_text.isdigit():
            await update.message.reply_text("❌ المستوى والسعر يجب أن يكونا أرقام.")
            return

        levels = get_counter_levels(data)
        if level_text not in levels:
            await update.message.reply_text("❌ هذا المستوى غير موجود.")
            return

        new_price = int(price_text)
        if new_price < 0:
            await update.message.reply_text("❌ السعر لا يمكن أن يكون سالب.")
            return

        levels[level_text]["upgrade_cost"] = new_price
        clear_pending(admin_user)
        await update.message.reply_text(
            f"✅ تم تحديث سعر تطوير المستوى {level_text} إلى {new_price} نقطة."
        )
        return

    if action == "add_points":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ أرسل هكذا:\nايدي_المستخدم عدد_النقاط")
            return

        uid, amount_text = parts
        if not uid.isdigit() or not amount_text.isdigit():
            await update.message.reply_text("❌ الايدي والنقاط يجب أن يكونا أرقام.")
            return

        target = find_user_by_id(data, uid)
        if not target:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            return

        amount = int(amount_text)
        if amount <= 0:
            await update.message.reply_text("❌ العدد يجب أن يكون أكبر من صفر.")
            return

        target["points"] = target.get("points", 0) + amount
        clear_pending(admin_user)
        await update.message.reply_text(f"✅ تم إضافة {amount} نقطة للمستخدم {uid}.")
        return

    if action == "remove_points":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ أرسل هكذا:\nايدي_المستخدم عدد_النقاط")
            return

        uid, amount_text = parts
        if not uid.isdigit() or not amount_text.isdigit():
            await update.message.reply_text("❌ الايدي والنقاط يجب أن يكونا أرقام.")
            return

        target = find_user_by_id(data, uid)
        if not target:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            return

        amount = int(amount_text)
        if amount <= 0:
            await update.message.reply_text("❌ العدد يجب أن يكون أكبر من صفر.")
            return

        current_points = target.get("points", 0)
        if amount > current_points:
            amount = current_points

        target["points"] = current_points - amount
        clear_pending(admin_user)
        await update.message.reply_text(f"✅ تم خصم {amount} نقطة من المستخدم {uid}.")
        return


async def handle_withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ هذا الإجراء خاص بالمدير فقط.")
        return

    data = load_data()

    try:
        action, user_id, points_text = query.data.split("|")
        withdraw_points = int(points_text)
    except Exception:
        await query.edit_message_text("❌ بيانات الطلب غير صحيحة.")
        return

    target_user = find_user_by_id(data, user_id)
    if not target_user:
        await query.edit_message_text("❌ المستخدم غير موجود.")
        return

    if action == "approve_withdraw":
        if target_user.get("points", 0) < withdraw_points:
            await query.edit_message_text(
                "❌ لا يمكن قبول الطلب لأن رصيد المستخدم أصبح أقل من المطلوب."
            )
            return

        target_user["points"] -= withdraw_points
        save_data(data)

        await query.edit_message_text(
            f"✅ تم قبول طلب السحب.\n"
            f"🆔 ايدي المستخدم: {user_id}\n"
            f"💰 تم خصم: {withdraw_points} نقطة"
        )

        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=(
                    "✅ تم قبول طلب السحب الخاص بك.\n\n"
                    f"💰 تم خصم {withdraw_points} نقطة من رصيدك."
                )
            )
        except Exception:
            pass

    elif action == "reject_withdraw":
        await query.edit_message_text(
            f"❌ تم رفض طلب السحب.\n"
            f"🆔 ايدي المستخدم: {user_id}\n"
            f"💰 لم يتم خصم أي نقاط."
        )

        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="❌ تم رفض طلب السحب الخاص بك.\nلم يتم خصم أي نقاط."
            )
        except Exception:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    tg_user = update.effective_user
    user = get_user(data, tg_user.id, tg_user.full_name)

    claimed, reward = check_counter_reward(user, data)
    save_data(data)

    msg = f"أهلاً بك {tg_user.full_name} 🌹\n\nاختر من القائمة الرئيسية:"
    if claimed:
        msg = f"✅ تم إضافة {reward} نقاط من العداد تلقائياً.\n\n" + msg

    await update.message.reply_text(
        msg,
        reply_markup=get_main_keyboard(tg_user.id)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    tg_user = update.effective_user

    data = load_data()
    user = get_user(data, tg_user.id, tg_user.full_name)

    claimed, reward = check_counter_reward(user, data)
    auto_msg = ""
    if claimed:
        auto_msg = f"✅ تم إضافة {reward} نقاط من العداد تلقائياً.\n\n"

    if tg_user.id == ADMIN_ID and user.get("pending_action"):
        await handle_admin_actions(update, context, user, data)
        save_data(data)
        return

    if user.get("pending_action") == "transfer_points":
        await handle_transfer_request(update, user, data)
        save_data(data)
        return

    if user.get("pending_action") == "points_calculator":
        if not text.isdigit():
            await update.message.reply_text("❌ أرسل عدد النقاط بالأرقام فقط.")
            save_data(data)
            return

        points = int(text)
        user["pending_action"] = ""
        await update.message.reply_text(
            "📊 قيمة النقاط:\n\n" + format_points_value(points),
            reply_markup=get_main_keyboard(tg_user.id)
        )
        save_data(data)
        return

    if user.get("pending_action") == "withdraw_request":
        parts = [p.strip() for p in text.split("|")]

        if len(parts) != 3:
            await update.message.reply_text(
                "❌ الصيغة غير صحيحة.\n\n"
                "أرسل هكذا:\n"
                "الطريقة | الرقم_او_المعرف | عدد_النقاط"
            )
            save_data(data)
            return

        method, account_info, points_text = parts

        if not points_text.isdigit():
            await update.message.reply_text("❌ عدد النقاط يجب أن يكون رقم فقط.")
            save_data(data)
            return

        withdraw_points = int(points_text)

        if withdraw_points <= 0:
            await update.message.reply_text("❌ عدد النقاط يجب أن يكون أكبر من صفر.")
            save_data(data)
            return

        if user.get("points", 0) < withdraw_points:
            await update.message.reply_text(
                f"❌ ليس لديك نقاط كافية.\n"
                f"💰 نقاطك الحالية: {user.get('points', 0)}"
            )
            save_data(data)
            return

        dinar_value = points_to_dinar(withdraw_points)
        dollar_value = points_to_dollar(withdraw_points)

        user["pending_action"] = ""

        await update.message.reply_text(
            "✅ تم إرسال طلب السحب إلى الإدارة.\n\n"
            f"💰 النقاط: {withdraw_points}\n"
            f"💴 القيمة بالدينار: {dinar_value} د.ع\n"
            f"💵 القيمة بالدولار: {dollar_value}$\n"
            f"💳 الطريقة: {method}\n"
            f"🆔 الرقم/المعرف: {account_info}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ قبول السحب", callback_data=f"approve_withdraw|{tg_user.id}|{withdraw_points}"),
                InlineKeyboardButton("❌ رفض السحب", callback_data=f"reject_withdraw|{tg_user.id}|{withdraw_points}")
            ]
        ])

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📥 طلب سحب جديد\n\n"
                    f"👤 الاسم: {user.get('name', 'بدون اسم')}\n"
                    f"🆔 ايدي المستخدم: {tg_user.id}\n"
                    f"💰 النقاط: {withdraw_points}\n"
                    f"💴 القيمة بالدينار: {dinar_value} د.ع\n"
                    f"💵 القيمة بالدولار: {dollar_value}$\n"
                    f"💳 الطريقة: {method}\n"
                    f"🆔 الرقم/المعرف: {account_info}"
                ),
                reply_markup=keyboard
            )
        except Exception:
            pass

        save_data(data)
        return

    if user.get("pending_action") == "apply_agent_request":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 4:
            await update.message.reply_text(
                "❌ الصيغة غير صحيحة.\n\n"
                "أرسل هكذا:\n"
                "الاسم | الرقم | المعرف | طرق الدفع"
            )
            save_data(data)
            return

        full_name, phone, contact, payment_methods = parts

        user["agent_name"] = full_name
        user["agent_phone"] = phone
        user["agent_contact"] = contact
        user["agent_payment_methods"] = payment_methods
        user["agent_request_pending"] = True
        user["pending_action"] = ""

        await update.message.reply_text(
            "✅ تم إرسال طلب الوكالة إلى الإدارة بنجاح.\n"
            "⏳ انتظر موافقة المدير."
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📥 طلب وكالة جديد\n\n"
                    f"🆔 ايدي المستخدم: {tg_user.id}\n"
                    f"👤 الاسم: {full_name}\n"
                    f"📱 الرقم: {phone}\n"
                    f"🆔 المعرف: {contact}\n"
                    f"💳 طرق الدفع: {payment_methods}\n\n"
                    "لمنحه وكالة استخدم أمر: منح وكالة"
                )
            )
        except Exception:
            pass

        save_data(data)
        return

    if text == "💰 رصيدي":
        msg = (
            f"{auto_msg}"
            f"{get_counter_panel_text(user, data)}\n\n"
            f"👥 عدد الدعوات: {user.get('referrals', 0)}\n"
            f"🏷 حالة الوكالة: {'وكيل ✅' if user.get('is_agent') else 'ليس وكيل ❌'}"
        )
        await update.message.reply_text(
            msg,
            reply_markup=get_main_keyboard(tg_user.id)
        )

    elif text == "🎁 المكافأة اليومية":
        ok, msg = claim_daily_reward(user)
        await update.message.reply_text(auto_msg + msg)

    elif text == "⏱ العداد":
        await update.message.reply_text(
            get_counter_panel_text(user, data),
            reply_markup=get_counter_keyboard()
        )

    elif text == "⏱ الوقت المتبقي":
        await update.message.reply_text(
            f"⏱ الوقت المتبقي للحصول على نقاط العداد:\n{get_counter_time_left(user)}",
            reply_markup=get_counter_keyboard()
        )

    elif text == "📊 أرباح العداد":
        await update.message.reply_text(
            f"📊 أرباح العداد الحالية:\n"
            f"🎯 مستوى العداد: {user.get('counter_level', 1)}\n"
            f"💰 الربح اليومي: {get_counter_reward(user, data)} نقطة كل 24 ساعة",
            reply_markup=get_counter_keyboard()
        )

    elif text == "📊 أسعار تطوير العداد":
        await update.message.reply_text(format_counter_prices(data))

    elif text == "🛒 متجر العدادات":
        await update.message.reply_text(
            format_counter_prices(data),
            reply_markup=get_counter_keyboard()
        )

    elif text == "🎁 إهداء عداد":
        await update.message.reply_text(
            "🎁 إهداء العداد غير مفعّل حالياً.",
            reply_markup=get_counter_keyboard()
        )

    elif text == "🔙 رجوع":
        await update.message.reply_text(
            "تم الرجوع إلى القائمة الرئيسية.",
            reply_markup=get_main_keyboard(tg_user.id)
        )

    elif text == "⏱ تطوير العداد":
        level = user.get("counter_level", 1)
        reward_amount = get_counter_reward(user, data)
        upgrade_cost = get_counter_upgrade_cost(user, data)
        next_level, next_info = get_next_level_data(user, data)

        if upgrade_cost == 0 or next_info is None:
            msg = (
                f"{auto_msg}"
                f"🎯 مستوى العداد الحالي: {level}\n"
                f"🎁 النقاط كل 24 ساعة: {reward_amount}\n"
                "✅ لقد وصلت إلى أعلى مستوى."
            )
        else:
            next_reward = next_info["reward"]
            msg = (
                f"{auto_msg}"
                f"🎯 مستوى العداد الحالي: {level}\n"
                f"🎁 نقاط العداد الحالية: {reward_amount} كل 24 ساعة\n"
                f"⬆️ المستوى التالي: {next_level}\n"
                f"🎁 نقاط المستوى التالي: {next_reward} كل 24 ساعة\n"
                f"💸 سعر التطوير: {upgrade_cost} نقطة\n\n"
                "للتطوير أرسل:\n"
                "⬆️ تطوير الآن"
            )
        await update.message.reply_text(msg)

    elif text == "⬆️ تطوير الآن":
        level = user.get("counter_level", 1)
        cost = get_counter_upgrade_cost(user, data)
        next_level, next_info = get_next_level_data(user, data)

        if cost == 0 or next_info is None:
            await update.message.reply_text("✅ العداد لديك في أعلى مستوى بالفعل.")
        elif user.get("points", 0) < cost:
            await update.message.reply_text(
                f"❌ نقاطك غير كافية.\n"
                f"سعر التطوير: {cost}\n"
                f"نقاطك الحالية: {user.get('points', 0)}"
            )
        else:
            user["points"] -= cost
            user["counter_level"] = level + 1
            await update.message.reply_text(
                f"✅ تم تطوير العداد إلى المستوى {user['counter_level']}.\n"
                f"🎁 سيعطيك الآن {get_counter_reward(user, data)} نقطة كل 24 ساعة.\n"
                f"💰 نقاطك الحالية: {user.get('points', 0)}"
            )

    elif text == "🔁 تحويل نقاط":
        clear_pending(user)
        user["pending_action"] = "transfer_points"
        reset_daily_transfer_if_needed(user)

        if user.get("is_agent"):
            limit = user.get("agent_transfer_limit_daily", 500000)
            used = user.get("daily_transfer_used", 0)
            left = max(0, limit - used)
            msg = (
                "🔁 تحويل نقاط\n\n"
                "أرسل بالشكل التالي:\n"
                "ايدي_المستخدم المبلغ\n\n"
                f"حدك اليومي كوكيل: {limit}\n"
                f"المتبقي لك اليوم: {left}"
            )
        else:
            used = user.get("daily_transfer_used", 0)
            left = max(0, NORMAL_DAILY_TRANSFER_LIMIT - used)
            msg = (
                "🔁 تحويل نقاط\n\n"
                "أرسل بالشكل التالي:\n"
                "ايدي_المستخدم المبلغ\n\n"
                f"حد المستخدم العادي اليومي: {NORMAL_DAILY_TRANSFER_LIMIT}\n"
                f"المتبقي لك اليوم: {left}\n\n"
                f"التحويل إلى الوكيل يجب أن يكون بين {AGENT_MIN_TRANSFER} و {AGENT_MAX_TRANSFER}"
            )

        await update.message.reply_text(msg)

    elif text == "🏷 التقديم على وكالة":
        if user.get("is_agent"):
            await update.message.reply_text("✅ أنت وكيل معتمد بالفعل.")
        elif user.get("agent_request_pending"):
            await update.message.reply_text("⏳ لديك طلب وكالة قيد المراجعة من قبل الإدارة.")
        else:
            user["pending_action"] = "apply_agent_request"
            await update.message.reply_text(
                "📋 للتقديم على الوكالة أرسل معلوماتك بهذا الشكل:\n\n"
                "الاسم | الرقم | المعرف | طرق الدفع\n\n"
                "مثال:\n"
                "محمد علي | 07701234567 | @mohammed_agent | زين كاش، ماستر كارد، Binance"
            )

    elif text == "👥 عرض الوكلاء":
        await update.message.reply_text(format_agents_list(data))

    elif text == "🔗 دعوة الأصدقاء":
        bot_username = context.bot.username
        invite_link = f"https://t.me/{bot_username}?start={tg_user.id}"
        await update.message.reply_text(
            f"👥 رابط الدعوة الخاص بك:\n{invite_link}\n\n"
            f"عدد الأشخاص الذين دعوتهم: {user.get('referrals', 0)}"
        )

    elif text == "💸 طلب سحب":
        user["pending_action"] = "withdraw_request"
        await update.message.reply_text(
            "💸 طلب سحب\n\n"
            "طرق السحب المتاحة:\n"
            "- زين كاش\n"
            "- ماستر كارد\n"
            "- Binance\n"
            "- OKX\n\n"
            "أرسل الطلب بهذا الشكل:\n"
            "الطريقة | الرقم_او_المعرف | عدد_النقاط\n\n"
            "مثال:\n"
            "زين كاش | 07701234567 | 80000"
        )

    elif text == "🛒 المتجر":
        await update.message.reply_text(
            "🛒 المتجر\n"
            "يمكن للمستخدم طلب شراء الخدمات، والموافقة تكون يدوية من الإدارة."
        )

    elif text == "🧮 حاسبة النقاط":
        user["pending_action"] = "points_calculator"
        await update.message.reply_text(
            "🧮 حاسبة النقاط\n\n"
            "أرسل عدد النقاط فقط.\n\n"
            "مثال:\n"
            "8000"
        )

    elif text == "📞 تواصل مع الدعم":
        await update.message.reply_text(f"📞 الدعم: @{SUPPORT_USERNAME}")

    elif text == "🛠 لوحة المدير":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذه اللوحة خاصة بالمدير فقط.")
        else:
            await admin_panel(update, data)

    elif text == "سعر الوكالة":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "set_agent_price"
            await update.message.reply_text("أرسل سعر الوكالة الجديد بالأرقام فقط.")

    elif text == "مراجعة طلبات الوكالة":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            pending_list = []
            for uid, u in data["users"].items():
                if u.get("agent_request_pending"):
                    pending_list.append(
                        f"🆔 {uid}\n"
                        f"👤 الاسم: {u.get('agent_name', 'غير مضاف')}\n"
                        f"📱 الرقم: {u.get('agent_phone', 'غير مضاف')}\n"
                        f"🆔 المعرف: {u.get('agent_contact', 'غير مضاف')}\n"
                        f"💳 طرق الدفع: {u.get('agent_payment_methods', 'غير مضافة')}\n"
                        "--------------------"
                    )

            if not pending_list:
                await update.message.reply_text("❌ لا توجد طلبات وكالة معلقة.")
            else:
                await update.message.reply_text("📥 طلبات الوكالة المعلقة:\n\n" + "\n".join(pending_list))

    elif text == "منح وكالة":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "grant_agent"
            await update.message.reply_text("أرسل ايدي المستخدم الذي تريد منحه وكالة.")

    elif text == "سحب وكالة":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "remove_agent"
            await update.message.reply_text("أرسل ايدي المستخدم الذي تريد سحب الوكالة منه.")

    elif text == "حد الوكيل":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "set_agent_limit"
            await update.message.reply_text("أرسل بالشكل التالي:\nايدي_الوكيل الحد_اليومي")

    elif text == "صلاحية الوكيل":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "set_agent_permission"
            await update.message.reply_text(
                "أرسل بالشكل التالي:\n"
                "ايدي_الوكيل 1 = سماح\n"
                "ايدي_الوكيل 0 = منع"
            )

    elif text == "رسالة جماعية":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "broadcast"
            await update.message.reply_text("أرسل الآن نص الرسالة الجماعية.")

    elif text == "أسعار العدادات":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "set_counter_price"
            await update.message.reply_text(
                format_counter_prices(data) +
                "\n\nلتغيير السعر أرسل هكذا:\n"
                "رقم_المستوى السعر\n"
                "مثال:\n"
                "2 15000"
            )

    elif text == "إضافة نقاط":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "add_points"
            await update.message.reply_text(
                "أرسل هكذا:\n"
                "ايدي_المستخدم عدد_النقاط\n\n"
                "مثال:\n"
                "123456789 5000"
            )

    elif text == "خصم نقاط":
        if tg_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر خاص بالمدير فقط.")
        else:
            user["pending_action"] = "remove_points"
            await update.message.reply_text(
                "أرسل هكذا:\n"
                "ايدي_المستخدم عدد_النقاط\n\n"
                "مثال:\n"
                "123456789 3000"
            )

    else:
        await update.message.reply_text(
            auto_msg + "اختر زر من القائمة الرئيسية.",
            reply_markup=get_main_keyboard(tg_user.id)
        )

    save_data(data)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_withdraw_callback, pattern="^(approve_withdraw|reject_withdraw)\\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()


import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler
from flask import Flask, request, jsonify
import threading
import sqlite3
import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"

# Токен ЮKassa
YOOKASSA_PROVIDER_TOKEN = "test_WID1Xwp2NqxOeQ82EEEvsDhLI_dEcEGKeLrxr3qTKLk"
YOOKASSA_SHOP_ID = "1212021"

# Цены за подписку
PRICES = {
    "1_month": 15000,
    "3_months": 35000,
    "6_months": 60000,
    "12_months": 100000
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            yookassa_payment_id TEXT,
            tariff TEXT,
            amount INTEGER,
            status TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Функции для работы с БД
def save_payment(user_id, yookassa_payment_id, tariff, amount, email):
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (user_id, yookassa_payment_id, tariff, amount, status, email)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, yookassa_payment_id, tariff, amount, 'pending', email))
    conn.commit()
    conn.close()

def update_payment_status(yookassa_payment_id, status):
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE payments SET status = ? WHERE yookassa_payment_id = ?
    ''', (status, yookassa_payment_id))
    conn.commit()
    conn.close()

# Flask app для вебхуков
app = Flask(__name__)

@app.route('/webhook/yookassa', methods=['POST'])
def yookassa_webhook():
    """Вебхук для уведомлений от ЮKassa"""
    try:
        data = request.json
        logging.info(f"Получен вебхук: {data}")
        
        event = data.get('event')
        payment_data = data.get('object', {})
        payment_id = payment_data.get('id')
        status = payment_data.get('status')
        
        if event == 'payment.waiting_for_capture':
            # Платеж ожидает подтверждения
            update_payment_status(payment_id, 'waiting_for_capture')
            
        elif event == 'payment.succeeded':
            # Платеж успешно завершен
            update_payment_status(payment_id, 'succeeded')
            logging.info(f"Платеж {payment_id} подтвержден через вебхук")
            
        elif event == 'payment.canceled':
            # Платеж отменен
            update_payment_status(payment_id, 'canceled')
            
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logging.error(f"Ошибка в вебхуке: {e}")
        return jsonify({'status': 'error'}), 500

# Запуск Flask в отдельном потоке
def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# Остальные функции бота (start, handle_message и т.д.) остаются без изменений
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    welcome_text = f"""
🔐 <b>Добро пожаловать в VPN Service Bot!</b>

👋 Привет, {user.first_name}!

👇 <b>Выберите тариф для продолжения:</b>
    """
    
    keyboard = [
        [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
        [KeyboardButton("6 месяцев - 600₽"), KeyboardButton("12 месяцев - 1000₽")],
        [KeyboardButton("📞 Поддержка"), KeyboardButton("📖 Инструкция")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    
    if "1 месяц" in text:
        await create_invoice(update, "1_month", "VPN подписка на 1 месяц", "Доступ к VPN на 1 месяц", PRICES["1_month"])
    elif "3 месяца" in text:
        await create_invoice(update, "3_months", "VPN подписка на 3 месяца", "Доступ к VPN на 3 месяца", PRICES["3_months"])
    elif "6 месяцев" in text:
        await create_invoice(update, "6_months", "VPN подписка на 6 месяцев", "Доступ к VPN на 6 месяцев", PRICES["6_months"])
    elif "12 месяцев" in text:
        await create_invoice(update, "12_months", "VPN подписка на 12 месяцев", "Доступ к VPN на 12 месяцев", PRICES["12_months"])
    elif "поддерж" in text.lower() or "📞" in text:
        await support(update, context)
    elif "инструкц" in text.lower() or "📖" in text:
        await instructions(update, context)
    else:
        await start(update, context)

async def create_invoice(update: Update, tariff_id: str, title: str, description: str, price: int):
    try:
        payload = f"vpn_subscription_{tariff_id}"
        currency = "RUB"
        prices = [LabeledPrice(label=title, amount=price)]
        
        await update.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=currency,
            prices=prices,
            need_name=False,
            need_email=True,
            need_phone_number=False,
            need_shipping_address=False,
            is_flexible=False
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при создании платежа: {e}")

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    
    # Сохраняем информацию о платеже
    user_id = query.from_user.id
    email = query.order_info.email if query.order_info else None
    
    # Определяем тариф из payload
    tariff = query.invoice_payload.replace('vpn_subscription_', '')
    amount = PRICES.get(tariff, 0)
    
    save_payment(user_id, 'pending_' + str(user_id), tariff, amount, email)
    
    if query.invoice_payload.startswith('vpn_subscription_'):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Произошла ошибка при обработке платежа")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        payment = update.message.successful_payment
        user = update.message.from_user
        
        # Обновляем статус платежа в БД
        update_payment_status('pending_' + str(user.id), 'succeeded_telegram')
        
        tariff_map = {
            "vpn_subscription_1_month": ("1 месяц", 150),
            "vpn_subscription_3_months": ("3 месяца", 350), 
            "vpn_subscription_6_months": ("6 месяцев", 600),
            "vpn_subscription_12_months": ("12 месяцев", 1000)
        }
        
        tariff_name, tariff_price = tariff_map.get(payment.invoice_payload, ("неизвестный тариф", 0))
        
        vpn_username = f"vpnuser{user.id}"
        vpn_password = generate_password()
        
        success_text = f"""
🎉 <b>Оплата прошла успешно!</b>

✅ <b>Тариф:</b> {tariff_name}
💳 <b>Сумма:</b> {tariff_price} ₽

🔐 <b>Ваши данные для VPN:</b>
├ Логин: <code>{vpn_username}</code>
├ Пароль: <code>{vpn_password}</code>
└ Срок действия: {tariff_name}

📖 Для инструкции по настройке нажмите "📖 Инструкция"
        """
        
        await update.message.reply_text(success_text, parse_mode='HTML')
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при обработке платежа: {e}")

def generate_password(length=12):
    import string
    import random
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_text = """
📞 <b>Техническая поддержка</b>
📱 <b>Telegram:</b> @o0_Ai_Donna_0o
💬 <b>Напишите нам для быстрого ответа!</b>
    """
    await update.message.reply_text(support_text, parse_mode='HTML')

async def instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instructions_text = """
📖 <b>Инструкция по настройке VPN</b>

🖥 <b>Для Windows/Android/iOS:</b>
1. Скачайте OpenVPN
2. Установите программу
3. Запросите конфиг-файл у поддержки
4. Введите логин и пароль
5. Подключитесь

🔧 <b>Нужна помощь?</b> Нажмите "📞 Поддержка"
    """
    await update.message.reply_text(instructions_text, parse_mode='HTML')

def main():
    try:
        # Запускаем Flask в отдельном потоке
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("support", support))
        application.add_handler(CommandHandler("instructions", instructions))
        
        # Обработчики платежей
        application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
        
        # Обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🟢 Бот запущен с вебхуками!")
        print("🌐 Вебхук работает на порту 5000")
        print("💰 Платежная система готова")
        
        application.run_polling()
        
    except Exception as e:
        print(f"🔴 Ошибка: {e}")
        import time
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()

import os
import logging
import sqlite3
import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токены
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"

# РАБОЧИЕ ТЕСТОВЫЕ ТОКЕНЫ ЮKASSA
YOOKASSA_PROVIDER_TOKENS = [
    "381764678:TEST:42000",  # Основной рабочий токен
    "381764678:TEST:40597",  # Запасной 1
    "381764678:TEST:40870",  # Запасной 2
]

# Текущий токен (будем перебирать если не работает)
CURRENT_PROVIDER_TOKEN = YOOKASSA_PROVIDER_TOKENS[0]

# Цены в копейках
PRICES = {
    "1_month": 14900,    # 149 руб
    "3_months": 39900,   # 399 руб
    "6_months": 69900,   # 699 руб
    "12_months": 119900  # 1199 руб
}

# Инициализация БД
def init_db():
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            tariff TEXT,
            status TEXT,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            yookassa_id TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vpn_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            config_name TEXT,
            config_data TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню как у OutlineVPN"""
    user = update.message.from_user
    
    # Сохраняем пользователя в БД
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username) 
        VALUES (?, ?)
    ''', (user.id, user.username))
    
    # Получаем баланс
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    welcome_text = f"""
🔓 <b>Добро пожаловать в VPN Сервис!</b>

👤 <b>Ваш ID:</b> <code>{user.id}</code>
💳 <b>Баланс:</b> {balance} руб

🚀 <b>Наши преимущества:</b>
• Высокая скорость
• Безлимитный трафик
• Защита данных
• Поддержка 24/7

👇 <b>Выберите действие:</b>
"""
    
    keyboard = [
        [KeyboardButton("💰 Пополнить баланс"), KeyboardButton("🔧 Мои конфиги")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("ℹ️ Помощь")],
        [KeyboardButton("👨‍💻 Поддержка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пополнение баланса"""
    user = update.message.from_user
    
    # Получаем текущий баланс
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    text = f"""
💳 <b>Пополнение баланса</b>

💰 <b>Текущий баланс:</b> {balance} руб

Выберите сумму для пополнения:

🎯 <b>Популярные тарифы:</b>
"""
    
    # Инлайн-клавиатура с тарифами
    keyboard = [
        [
            InlineKeyboardButton("1 месяц - 149₽", callback_data="tariff_1_month"),
            InlineKeyboardButton("3 месяца - 399₽", callback_data="tariff_3_months")
        ],
        [
            InlineKeyboardButton("6 месяцев - 699₽", callback_data="tariff_6_months"),
            InlineKeyboardButton("12 месяцев - 1199₽", callback_data="tariff_12_months")
        ],
        [
            InlineKeyboardButton("💎 Другая сумма", callback_data="custom_amount"),
            InlineKeyboardButton("📊 История платежей", callback_data="payment_history")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_my_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои конфигурации"""
    user_id = update.message.from_user.id
    
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('SELECT config_name, created_date FROM vpn_configs WHERE user_id = ? AND is_active = TRUE', (user_id,))
    configs = cursor.fetchall()
    conn.close()
    
    if configs:
        text = "🔧 <b>Ваши конфигурации:</b>\n\n"
        for i, (name, date) in enumerate(configs, 1):
            text += f"{i}. <b>{name}</b>\n   📅 Создан: {date[:10]}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🆕 Создать конфиг", callback_data="create_config")],
            [InlineKeyboardButton("🗑️ Удалить конфиг", callback_data="delete_config"),
             InlineKeyboardButton("🔄 Обновить", callback_data="refresh_configs")]
        ]
    else:
        text = "🔧 <b>У вас пока нет конфигураций</b>\n\nНажмите кнопку ниже чтобы создать первую конфигурацию!"
        keyboard = [[InlineKeyboardButton("🆕 Создать конфиг", callback_data="create_config")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика"""
    user_id = update.message.from_user.id
    
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    
    # Получаем баланс
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance_result = cursor.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    # Получаем количество конфигов
    cursor.execute('SELECT COUNT(*) FROM vpn_configs WHERE user_id = ? AND is_active = TRUE', (user_id,))
    config_count = cursor.fetchone()[0]
    
    conn.close()
    
    text = f"""
📊 <b>Ваша статистика</b>

👤 <b>ID пользователя:</b> <code>{user_id}</code>
💳 <b>Баланс:</b> {balance} руб
🔧 <b>Активных конфигов:</b> {config_count}

⚡ <b>Использование за месяц:</b>
• Трафик: 0 GB
• Онлайн время: 0 часов
• Подключения: 0

🆓 <b>Тестовый период:</b> Не активен
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_stats"),
         InlineKeyboardButton("📈 Детальная статистика", callback_data="detailed_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    text = """
ℹ️ <b>Помощь и инструкции</b>

📱 <b>Как подключиться:</b>
1. Создайте конфигурацию в разделе "🔧 Мои конфиги"
2. Скачайте файл .ovpn
3. Импортируйте в OpenVPN клиент
4. Введите логин и пароль при подключении

🛠️ <b>Поддерживаемые платформы:</b>
• Windows • macOS • Linux
• Android • iOS • RouterOS

🔧 <b>Клиенты:</b>
• OpenVPN Connect
• Outline Client  
• V2RayN
• Clash

❓ <b>Частые вопросы:</b>
• Как создать конфиг? - Нажмите "🔧 Мои конфиги"
• Как пополнить баланс? - Нажмите "💰 Пополнить баланс"
• Проблемы с подключением? - Напишите в поддержку

👇 Выберите раздел помощи:
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📱 Инструкция", callback_data="help_instructions"),
            InlineKeyboardButton("🛠️ Клиенты", callback_data="help_clients")
        ],
        [
            InlineKeyboardButton("❓ FAQ", callback_data="help_faq"),
            InlineKeyboardButton("🔧 Настройки", callback_data="help_settings")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    text = """
👨‍💻 <b>Техническая поддержка</b>

🕒 <b>Режим работы:</b> 24/7
📧 <b>Email:</b> support@vpnservice.com
👤 <b>Telegram:</b> @o0_Ai_Donna_0o

🔧 <b>Мы помогаем с:</b>
• Настройкой подключения
• Проблемами со скоростью
• Ошибками подключения
• Оплатой и балансом

💬 <b>Напишите нам прямо сейчас!</b>

⚠️ <b>При обращении укажите:</b>
• Ваш ID: <code>{}</code>
• Описание проблемы
• Скриншот ошибки (если есть)
""".format(update.message.from_user.id)
    
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка инлайн-кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith('tariff_'):
        # Обработка выбора тарифа
        tariff = data.replace('tariff_', '')
        tariff_names = {
            '1_month': '1 месяц',
            '3_months': '3 месяца', 
            '6_months': '6 месяцев',
            '12_months': '12 месяцев'
        }
        price = PRICES[tariff]
        
        await create_invoice(query, tariff, f"VPN - {tariff_names[tariff]}", f"Доступ к VPN на {tariff_names[tariff]}", price)
    
    elif data == 'custom_amount':
        await query.edit_message_text(
            "💎 <b>Другая сумма</b>\n\nВведите сумму пополнения в рублях:",
            parse_mode='HTML'
        )
    
    elif data == 'create_config':
        await create_vpn_config(query, user_id)
    
    elif data == 'refresh_configs':
        await handle_my_configs(update, context)
    
    elif data == 'refresh_stats':
        await handle_statistics(update, context)
    
    elif data == 'payment_history':
        await show_payment_history(query, user_id)

async def show_payment_history(query, user_id: int):
    """Показать историю платежей"""
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT amount, tariff, status, payment_date 
        FROM payments 
        WHERE user_id = ? 
        ORDER BY payment_date DESC 
        LIMIT 10
    ''', (user_id,))
    payments = cursor.fetchall()
    conn.close()
    
    if payments:
        text = "📊 <b>История платежей:</b>\n\n"
        for i, (amount, tariff, status, date) in enumerate(payments, 1):
            status_icon = "✅" if status == 'success' else "❌"
            text += f"{i}. {status_icon} {amount} руб - {tariff}\n   📅 {date[:16]}\n\n"
    else:
        text = "📊 <b>История платежей пуста</b>\n\nУ вас еще не было пополнений баланса."
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_balance")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def create_invoice(query, tariff_id: str, title: str, description: str, price: int):
    """Создание инвойса для оплаты"""
    try:
        payload = f"vpn_{tariff_id}_{int(datetime.datetime.now().timestamp())}"
        prices = [LabeledPrice(label=title, amount=price)]
        
        # Пробуем разные токены если текущий не работает
        global CURRENT_PROVIDER_TOKEN
        
        for token in YOOKASSA_PROVIDER_TOKENS:
            try:
                CURRENT_PROVIDER_TOKEN = token
                await query.message.reply_invoice(
                    title=title,
                    description=description,
                    payload=payload,
                    provider_token=CURRENT_PROVIDER_TOKEN,
                    currency="RUB",
                    prices=prices,
                    need_email=True,
                    need_phone_number=False,
                    need_shipping_address=False,
                    send_email_to_provider=False,
                    send_phone_number_to_provider=False
                )
                print(f"✅ Успешно создан инвойс с токеном: {token[:20]}...")
                return
                
            except Exception as e:
                print(f"❌ Токен {token[:20]}... не работает: {e}")
                continue
        
        # Если ни один токен не сработал
        raise Exception("Все тестовые токены не работают. Проверьте настройки ЮKassa.")
        
    except Exception as e:
        error_msg = f"❌ Ошибка при создании платежа: {str(e)}"
        print(error_msg)
        await query.message.reply_text(
            "❌ <b>Временная проблема с платежами</b>\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку: @o0_Ai_Donna_0o",
            parse_mode='HTML'
        )

async def create_vpn_config(query, user_id: int):
    """Создание VPN конфигурации"""
    try:
        # Проверяем баланс
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = cursor.fetchone()[0]
        conn.close()
        
        if balance <= 0:
            await query.edit_message_text(
                "❌ <b>Недостаточно средств!</b>\n\n"
                "Для создания конфигурации необходимо пополнить баланс.\n"
                "Минимальная сумма: 149 руб (1 месяц)",
                parse_mode='HTML'
            )
            return
        
        # Генерируем уникальные данные
        config_name = f"config_{user_id}_{int(datetime.datetime.now().timestamp())}"
        vpn_username = f"user{user_id}"
        vpn_password = generate_password()
        
        # Сохраняем в БД
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vpn_configs (user_id, config_name, config_data)
            VALUES (?, ?, ?)
        ''', (user_id, config_name, f"username:{vpn_username},password:{vpn_password}"))
        conn.commit()
        conn.close()
        
        success_text = f"""
✅ <b>Конфигурация создана!</b>

📁 <b>Имя:</b> {config_name}
👤 <b>Логин:</b> <code>{vpn_username}</code>
🔐 <b>Пароль:</b> <code>{vpn_password}</code>

📥 <b>Для получения конфиг-файла:</b>
Обратитесь в поддержку - @o0_Ai_Donna_0o

💡 <b>Сохраните эти данные!</b>
"""
        await query.edit_message_text(success_text, parse_mode='HTML')
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка создания конфигурации: {str(e)}")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешного платежа"""
    try:
        payment = update.message.successful_payment
        user = update.message.from_user
        
        # Определяем сумму и тариф
        amount = payment.total_amount // 100  # Переводим в рубли
        tariff = "custom"
        if hasattr(payment, 'invoice_payload') and payment.invoice_payload:
            payload = payment.invoice_payload
            if '1_month' in payload:
                tariff = "1_month"
            elif '3_months' in payload:
                tariff = "3_months"
            elif '6_months' in payload:
                tariff = "6_months"
            elif '12_months' in payload:
                tariff = "12_months"
        
        # Обновляем баланс в БД
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        ''', (amount, user.id))
        
        # Сохраняем платеж
        cursor.execute('''
            INSERT INTO payments (user_id, amount, tariff, status, yookassa_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user.id, amount, tariff, 'success', payment.provider_payment_charge_id))
        
        conn.commit()
        
        # Получаем обновленный баланс
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
        new_balance = cursor.fetchone()[0]
        conn.close()
        
        success_text = f"""
🎉 <b>Платеж успешно завершен!</b>

💳 <b>Сумма:</b> {amount} руб
📧 <b>Email:</b> {payment.order_info.email if payment.order_info and payment.order_info.email else 'не указан'}
✅ <b>Статус:</b> Успешно

💰 <b>Баланс пополнен!</b>
• Было: {new_balance - amount} руб
• Стало: {new_balance} руб

Теперь вы можете создать конфигурацию в разделе "🔧 Мои конфиги"
"""
        await update.message.reply_text(success_text, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки платежа: {str(e)}")

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение платежа"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text
    
    if text == "💰 Пополнить баланс":
        await handle_balance(update, context)
    elif text == "🔧 Мои конфиги":
        await handle_my_configs(update, context)
    elif text == "📊 Статистика":
        await handle_statistics(update, context)
    elif text == "ℹ️ Помощь":
        await handle_help(update, context)
    elif text == "👨‍💻 Поддержка":
        await handle_support(update, context)
    else:
        await start(update, context)

def generate_password(length=12):
    """Генерация пароля"""
    import string
    import random
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def main():
    """Запуск бота"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
        
        print("🟢 VPN Bot запущен!")
        print("💎 Интерфейс как у OutlineVPN")
        print("💰 Тестируем токены ЮKassa...")
        print(f"🔑 Доступно токенов: {len(YOOKASSA_PROVIDER_TOKENS)}")
        print("💳 Тестовые карты: 5555 5555 5555 4444")
        
        application.run_polling()
        
    except Exception as e:
        print(f"🔴 Ошибка: {e}")
        import time
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()

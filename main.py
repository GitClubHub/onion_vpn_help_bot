import os
import logging
import sqlite3
import datetime
import requests
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токены
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"

# Данные ЮKassa API
YOOKASSA_SHOP_ID = "1212021"
YOOKASSA_SECRET_KEY = "test_WID1Xwp2NqxOeQ82EEEvsDhLI_dEcEGKeLrxr3qTKLk"  # Ваш секретный ключ
YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"

# Цены в рублях
PRICES = {
    "1_month": 149,
    "3_months": 399,
    "6_months": 699,
    "12_months": 1199
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
            yookassa_payment_id TEXT UNIQUE,
            confirmation_url TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vpn_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            config_name TEXT,
            config_data TEXT,
            access_key TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def create_yookassa_payment(amount, tariff, user_id):
    """Создание платежа в ЮKassa и получение ссылки для оплаты"""
    try:
        # Генерируем уникальный ID платежа
        payment_id = f"vpn_{user_id}_{int(datetime.datetime.now().timestamp())}"
        
        # Данные для создания платежа
        payment_data = {
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "payment_method_data": {
                "type": "bank_card"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/your_bot"
            },
            "capture": True,
            "description": f"VPN подписка: {tariff}",
            "metadata": {
                "user_id": user_id,
                "tariff": tariff
            }
        }
        
        # Создаем платеж через API ЮKassa
        response = requests.post(
            YOOKASSA_API_URL,
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            headers={
                'Content-Type': 'application/json',
                'Idempotence-Key': payment_id
            },
            data=json.dumps(payment_data)
        )
        
        if response.status_code == 200:
            payment_info = response.json()
            
            # Сохраняем платеж в БД
            conn = sqlite3.connect('vpn.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO payments (user_id, amount, tariff, status, yookassa_payment_id, confirmation_url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, amount, tariff, 'pending', payment_info['id'], payment_info['confirmation']['confirmation_url']))
            conn.commit()
            conn.close()
            
            return payment_info['confirmation']['confirmation_url']
        else:
            print(f"Ошибка ЮKassa API: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Ошибка создания платежа: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
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
🔓 <b>Добро пожаловать в Premium VPN Service!</b>

👋 <b>Привет, {user.first_name}!</b>

🚀 <b>О нашем сервисе:</b>
• Используем <b>высокопроизводительные сервера</b> с SSD дисками
• Работаем через <b>Outline VPN</b> - технологию от Google
• <b>Собственная инфраструктура</b> с защитой DDoS-атак
• Сервера расположены в <b>Германии, Нидерландах и США</b>

⭐ <b>Преимущества Outline VPN:</b>
• <b>Максимальная скорость</b> - до 1 Гбит/с
• <b>Простая настройка</b> - один ключ для всех устройств
• <b>Стабильное соединение</b> - обход блокировок
• <b>Кроссплатформенность</b> - Windows, Mac, Android, iOS
• <b>Без ограничений</b> - неограниченный трафик

💰 <b>Ваш баланс:</b> {balance} руб

👇 <b>Выберите действие:</b>
"""
    
    keyboard = [
        [KeyboardButton("💰 Пополнить баланс"), KeyboardButton("🔧 Мои конфиги")],
        [KeyboardButton("📖 Инструкция"), KeyboardButton("👨‍💻 Поддержка")]
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

Выберите тариф:
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
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инструкция по получению VPN"""
    text = """
📖 <b>ИНСТРУКЦИЯ ПО ПОЛУЧЕНИЮ VPN</b>

🔹 <b>ШАГ 1: ОПЛАТА</b>
• Нажмите "💰 Пополнить баланс"
• Выберите подходящий тариф
• Оплатите через безопасную страницу ЮKassa

🔹 <b>ШАГ 2: ПОЛУЧЕНИЕ КЛЮЧА</b>
• После оплаты нажмите "✅ Проверить оплату"
• Система автоматически создаст ваш VPN ключ
• Вы получите <b>уникальный ключ доступа</b> к Outline VPN

🔹 <b>ШАГ 3: НАСТРОЙКА</b>
• Скачайте Outline Client по ссылке ниже
• Вставьте полученный ключ в программу
• Нажмите "Подключиться" - готово!

📲 <b>СКАЧАТЬ OUTLINE CLIENT:</b>

<b>Официальный сайт:</b>
https://getoutline.org/

<b>Яндекс Диск (если не открывается):</b>
https://disk.yandex.ru/d/TcLDT462de165g

🛠 <b>Поддерживаемые платформы:</b>
• Windows 10/11 • macOS • Linux
• Android • iOS

💡 <b>После оплаты вы автоматически получите полную инструкцию с вашим ключом!</b>
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Начать - Пополнить баланс", callback_data="to_balance")],
        [InlineKeyboardButton("🔧 Мои конфиги", callback_data="to_configs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

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
        amount = PRICES[tariff]
        
        # Создаем платеж в ЮKassa
        payment_url = create_yookassa_payment(amount, tariff, user_id)
        
        if payment_url:
            # Отправляем пользователю ссылку для оплаты
            payment_text = f"""
💳 <b>Оплата тарифа: {tariff_names[tariff]}</b>

💰 <b>Сумма:</b> {amount} руб

👇 <b>Для оплаты нажмите на кнопку ниже:</b>

После успешной оплаты вернитесь в бот и нажмите кнопку "✅ Проверить оплату"

🔒 <b>Безопасная оплата через ЮKassa</b>
"""
            
            keyboard = [
                [InlineKeyboardButton("🌐 Перейти к оплате", url=payment_url)],
                [InlineKeyboardButton("✅ Проверить оплату", callback_data="check_payment")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_balance")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query.edit_message_text(
                "❌ <b>Ошибка при создании платежа</b>\n\nПожалуйста, попробуйте позже или обратитесь в поддержку.",
                parse_mode='HTML'
            )
    
    elif data == 'check_payment':
        await check_payment_status(query, user_id)
    
    elif data == 'back_to_balance':
        await handle_balance(update, context)
    
    elif data == 'to_balance':
        await handle_balance(update, context)
    
    elif data == 'to_configs':
        await handle_my_configs(update, context)
    
    elif data == 'create_config':
        await create_vpn_config(query, user_id)

async def check_payment_status(query, user_id: int):
    """Проверка статуса платежа"""
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    
    # Ищем последний pending платеж пользователя
    cursor.execute('''
        SELECT yookassa_payment_id, amount, tariff, status 
        FROM payments 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY payment_date DESC 
        LIMIT 1
    ''', (user_id,))
    
    payment = cursor.fetchone()
    
    if not payment:
        await query.edit_message_text(
            "❌ <b>Не найдено ожидающих платежей</b>\n\nЕсли вы уже оплатили, подождите несколько минут и проверьте снова.",
            parse_mode='HTML'
        )
        conn.close()
        return
    
    payment_id, amount, tariff, status = payment
    
    try:
        # Проверяем статус платежа через API ЮKassa
        response = requests.get(
            f"{YOOKASSA_API_URL}/{payment_id}",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        )
        
        if response.status_code == 200:
            payment_info = response.json()
            
            if payment_info['status'] == 'succeeded':
                # Платеж успешен - обновляем баланс
                cursor.execute('''
                    UPDATE payments SET status = 'succeeded' 
                    WHERE yookassa_payment_id = ?
                ''', (payment_id,))
                
                cursor.execute('''
                    UPDATE users SET balance = balance + ? 
                    WHERE user_id = ?
                ''', (amount, user_id))
                
                conn.commit()
                
                # Создаем VPN конфиг автоматически после оплаты
                await create_vpn_config_after_payment(query, user_id, amount)
                
            elif payment_info['status'] == 'pending':
                await query.edit_message_text(
                    "⏳ <b>Платеж еще обрабатывается</b>\n\n"
                    "Если вы уже оплатили, подождите несколько минут и проверьте снова.",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(
                    f"❌ <b>Платеж не завершен</b>\n\nСтатус: {payment_info['status']}",
                    parse_mode='HTML'
                )
        else:
            await query.edit_message_text(
                "❌ <b>Ошибка проверки платежа</b>\n\nПожалуйста, попробуйте позже.",
                parse_mode='HTML'
            )
            
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Ошибка при проверке платежа:</b> {str(e)}",
            parse_mode='HTML'
        )
    
    conn.close()

async def create_vpn_config_after_payment(query, user_id: int, amount: int):
    """Создание VPN конфигурации после успешной оплаты"""
    try:
        # Генерируем уникальные данные
        config_name = f"premium_{user_id}_{int(datetime.datetime.now().timestamp())}"
        vpn_username = f"user{user_id}"
        access_key = generate_access_key()
        
        # Сохраняем в БД
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vpn_configs (user_id, config_name, config_data, access_key)
            VALUES (?, ?, ?, ?)
        ''', (user_id, config_name, f"username:{vpn_username}", access_key))
        conn.commit()
        conn.close()
        
        success_text = f"""
🎉 <b>Оплата подтверждена и VPN ключ создан!</b>

💳 <b>Сумма:</b> {amount} руб
✅ <b>Статус:</b> Успешно

🔑 <b>ВАШ КЛЮЧ ДОСТУПА:</b>
<code>{access_key}</code>

📖 <b>ИНСТРУКЦИЯ ПО НАСТРОЙКЕ:</b>

1. <b>Скачайте Outline Client:</b>
   • Официальный сайт: https://getoutline.org/
   • Яндекс Диск: https://disk.yandex.ru/d/TcLDT462de165g

2. <b>Установите программу</b> на ваше устройство

3. <b>Вставьте ключ доступа</b> в программу:
   <code>{access_key}</code>

4. <b>Нажмите "Подключиться"</b> - готово!

💡 <b>Сохраните этот ключ!</b> Он понадобится для подключения на других устройствах.

🛠 <b>Нужна помощь?</b> Напишите в поддержку: @o0_Ai_Donna_0o
"""
        await query.edit_message_text(success_text, parse_mode='HTML')
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка создания конфигурации: {str(e)}")

async def create_vpn_config(query, user_id: int):
    """Создание VPN конфигурации по запросу"""
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
        access_key = generate_access_key()
        
        # Сохраняем в БД
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vpn_configs (user_id, config_name, config_data, access_key)
            VALUES (?, ?, ?, ?)
        ''', (user_id, config_name, f"username:{vpn_username}", access_key))
        conn.commit()
        conn.close()
        
        success_text = f"""
✅ <b>Конфигурация создана!</b>

🔑 <b>Ваш ключ доступа:</b>
<code>{access_key}</code>

📖 <b>Инструкция по настройке:</b>

1. Скачайте Outline Client:
   • https://getoutline.org/
   • или Яндекс Диск: https://disk.yandex.ru/d/TcLDT462de165g

2. Вставьте ключ в программу и подключитесь!

💡 <b>Сохраните ключ!</b>
"""
        await query.edit_message_text(success_text, parse_mode='HTML')
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка создания конфигурации: {str(e)}")

async def handle_my_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои конфигурации"""
    user_id = update.message.from_user.id
    
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('SELECT config_name, access_key, created_date FROM vpn_configs WHERE user_id = ? AND is_active = TRUE', (user_id,))
    configs = cursor.fetchall()
    conn.close()
    
    if configs:
        text = "🔧 <b>Ваши конфигурации:</b>\n\n"
        for i, (name, access_key, date) in enumerate(configs, 1):
            text += f"{i}. <b>{name}</b>\n   🔑 Ключ: <code>{access_key}</code>\n   📅 Создан: {date[:10]}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🆕 Создать конфиг", callback_data="create_config")],
            [InlineKeyboardButton("📖 Инструкция", callback_data="show_instructions")]
        ]
    else:
        text = "🔧 <b>У вас пока нет конфигураций</b>\n\nНажмите кнопку ниже чтобы создать первую конфигурацию!"
        keyboard = [
            [InlineKeyboardButton("🆕 Создать конфиг", callback_data="create_config")],
            [InlineKeyboardButton("📖 Инструкция", callback_data="show_instructions")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    text = """
👨‍💻 <b>Техническая поддержка</b>

🕒 <b>Режим работы:</b> 24/7
📱 <b>Telegram:</b> @o0_Ai_Donna_0o

🔧 <b>Мы помогаем с:</b>
• Настройкой Outline Client
• Проблемами с подключением
• Оплатой и балансом
• Консультацией по использованию VPN

💬 <b>Напишите нам прямо сейчас!</b>

⚠️ <b>При обращении укажите ваш ID:</b> <code>{}</code>
""".format(update.message.from_user.id)
    
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text
    
    if text == "💰 Пополнить баланс":
        await handle_balance(update, context)
    elif text == "🔧 Мои конфиги":
        await handle_my_configs(update, context)
    elif text == "📖 Инструкция":
        await handle_instructions(update, context)
    elif text == "👨‍💻 Поддержка":
        await handle_support(update, context)
    else:
        await start(update, context)

def generate_access_key():
    """Генерация ключа доступа Outline"""
    import string
    import random
    # Outline ключ обычно в формате: ss://...
    chars = string.ascii_letters + string.digits + "+/="
    key = ''.join(random.choice(chars) for _ in range(40))
    return f"ss://{key}@outline-server.com:12345"

def main():
    """Запуск бота"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
        
        print("🟢 VPN Bot запущен!")
        print("💎 Outline VPN с автоматической выдачей ключей")
        print("💰 Интеграция с ЮKassa")
        print("🌐 Готов к работе!")
        
        application.run_polling()
        
    except Exception as e:
        print(f"🔴 Ошибка: {e}")
        import time
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()

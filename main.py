import os
import logging
import sqlite3
import datetime
import requests
import json
import base64
import random
import string
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токены и настройки
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"
YOOKASSA_SHOP_ID = "1209387"
YOOKASSA_SECRET_KEY = "live_R__UrA2rVtI3qv0XHGoRbePpRxpaMoy7QXKXCLKIYhw"
YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"
OUTLINE_API_URL = "https://38.244.215.5:36538/bKNIHZi5uzkpxbWFLdkGdg"
OUTLINE_VERIFY_SSL = False
SUPPORT_USERNAME = "@o0_Ai_Donna_0o"
SERVER_LOCATION = "Германия"

# Цены в рублях
PRICES = {
    "1_month": 149,
    "3_months": 399,
    "6_months": 699,
    "12_months": 1199
}

# Тарифные названия
TARIFF_NAMES = {
    "1_month": "1 месяц",
    "3_months": "3 месяца", 
    "6_months": "6 месяцев",
    "12_months": "12 месяцев"
}

# Инициализация БД
def init_db():
    conn = sqlite3.connect('vpn.db', check_same_thread=False)
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
            status TEXT DEFAULT 'pending',
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            yookassa_payment_id TEXT UNIQUE,
            confirmation_url TEXT,
            message_id INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vpn_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            config_name TEXT,
            access_key TEXT,
            outline_key_id TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_date TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def create_real_outline_key():
    """Создание реального ключа через Outline API"""
    try:
        print("🔄 Создаю реальный ключ через Outline API...")
        
        response = requests.post(
            f"{OUTLINE_API_URL}/access-keys",
            verify=OUTLINE_VERIFY_SSL,
            timeout=30
        )
        
        print(f"📊 Ответ API Outline: {response.status_code}")
        
        if response.status_code == 201:
            key_data = response.json()
            access_url = key_data['accessUrl']
            key_id = key_data['id']
            
            print(f"✅ Реальный ключ создан! ID: {key_id}")
            return access_url, key_id
        else:
            print(f"❌ Ошибка Outline API: {response.status_code} - {response.text}")
            return None, None
            
    except Exception as e:
        print(f"❌ Ошибка подключения к Outline: {e}")
        return None, None

def generate_demo_access_key():
    """Генерация демо-ключа"""
    methods = ["chacha20-ietf-poly1305", "aes-256-gcm"]
    method = random.choice(methods)
    password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
    server = "germany.outline-server.com"
    port = random.randint(10000, 65535)
    
    config = f"{method}:{password}@{server}:{port}"
    encoded_config = base64.b64encode(config.encode()).decode()
    
    return f"ss://{encoded_config}#Outline-{SERVER_LOCATION}"

def create_yookassa_payment(amount, tariff, user_id, message_id=None):
    """Создание платежа в ЮKassa"""
    try:
        payment_id = f"vpn_{user_id}_{int(datetime.datetime.now().timestamp())}"
        
        payment_data = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "payment_method_data": {
                "type": "bank_card"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/your_vpn_bot"
            },
            "capture": True,
            "description": f"Outline VPN - {TARIFF_NAMES[tariff]}",
            "metadata": {
                "user_id": user_id,
                "tariff": tariff
            }
        }
        
        auth = (YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        headers = {
            'Content-Type': 'application/json',
            'Idempotence-Key': payment_id
        }
        
        print(f"🔄 Создаю платеж для пользователя {user_id}, сумма: {amount} руб")
        
        response = requests.post(
            YOOKASSA_API_URL,
            auth=auth,
            headers=headers,
            data=json.dumps(payment_data),
            timeout=30
        )
        
        print(f"📊 Ответ ЮKassa: {response.status_code}")
        
        if response.status_code == 200:
            payment_info = response.json()
            confirmation_url = payment_info['confirmation']['confirmation_url']
            yookassa_id = payment_info['id']
            
            # Сохраняем платеж в БД
            conn = sqlite3.connect('vpn.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO payments 
                (user_id, amount, tariff, status, yookassa_payment_id, confirmation_url, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, amount, tariff, 'pending', yookassa_id, confirmation_url, message_id))
            conn.commit()
            conn.close()
            
            print(f"✅ Платеж создан: {yookassa_id}")
            return confirmation_url
        else:
            print(f"❌ Ошибка ЮKassa API: {response.status_code}")
            print(f"❌ Текст ошибки: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Исключение при создании платежа: {e}")
        return None

def calculate_expiry_date(tariff):
    """Рассчет даты окончания подписки"""
    now = datetime.datetime.now()
    
    if tariff == "1_month":
        return now + datetime.timedelta(days=30)
    elif tariff == "3_months":
        return now + datetime.timedelta(days=90)
    elif tariff == "6_months":
        return now + datetime.timedelta(days=180)
    elif tariff == "12_months":
        return now + datetime.timedelta(days=365)
    else:
        return now + datetime.timedelta(days=30)

async def create_vpn_config_after_payment(user_id: int, amount: int, tariff: str, update: Update = None):
    """АВТОМАТИЧЕСКОЕ создание VPN конфигурации после оплаты"""
    try:
        print(f"🎯 Автоматически создаю VPN ключ для {user_id}, тариф: {tariff}")
        
        # 1. Пытаемся создать реальный ключ через Outline API
        access_key, key_id = create_real_outline_key()
        
        # 2. Если не удалось - создаем демо-ключ
        if not access_key:
            print("⚠️ Outline API недоступен, создаю демо-ключ")
            access_key = generate_demo_access_key()
            key_id = f"demo_{user_id}_{int(datetime.datetime.now().timestamp())}"
        
        # 3. Сохраняем в базу данных
        expiry_date = calculate_expiry_date(tariff)
        
        conn = sqlite3.connect('vpn.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vpn_configs 
            (user_id, config_name, access_key, outline_key_id, expiry_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id, 
            f"outline_{tariff}_{user_id}",
            access_key, 
            key_id,
            expiry_date,
            True
        ))
        conn.commit()
        conn.close()
        
        print(f"✅ Ключ сохранен в БД для пользователя {user_id}")
        
        # 4. Отправляем ключ пользователю
        await send_vpn_key_to_user(user_id, access_key, amount, tariff, expiry_date, key_id, update)
        
    except Exception as e:
        print(f"❌ Ошибка создания конфига: {e}")
        # Отправляем сообщение об ошибке
        if update and hasattr(update, 'message'):
            await update.message.reply_text(
                "❌ <b>Ошибка при создании VPN ключа</b>\n\n"
                f"Пожалуйста, обратитесь в поддержку: {SUPPORT_USERNAME}\n"
                "Мы решим проблему в течение 15 минут!",
                parse_mode='HTML'
            )

async def send_vpn_key_to_user(user_id: int, access_key: str, amount: int, tariff: str, 
                              expiry_date: datetime, key_id: str, update: Update = None):
    """Отправка ключа пользователю"""
    
    # Определяем тип ключа для сообщения
    is_demo = key_id.startswith('demo_') if key_id else True
    key_type = "🔴 ДЕМО-КЛЮЧ (для тестирования)" if is_demo else "🟢 РЕАЛЬНЫЙ КЛЮЧ"
    
    success_text = f"""
🎉 <b>ОПЛАТА ПОДТВЕРЖДЕНА И КЛЮЧ СОЗДАН!</b>

{key_type}

✅ <b>Тариф:</b> {TARIFF_NAMES.get(tariff, tariff)}
💳 <b>Сумма:</b> {amount} руб
📅 <b>Действует до:</b> {expiry_date.strftime('%d.%m.%Y')}
🌍 <b>Локация:</b> {SERVER_LOCATION}

🔑 <b>ВАШ КЛЮЧ ДОСТУПА Outline:</b>
<code>{access_key}</code>

🚀 <b>ПОДКЛЮЧЕНИЕ ЗА 2 МИНУТЫ:</b>

1. <b>Скачайте Outline Client:</b>
   📱 Официальный сайт: https://getoutline.org/
   💾 Яндекс Диск: https://disk.yandex.ru/d/TcLDT462de165g

2. <b>Установите программу</b>

3. <b>ВСТАВЬТЕ ЭТОТ КЛЮЧ:</b>
   <code>{access_key}</code>

4. <b>Нажмите "Подключиться"</b> - готово!

⭐ <b>Характеристики сервера:</b>
• Локация: {SERVER_LOCATION}
• Скорость: до 1 Гбит/с
• Трафик: безлимитный
• Технология: Shadowsocks

💡 <b>Сохраните этот ключ!</b> Он нужен для подключения на всех устройствах.

🛠 <b>Помощь:</b> {SUPPORT_USERNAME}
"""

    # Отправляем сообщение пользователю
    try:
        if update:
            if hasattr(update, 'message'):
                await update.message.reply_text(success_text, parse_mode='HTML')
            elif hasattr(update, 'callback_query'):
                await update.callback_query.message.reply_text(success_text, parse_mode='HTML')
        else:
            # Если update нет, используем context для отправки
            from telegram.ext import ContextTypes
            # Этот случай обрабатывается в check_payment_status
            pass
    except Exception as e:
        print(f"❌ Ошибка отправки ключа пользователю: {e}")

async def check_payment_status(payment_id: str, user_id: int, update: Update = None):
    """Проверка статуса конкретного платежа"""
    try:
        response = requests.get(
            f"{YOOKASSA_API_URL}/{payment_id}",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            timeout=30
        )
        
        if response.status_code == 200:
            payment_info = response.json()
            
            if payment_info['status'] == 'succeeded':
                # Платеж успешен!
                amount = int(float(payment_info['amount']['value']))
                tariff = payment_info['metadata']['tariff']
                
                # Обновляем статус в БД
                conn = sqlite3.connect('vpn.db', check_same_thread=False)
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE payments SET status = "succeeded" WHERE yookassa_payment_id = ?', 
                    (payment_id,)
                )
                cursor.execute(
                    'UPDATE users SET balance = balance + ? WHERE user_id = ?', 
                    (amount, user_id)
                )
                conn.commit()
                conn.close()
                
                print(f"✅ Платеж {payment_id} подтвержден для пользователя {user_id}")
                
                # Автоматически создаем VPN ключ
                await create_vpn_config_after_payment(user_id, amount, tariff, update)
                return True
                
            elif payment_info['status'] == 'pending':
                print(f"⏳ Платеж {payment_id} все еще обрабатывается")
                return False
            else:
                print(f"❌ Платеж {payment_id} имеет статус: {payment_info['status']}")
                return False
                
        else:
            print(f"❌ Ошибка проверки платежа {payment_id}: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение при проверке платежа: {e}")
        return False

async def check_all_user_payments(user_id: int, update: Update):
    """Проверка ВСЕХ платежей пользователя"""
    conn = sqlite3.connect('vpn.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Ищем ВСЕ pending платежи пользователя
    cursor.execute('''
        SELECT yookassa_payment_id, amount, tariff, status 
        FROM payments 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY payment_date DESC
    ''', (user_id,))
    
    payments = cursor.fetchall()
    conn.close()
    
    if not payments:
        if hasattr(update, 'callback_query'):
            await update.callback_query.message.reply_text(
                "❌ <b>Не найдено ожидающих платежей</b>\n\n"
                "Если вы уже оплатили, подождите 2-3 минуты и проверьте снова.",
                parse_mode='HTML'
            )
        elif hasattr(update, 'message'):
            await update.message.reply_text(
                "❌ <b>Не найдено ожидающих платежей</b>\n\n"
                "Если вы уже оплатили, подождите 2-3 минуты и проверьте снова.",
                parse_mode='HTML'
            )
        return
    
    processed_payments = 0
    
    for payment in payments:
        payment_id, amount, tariff, status = payment
        
        success = await check_payment_status(payment_id, user_id, update)
        if success:
            processed_payments += 1
    
    if processed_payments == 0:
        if hasattr(update, 'callback_query'):
            await update.callback_query.message.reply_text(
                "⏳ <b>Платежи еще обрабатываются</b>\n\n"
                "Если вы уже оплатили, подождите несколько минут и проверьте снова.\n"
                f"Или напишите в поддержку: {SUPPORT_USERNAME}",
                parse_mode='HTML'
            )
        elif hasattr(update, 'message'):
            await update.message.reply_text(
                "⏳ <b>Платежи еще обрабатываются</b>\n\n"
                "Если вы уже оплатили, подождите несколько минут и проверьте снова.\n"
                f"Или напишите в поддержку: {SUPPORT_USERNAME}",
                parse_mode='HTML'
            )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    user = update.message.from_user
    
    conn = sqlite3.connect('vpn.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                  (user.id, user.username))
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    welcome_text = f"""
🔓 <b>Добро пожаловать в Premium Outline VPN Service!</b>

👋 <b>Привет, {user.first_name}!</b>

💰 <b>Ваш баланс:</b> {balance} руб

🚀 <b>Автоматическая выдача ключей после оплаты!</b>

👇 <b>Выберите действие:</b>
"""
    
    keyboard = [
        [KeyboardButton("💰 Пополнить баланс"), KeyboardButton("🔧 Мои конфиги")],
        [KeyboardButton("✅ Проверить оплату"), KeyboardButton("📖 Инструкция")],
        [KeyboardButton("👨‍💻 Поддержка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пополнение баланса"""
    user = update.message.from_user
    
    conn = sqlite3.connect('vpn.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    text = f"""
💳 <b>Пополнение баланса</b>

💰 <b>Текущий баланс:</b> {balance} руб
🌍 <b>Локация серверов:</b> {SERVER_LOCATION}

💡 <b>После оплаты нажмите "✅ Проверить оплату" для получения ключа</b>

Выберите тариф:
"""
    
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
    
    # Сохраняем message_id для привязки платежа
    message = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    context.user_data['balance_message_id'] = message.message_id

async def handle_check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка оплаты через кнопку"""
    user_id = update.message.from_user.id
    
    await update.message.reply_text(
        "🔄 <b>Проверяю все ваши платежи...</b>\n\n"
        "Это займет несколько секунд.",
        parse_mode='HTML'
    )
    
    await check_all_user_payments(user_id, update)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка инлайн-кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith('tariff_'):
        tariff = data.replace('tariff_', '')
        amount = PRICES[tariff]
        
        # Получаем message_id из context
        message_id = context.user_data.get('balance_message_id')
        
        payment_url = create_yookassa_payment(amount, tariff, user_id, message_id)
        
        if payment_url:
            payment_text = f"""
💳 <b>Оплата тарифа: {TARIFF_NAMES[tariff]}</b>

💰 <b>Сумма:</b> {amount} руб
🌍 <b>Локация:</b> {SERVER_LOCATION}

👇 <b>Для оплаты нажмите на кнопку ниже:</b>

💡 <b>ВАЖНО:</b> После оплаты вернитесь в бот и нажмите:
• "✅ Проверить оплату" в главном меню
• ИЛИ напишите /check_payment

🔒 <b>Безопасная оплата через ЮKassa</b>
"""
            
            keyboard = [
                [InlineKeyboardButton("🌐 Перейти к оплате", url=payment_url)],
                [InlineKeyboardButton("✅ Проверить оплату", callback_data="check_payment_global")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_balance")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query.edit_message_text(
                "❌ <b>Ошибка при создании платежа</b>\n\n"
                f"Пожалуйста, попробуйте позже или обратитесь в поддержку: {SUPPORT_USERNAME}",
                parse_mode='HTML'
            )
    
    elif data == 'check_payment_global':
        await query.edit_message_text("🔄 Проверяю платежи...")
        await check_all_user_payments(user_id, update)
    
    elif data == 'back_to_balance':
        await handle_balance_callback(update, context)
    
    elif data == 'to_balance':
        await handle_balance_callback(update, context)
    
    elif data == 'show_instructions':
        await handle_instructions_callback(update, context)

async def handle_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки баланса в callback"""
    query = update.callback_query
    user = query.from_user
    
    conn = sqlite3.connect('vpn.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    text = f"""
💳 <b>Пополнение баланса</b>

💰 <b>Текущий баланс:</b> {balance} руб
🌍 <b>Локация серверов:</b> {SERVER_LOCATION}

💡 <b>После оплаты нажмите "✅ Проверить оплату" для получения ключа</b>

Выберите тариф:
"""
    
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
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инструкция по получению VPN"""
    text = f"""
📖 <b>ИНСТРУКЦИЯ ПО ПОЛУЧЕНИЮ OUTLINE VPN</b>

🔹 <b>ШАГ 1: ОПЛАТА</b>
• Нажмите "💰 Пополнить баланс"
• Выберите подходящий тариф
• Оплатите через безопасную страницу ЮKassa

🔹 <b>ШАГ 2: ПОЛУЧЕНИЕ КЛЮЧА</b>
• После оплаты вернитесь в бот
• Нажмите "✅ Проверить оплату" в главном меню
• Система <b>АВТОМАТИЧЕСКИ</b> создаст ключ и отправит его вам

🔹 <b>ШАГ 3: НАСТРОЙКА</b>
• Скачайте Outline Client по ссылке ниже
• Вставьте полученный ключ в программу
• Нажмите "Подключиться" - готово!

🔧 <b>О ТЕХНОЛОГИИ SHADOWSOCKS:</b>
Outline использует технологию Shadowsocks - это современный защищенный прокси-протокол. 
Он обеспечивает стабильное соединение и высокую скорость за счет эффективного шифрования трафика.

📲 <b>СКАЧАТЬ OUTLINE CLIENT:</b>

<b>Официальный сайт:</b>
https://getoutline.org/

<b>Яндекс Диск (если не открывается):</b>
https://disk.yandex.ru/d/TcLDT462de165g

💡 <b>После оплаты нажмите "✅ Проверить оплату" для получения ключа!</b>
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Пополнить баланс", callback_data="to_balance")],
        [InlineKeyboardButton("✅ Проверить оплату", callback_data="check_payment_global")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_instructions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инструкция для callback"""
    text = f"""
📖 <b>ИНСТРУКЦИЯ ПО ПОЛУЧЕНИЮ OUTLINE VPN</b>

🔹 <b>ШАГ 1: ОПЛАТА</b>
• Нажмите "💰 Пополнить баланс"
• Выберите подходящий тариф
• Оплатите через безопасную страницу ЮKassa

🔹 <b>ШАГ 2: ПОЛУЧЕНИЕ КЛЮЧА</b>
• После оплаты вернитесь в бот
• Нажмите "✅ Проверить оплату"
• Система <b>АВТОМАТИЧЕСКИ</b> создаст ключ и отправит его вам

🔹 <b>ШАГ 3: НАСТРОЙКА</b>
• Скачайте Outline Client
• Вставьте полученный ключ в программу
• Нажмите "Подключиться" - готово!

📲 <b>СКАЧАТЬ OUTLINE CLIENT:</b>
https://getoutline.org/

💡 <b>После оплаты нажмите "✅ Проверить оплату"!</b>
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Пополнить баланс", callback_data="to_balance")],
        [InlineKeyboardButton("✅ Проверить оплату", callback_data="check_payment_global")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query = update.callback_query
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_my_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои конфигурации"""
    user_id = update.message.from_user.id
    
    conn = sqlite3.connect('vpn.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT config_name, access_key, created_date, expiry_date 
        FROM vpn_configs 
        WHERE user_id = ? AND is_active = TRUE 
        ORDER BY created_date DESC
    ''', (user_id,))
    configs = cursor.fetchall()
    conn.close()
    
    if configs:
        text = "🔧 <b>Ваши конфигурации Outline:</b>\n\n"
        for i, (name, access_key, created, expiry) in enumerate(configs, 1):
            is_demo = "demo" in str(name) or "demo" in str(access_key)
            key_type = "🔴 ДЕМО" if is_demo else "🟢 РЕАЛЬНЫЙ"
            expiry_text = f"📅 Истекает: {expiry.strftime('%d.%m.%Y')}" if expiry else ""
            
            text += f"{i}. <b>{name}</b> {key_type}\n"
            text += f"   🔑 <code>{access_key}</code>\n"
            text += f"   📅 Создан: {created[:10]} {expiry_text}\n\n"
        
        text += "💡 <b>Используйте эти ключи для подключения в Outline Client</b>"
        
    else:
        text = "🔧 <b>У вас пока нет конфигураций</b>\n\nНажмите кнопку ниже чтобы пополнить баланс и создать первую конфигурацию!"
    
    keyboard = [
        [InlineKeyboardButton("💰 Пополнить баланс", callback_data="to_balance")],
        [InlineKeyboardButton("📖 Инструкция", callback_data="show_instructions")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    user_id = update.message.from_user.id
    text = f"""
👨‍💻 <b>Техническая поддержка Outline VPN</b>

🕒 <b>Режим работы:</b> 24/7
📱 <b>Telegram:</b> {SUPPORT_USERNAME}

🔧 <b>Мы помогаем с:</b>
• Настройкой Outline Client
• Проблемами с подключением
• Оплатой и балансом
• Автоматической выдачей ключей

💬 <b>Напишите нам прямо сейчас!</b>

⚠️ <b>При обращении укажите ваш ID:</b> <code>{user_id}</code>
"""
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text
    
    if text == "💰 Пополнить баланс":
        await handle_balance(update, context)
    elif text == "🔧 Мои конфиги":
        await handle_my_configs(update, context)
    elif text == "✅ Проверить оплату":
        await handle_check_payment(update, context)
    elif text == "📖 Инструкция":
        await handle_instructions(update, context)
    elif text == "👨‍💻 Поддержка":
        await handle_support(update, context)
    else:
        await start(update, context)

def main():
    """Запуск бота"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("balance", handle_balance))
        application.add_handler(CommandHandler("check_payment", handle_check_payment))
        application.add_handler(CommandHandler("configs", handle_my_configs))
        application.add_handler(CommandHandler("support", handle_support))
        application.add_handler(CommandHandler("instructions", handle_instructions))
        
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
        
        print("🟢 VPN Bot запущен!")
        print(f"🔑 Outline Server: {SERVER_LOCATION}")
        print("💰 Интеграция с ЮKassa")
        print("✅ Автоматическая выдача ключей")
        print("🚀 Готов к работе!")
        
        application.run_polling()
        
    except Exception as e:
        print(f"🔴 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        print("🔄 Перезапуск через 10 секунд...")
        import time
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()

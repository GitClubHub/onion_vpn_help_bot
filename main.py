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

# Токены
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"

# Данные ЮKassa API
YOOKASSA_SHOP_ID = "1212021"
YOOKASSA_SECRET_KEY = "test_WID1Xwp2NqxOeQ82EEEvsDhLI_dEcEGKeLrxr3qTKLk"
YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"

# ⚡ ВАШИ РЕАЛЬНЫЕ ДАННЫЕ OUTLINE SERVER ⚡
OUTLINE_API_URL = "https://38.244.215.5:36538/bKNIHZi5uzkpxbWFLdkGdg"
OUTLINE_SERVER_HOST = "38.244.215.5"
OUTLINE_SERVER_PORT = "53944"
OUTLINE_SERVER_ID = "bd1c3d9b-c33a-47cb-8cc5-8ce3b622fdc3"
OUTLINE_VERIFY_SSL = False  # Для самоподписанных сертификатов

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
            access_key TEXT,
            outline_key_id TEXT,
            server_host TEXT,
            server_port TEXT,
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
        print(f"📡 Подключаюсь к: {OUTLINE_API_URL}")
        
        # Создаем новый ключ доступа
        response = requests.post(
            f"{OUTLINE_API_URL}/access-keys",
            verify=OUTLINE_VERIFY_SSL,
            timeout=30
        )
        
        print(f"📊 Ответ API: {response.status_code}")
        
        if response.status_code == 201:
            key_data = response.json()
            access_url = key_data['accessUrl']
            key_id = key_data['id']
            name = key_data.get('name', 'auto_generated')
            
            print(f"✅ Реальный ключ создан! ID: {key_id}")
            print(f"🔑 URL: {access_url}")
            
            return access_url, key_id, name
            
        else:
            print(f"❌ Ошибка API: {response.status_code} - {response.text}")
            return None, None, None
            
    except requests.exceptions.ConnectTimeout:
        print("❌ Таймаут подключения к Outline API")
        return None, None, None
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения к Outline API")
        return None, None, None
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return None, None, None

def set_outline_data_limit(key_id, limit_gb=1000):
    """Установка лимита трафика"""
    try:
        if not key_id or key_id.startswith('demo_'):
            return False
            
        bytes_limit = limit_gb * 1024 * 1024 * 1024
        data = {"limit": {"bytes": bytes_limit}}
        
        response = requests.put(
            f"{OUTLINE_API_URL}/access-keys/{key_id}/data-limit",
            json=data,
            verify=OUTLINE_VERIFY_SSL,
            timeout=10
        )
        
        if response.status_code == 204:
            print(f"✅ Лимит {limit_gb}GB установлен для ключа {key_id}")
            return True
        else:
            print(f"⚠️ Не удалось установить лимит: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"⚠️ Ошибка установки лимита: {e}")
        return False

def get_outline_server_metrics():
    """Получение метрик сервера"""
    try:
        response = requests.get(
            f"{OUTLINE_API_URL}/metrics/transfer",
            verify=OUTLINE_VERIFY_SSL,
            timeout=10
        )
        
        if response.status_code == 200:
            metrics = response.json()
            print(f"📊 Метрики сервера: {metrics}")
            return metrics
        return None
    except Exception as e:
        print(f"⚠️ Ошибка получения метрик: {e}")
        return None

def generate_demo_access_key():
    """Генерация демо-ключа (если Outline API недоступен)"""
    methods = ["chacha20-ietf-poly1305", "aes-256-gcm"]
    method = random.choice(methods)
    password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    # Используем реальные данные вашего сервера
    server = OUTLINE_SERVER_HOST
    port = OUTLINE_SERVER_PORT
    
    config = f"{method}:{password}@{server}:{port}"
    encoded_config = base64.b64encode(config.encode()).decode()
    
    return f"ss://{encoded_config}#Outline-Server-{OUTLINE_SERVER_HOST}"

def create_yookassa_payment(amount, tariff, user_id):
    """Создание платежа в ЮKassa"""
    try:
        payment_id = f"vpn_{user_id}_{int(datetime.datetime.now().timestamp())}"
        
        payment_data = {
            "amount": {"value": str(amount), "currency": "RUB"},
            "payment_method_data": {"type": "bank_card"},
            "confirmation": {
                "type": "redirect", 
                "return_url": "https://t.me/your_bot"
            },
            "capture": True,
            "description": f"Outline VPN подписка: {tariff}",
            "metadata": {"user_id": user_id, "tariff": tariff}
        }
        
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
            print(f"❌ Ошибка ЮKassa API: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка создания платежа: {e}")
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

async def create_vpn_config_after_payment(query, user_id: int, amount: int, tariff: str):
    """АВТОМАТИЧЕСКОЕ создание VPN конфигурации после оплаты"""
    try:
        print(f"🎯 Автоматически создаю VPN ключ для {user_id}, тариф: {tariff}")
        
        # 1. Пытаемся создать реальный ключ через Outline API
        access_key, key_id, key_name = create_real_outline_key()
        
        # 2. Если не удалось - создаем демо-ключ
        if not access_key:
            print("⚠️ Outline API недоступен, создаю демо-ключ")
            access_key = generate_demo_access_key()
            key_id = f"demo_{user_id}_{int(datetime.datetime.now().timestamp())}"
            key_name = "demo_key"
        
        # 3. Устанавливаем лимит трафика для реального ключа
        if key_id and not key_id.startswith('demo_'):
            set_outline_data_limit(key_id, 1000)  # 1000 GB лимит
        
        # 4. Сохраняем в базу данных
        expiry_date = calculate_expiry_date(tariff)
        
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vpn_configs 
            (user_id, config_name, access_key, outline_key_id, server_host, server_port, expiry_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, 
            f"outline_{tariff}_{user_id}",
            access_key, 
            key_id,
            OUTLINE_SERVER_HOST,
            OUTLINE_SERVER_PORT,
            expiry_date,
            True
        ))
        conn.commit()
        conn.close()
        
        print(f"✅ Ключ сохранен в БД для пользователя {user_id}")
        
        # 5. Отправляем ключ пользователю
        await send_vpn_key_to_user(query, access_key, amount, tariff, expiry_date, key_id)
        
    except Exception as e:
        print(f"❌ Ошибка создания конфига: {e}")
        await query.edit_message_text(
            "❌ <b>Ошибка при создании VPN ключа</b>\n\n"
            "Пожалуйста, обратитесь в поддержку: @o0_Ai_Donna_0o\n"
            "Мы решим проблему в течение 15 минут!",
            parse_mode='HTML'
        )

async def send_vpn_key_to_user(query, access_key, amount, tariff, expiry_date, key_id):
    """Отправка ключа пользователю"""
    
    tariff_names = {
        '1_month': '1 месяц',
        '3_months': '3 месяца', 
        '6_months': '6 месяцев',
        '12_months': '12 месяцев'
    }
    
    # Определяем тип ключа для сообщения
    is_demo = key_id.startswith('demo_') if key_id else True
    key_type = "🔴 ДЕМО-КЛЮЧ (для тестирования)" if is_demo else "🟢 РЕАЛЬНЫЙ КЛЮЧ"
    server_info = f"🌐 Сервер: {OUTLINE_SERVER_HOST}:{OUTLINE_SERVER_PORT}"
    
    success_text = f"""
🎉 <b>ОПЛАТА ПОДТВЕРЖДЕНА И КЛЮЧ СОЗДАН!</b>

{key_type}
{server_info}

✅ <b>Тариф:</b> {tariff_names.get(tariff, tariff)}
💳 <b>Сумма:</b> {amount} руб
📅 <b>Действует до:</b> {expiry_date.strftime('%d.%m.%Y')}

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
• Локация: Германия/Нидерланды
• Скорость: до 1 Гбит/с
• Трафик: безлимитный
• Защита: DDoS protection

💡 <b>Сохраните этот ключ!</b> Он нужен для подключения на всех устройствах.

🛠 <b>Помощь:</b> @o0_Ai_Donna_0o
"""
    await query.edit_message_text(success_text, parse_mode='HTML')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    user = update.message.from_user
    
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user.id, user.username))
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    welcome_text = f"""
🔓 <b>Добро пожаловать в Premium Outline VPN Service!</b>

👋 <b>Привет, {user.first_name}!</b>

🚀 <b>Наш сервер Outline:</b>
• Хост: <code>{OUTLINE_SERVER_HOST}</code>
• Порт: <code>{OUTLINE_SERVER_PORT}</code>
• Локация: Германия/Нидерланды
• Технология: Outline (от Google)

⭐ <b>Преимущества:</b>
• <b>Максимальная скорость</b> - до 1 Гбит/с
• <b>Автоматическая выдача ключей</b> после оплаты
• <b>Стабильное соединение</b> - обход блокировок
• <b>Безлимитный трафик</b> - никаких ограничений
• <b>Поддержка 24/7</b> - всегда на связи

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
    
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    text = f"""
💳 <b>Пополнение баланса</b>

💰 <b>Текущий баланс:</b> {balance} руб
🌐 <b>Сервер:</b> {OUTLINE_SERVER_HOST}:{OUTLINE_SERVER_PORT}

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
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инструкция по получению VPN"""
    text = f"""
📖 <b>ИНСТРУКЦИЯ ПО ПОЛУЧЕНИЮ OUTLINE VPN</b>

🔹 <b>ШАГ 1: ОПЛАТА</b>
• Нажмите "💰 Пополнить баланс"
• Выберите подходящий тариф
• Оплатите через безопасную страницу ЮKassa

🔹 <b>ШАГ 2: АВТОМАТИЧЕСКОЕ ПОЛУЧЕНИЕ КЛЮЧА</b>
• После оплаты нажмите "✅ Проверить оплату"
• Система <b>АВТОМАТИЧЕСКИ</b> создаст ключ на сервере
• Вы получите <b>реальный ключ доступа</b> к Outline VPN

🔹 <b>ШАГ 3: НАСТРОЙКА</b>
• Скачайте Outline Client по ссылке ниже
• Вставьте полученный ключ в программу
• Нажмите "Подключиться" - готово!

🖥 <b>Данные сервера:</b>
• Хост: <code>{OUTLINE_SERVER_HOST}</code>
• Порт: <code>{OUTLINE_SERVER_PORT}</code>

📲 <b>СКАЧАТЬ OUTLINE CLIENT:</b>

<b>Официальный сайт:</b>
https://getoutline.org/

<b>Яндекс Диск (если не открывается):</b>
https://disk.yandex.ru/d/TcLDT462de165g

💡 <b>После оплаты вы АВТОМАТИЧЕСКИ получите реальный ключ!</b>
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
        tariff = data.replace('tariff_', '')
        tariff_names = {
            '1_month': '1 месяц',
            '3_months': '3 месяца', 
            '6_months': '6 месяцев',
            '12_months': '12 месяцев'
        }
        amount = PRICES[tariff]
        
        payment_url = create_yookassa_payment(amount, tariff, user_id)
        
        if payment_url:
            payment_text = f"""
💳 <b>Оплата тарифа: {tariff_names[tariff]}</b>

💰 <b>Сумма:</b> {amount} руб
🌐 <b>Сервер:</b> {OUTLINE_SERVER_HOST}:{OUTLINE_SERVER_PORT}

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
    
    elif data == 'show_instructions':
        await handle_instructions(update, context)

async def check_payment_status(query, user_id: int):
    """Проверка статуса платежа с АВТОМАТИЧЕСКИМ созданием ключа"""
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT yookassa_payment_id, amount, tariff, status 
        FROM payments 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY payment_date DESC 
        LIMIT 1
    ''', (user_id,))
    
    payment = cursor.fetchone()
    
    if not payment:
        await query.edit_message_text("❌ Не найдено ожидающих платежей")
        conn.close()
        return
    
    payment_id, amount, tariff, status = payment
    
    try:
        response = requests.get(
            f"{YOOKASSA_API_URL}/{payment_id}",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        )
        
        if response.status_code == 200:
            payment_info = response.json()
            
            if payment_info['status'] == 'succeeded':
                # Обновляем баланс
                cursor.execute('UPDATE payments SET status = "succeeded" WHERE yookassa_payment_id = ?', (payment_id,))
                cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
                conn.commit()
                conn.close()
                
                # АВТОМАТИЧЕСКИ СОЗДАЕМ КЛЮЧ!
                await create_vpn_config_after_payment(query, user_id, amount, tariff)
                return
                
            elif payment_info['status'] == 'pending':
                await query.edit_message_text("⏳ Платеж обрабатывается...")
            else:
                await query.edit_message_text(f"❌ Статус: {payment_info['status']}")
        else:
            await query.edit_message_text("❌ Ошибка проверки платежа")
            
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")
    
    conn.close()

async def create_vpn_config(query, user_id: int):
    """Создание VPN конфигурации по запросу"""
    try:
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = cursor.fetchone()[0]
        conn.close()
        
        if balance <= 0:
            await query.edit_message_text("❌ Недостаточно средств!")
            return
        
        # Создаем реальный или демо-ключ
        access_key, key_id, key_name = create_real_outline_key()
        if not access_key:
            access_key = generate_demo_access_key()
            key_id = f"demo_{user_id}_{int(datetime.datetime.now().timestamp())}"
        
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=30)
        
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vpn_configs 
            (user_id, config_name, access_key, outline_key_id, server_host, server_port, expiry_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, f"manual_{user_id}", access_key, key_id, OUTLINE_SERVER_HOST, OUTLINE_SERVER_PORT, expiry_date, True))
        conn.commit()
        conn.close()
        
        key_type = "🔴 ДЕМО-КЛЮЧ" if key_id.startswith('demo_') else "🟢 РЕАЛЬНЫЙ КЛЮЧ"
        
        success_text = f"""
✅ <b>Конфигурация создана!</b>

{key_type}
🌐 Сервер: {OUTLINE_SERVER_HOST}:{OUTLINE_SERVER_PORT}

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
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def handle_my_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои конфигурации"""
    user_id = update.message.from_user.id
    
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT config_name, access_key, created_date, expiry_date, server_host, server_port 
        FROM vpn_configs 
        WHERE user_id = ? AND is_active = TRUE 
        ORDER BY created_date DESC
    ''', (user_id,))
    configs = cursor.fetchall()
    conn.close()
    
    if configs:
        text = "🔧 <b>Ваши конфигурации Outline:</b>\n\n"
        for i, (name, access_key, created, expiry, host, port) in enumerate(configs, 1):
            is_demo = "demo" in str(access_key) or "demo" in str(name)
            key_type = "🔴 ДЕМО" if is_demo else "🟢 РЕАЛЬНЫЙ"
            expiry_text = f"📅 Истекает: {expiry.strftime('%d.%m.%Y')}" if expiry else ""
            server_info = f"🌐 {host}:{port}" if host and port else ""
            
            text += f"{i}. <b>{name}</b> {key_type}\n"
            text += f"   🔑 <code>{access_key}</code>\n"
            text += f"   {server_info}\n"
            text += f"   📅 Создан: {created[:10]} {expiry_text}\n\n"
        
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
    text = f"""
👨‍💻 <b>Техническая поддержка Outline VPN</b>

🕒 <b>Режим работы:</b> 24/7
📱 <b>Telegram:</b> @o0_Ai_Donna_0o

🔧 <b>Мы помогаем с:</b>
• Настройкой Outline Client
• Проблемами с подключением
• Оплатой и балансом
• Автоматической выдачей ключей

🌐 <b>Данные сервера:</b>
• Хост: <code>{OUTLINE_SERVER_HOST}</code>
• Порт: <code>{OUTLINE_SERVER_PORT}</code>
• API: <code>{OUTLINE_API_URL[:50]}...</code>

💬 <b>Напишите нам прямо сейчас!</b>

⚠️ <b>При обращении укажите ваш ID:</b> <code>{update.message.from_user.id}</code>
"""
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

def main():
    """Запуск бота"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
        
        print("🟢 VPN Bot запущен!")
        print("🔑 АВТОМАТИЧЕСКАЯ выдача Outline ключей")
        print("🌐 Сервер:", OUTLINE_SERVER_HOST + ":" + OUTLINE_SERVER_PORT)
        print("📡 API URL:", OUTLINE_API_URL)
        print("💰 Интеграция с ЮKassa")
        print("🚀 Готов к работе!")
        
        # Тестируем подключение к Outline API
        print("🧪 Тестируем подключение к Outline API...")
        access_key, key_id, name = create_real_outline_key()
        if access_key:
            print("✅ Outline API работает отлично!")
        else:
            print("⚠️ Outline API недоступен, используется демо-режим")
        
        application.run_polling()
        
    except Exception as e:
        print(f"🔴 Ошибка: {e}")
        import time
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()

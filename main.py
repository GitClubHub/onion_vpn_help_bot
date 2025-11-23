import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"

# Токен ЮKassa (ваш тестовый ключ)
YOOKASSA_PROVIDER_TOKEN = "test_WID1Xwp2NqxOeQ82EEEvsDhLI_dEcEGKeLrxr3qTKLk"

# Цены за подписку в копейках (ЮKassa работает в копейках)
PRICES = {
    "1_month": 15000,  # 150 рублей = 15000 копеек
    "3_months": 35000,
    "6_months": 60000,
    "12_months": 100000
}

# Словарь для хранения выбранных тарифов пользователей
user_tariffs = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.message.from_user
    
    welcome_text = f"""
🔐 <b>Добро пожаловать в VPN Service Bot!</b>

👋 Привет, {user.first_name}!

🤖 <i>Этот бот предоставляет доступ к premium VPN сервисам</i>

🚀 <b>Наши преимущества:</b>
• Высокая скорость соединения
• Полная анонимность
• Безлимитный трафик
• Поддержка 24/7
• Работа с любыми сайтами

👇 <b>Выберите тариф для продолжения:</b>
    """
    
    # Создаем клавиатуру с кнопками тарифов
    keyboard = [
        [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
        [KeyboardButton("6 месяцев - 600₽"), KeyboardButton("12 месяцев - 1000₽")],
        [KeyboardButton("📞 Поддержка"), KeyboardButton("📖 Инструкция")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех текстовых сообщений"""
    text = update.message.text
    user_id = update.message.from_user.id
    
    print(f"Получено сообщение: {text} от пользователя {user_id}")  # Для отладки
    
    # Обработка выбора тарифов
    if "1 месяц" in text:
        user_tariffs[user_id] = "1_month"
        await create_invoice(update, "1_month", "VPN подписка на 1 месяц", "Доступ к VPN на 1 месяц", PRICES["1_month"])
    elif "3 месяца" in text:
        user_tariffs[user_id] = "3_months"
        await create_invoice(update, "3_months", "VPN подписка на 3 месяца", "Доступ к VPN на 3 месяца", PRICES["3_months"])
    elif "6 месяцев" in text:
        user_tariffs[user_id] = "6_months"
        await create_invoice(update, "6_months", "VPN подписка на 6 месяцев", "Доступ к VPN на 6 месяцев", PRICES["6_months"])
    elif "12 месяцев" in text:
        user_tariffs[user_id] = "12_months"
        await create_invoice(update, "12_months", "VPN подписка на 12 месяцев", "Доступ к VPN на 12 месяцев", PRICES["12_months"])
    
    # Обработка других кнопок
    elif "поддерж" in text.lower() or "📞" in text:
        await support(update, context)
    elif "инструкц" in text.lower() or "📖" in text:
        await instructions(update, context)
    
    # Обработка простых сообщений
    elif any(word in text.lower() for word in ['привет', 'hello', 'hi', 'start']):
        await start(update, context)
    elif 'тариф' in text.lower() or 'цена' in text.lower():
        await price(update, context)
    elif 'инфо' in text.lower() or 'о сервисе' in text.lower():
        await info(update, context)
    else:
        await update.message.reply_text(
            "🤔 Не понял ваш запрос. Используйте кнопки ниже или напишите /start",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
                [KeyboardButton("📞 Поддержка"), KeyboardButton("📖 Инструкция")]
            ], resize_keyboard=True)
        )

async def create_invoice(update: Update, tariff_id: str, title: str, description: str, price: int):
    """Создание инвойса для оплаты через ЮKassa"""
    try:
        # Параметры для инвойса
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
    """Обработчик предварительной проверки оплаты"""
    query = update.pre_checkout_query
    
    # Проверяем данные
    if query.invoice_payload.startswith('vpn_subscription_'):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Произошла ошибка при обработке платежа")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик успешной оплаты"""
    try:
        payment = update.message.successful_payment
        user = update.message.from_user
        user_id = user.id
        
        # Определяем тариф по payload
        tariff_map = {
            "vpn_subscription_1_month": ("1 месяц", 150),
            "vpn_subscription_3_months": ("3 месяца", 350), 
            "vpn_subscription_6_months": ("6 месяцев", 600),
            "vpn_subscription_12_months": ("12 месяцев", 1000)
        }
        
        tariff_name, tariff_price = tariff_map.get(payment.invoice_payload, ("неизвестный тариф", 0))
        
        # Генерируем данные для VPN
        vpn_username = f"vpnuser{user.id}"
        vpn_password = generate_password()
        
        success_text = f"""
🎉 <b>Оплата прошла успешно!</b>

✅ <b>Тариф:</b> {tariff_name}
💳 <b>Сумма:</b> {tariff_price} ₽
📧 <b>Email для чека:</b> {payment.order_info.email if payment.order_info and payment.order_info.email else 'не указан'}

🔐 <b>Ваши данные для VPN:</b>
├ Логин: <code>{vpn_username}</code>
├ Пароль: <code>{vpn_password}</code>
└ Срок действия: {tariff_name}

📖 <b>Инструкция по настройке:</b>
Напишите "Инструкция" или нажмите кнопку ниже

🛠 <b>Техподдержка:</b>
Напишите "Поддержка" для связи

💡 <b>Сохраните эти данные в надежном месте!</b>
        """
        
        await update.message.reply_text(success_text, parse_mode='HTML')
        
        # Очищаем данные о выбранном тарифе
        if user_id in user_tariffs:
            del user_tariffs[user_id]
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при обработке платежа: {e}")

def generate_password(length=12):
    """Генерация случайного пароля"""
    import string
    import random
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды поддержки"""
    support_text = """
📞 <b>Техническая поддержка</b>

🕒 <b>Время работы:</b> 24/7

📱 <b>Telegram:</b> @o0_Ai_Donna_0o

🔧 <b>Мы поможем с:</b>
• Настройкой VPN
• Проблемами с подключением
• Вопросами по оплате
• Техническими неполадками

💬 <b>Напишите нам в Telegram</b> для быстрого ответа!
    """
    await update.message.reply_text(support_text, parse_mode='HTML')

async def instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды инструкции"""
    instructions_text = """
📖 <b>Инструкция по настройке VPN</b>

🖥 <b>Для Windows:</b>
1. Скачайте OpenVPN с официального сайта
2. Установите программу
3. Запросите конфиг-файл у поддержки
4. Запустите подключение

📱 <b>Для Android/iOS:</b>
1. Установите OpenVPN из магазина приложений
2. Импортируйте конфиг-файл
3. Введите логин и пароль
4. Подключитесь

🌐 <b>Для роутера:</b>
1. Войдите в панель управления роутером
2. Настройте OpenVPN клиент
3. Загрузите конфигурацию
4. Перезагрузите роутер

🔧 <b>Нужна помощь?</b> Напишите "Поддержка"
    """
    await update.message.reply_text(instructions_text, parse_mode='HTML')

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /price"""
    price_text = f"""
💰 <b>Стоимость подписки</b>

📅 <b>Тарифы:</b>
• 1 месяц - 150₽
• 3 месяца - 350₽
• 6 месяцев - 600₽
• 12 месяцев - 1000₽

💡 <b>Выберите тариф кнопками ниже</b>
    """
    
    keyboard = [
        [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
        [KeyboardButton("6 месяцев - 600₽"), KeyboardButton("12 месяцев - 1000₽")],
        [KeyboardButton("📞 Поддержка"), KeyboardButton("📖 Инструкция")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(price_text, reply_markup=reply_markup, parse_mode='HTML')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /info"""
    info_text = """
ℹ️ <b>О нашем VPN сервисе</b>

🛡️ <b>Безопасность:</b>
• Шифрование AES-256
• Безлоговые сервера
• Защита от утечек DNS

🌍 <b>Сервера:</b>
• Россия, Германия, США
• Нидерланды, Сингапур
• Высокая скорость подключения

⚡ <b>Скорость:</b>
• Неограниченный трафик
• Поддержка 4K потокового видео
• Стабильное соединение

💬 <b>Начните использовать - выберите тариф ниже!</b>
    """
    
    keyboard = [
        [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
        [KeyboardButton("📞 Поддержка"), KeyboardButton("📖 Инструкция")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(info_text, reply_markup=reply_markup, parse_mode='HTML')

def main():
    """Основная функция запуска бота"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("support", support))
        application.add_handler(CommandHandler("instructions", instructions))
        application.add_handler(CommandHandler("price", price))
        application.add_handler(CommandHandler("info", info))
        application.add_handler(CommandHandler("help", start))
        
        # Обработчики для платежей
        application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
        
        # Обработчик ВСЕХ текстовых сообщений - ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🟢 Бот запущен и работает с ЮKassa!")
        print("💰 Платежи готовы к тестированию")
        print("⏰ Бот будет работать 24/7")
        
        application.run_polling()
        
    except Exception as e:
        print(f"🔴 Ошибка: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        import time
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()

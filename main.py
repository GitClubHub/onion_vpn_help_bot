import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота из переменных окружения
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"

# Цены за подписку
PRICES = {
    "1_month": 150,
    "3_months": 350,
    "6_months": 600,
    "12_months": 1000
}

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

📋 <b>Доступные команды:</b>
/support - 📞 Техническая поддержка
/instructions - 📖 Инструкция по настройке
/price - 💰 Стоимость подписки
/info - ℹ️ О сервисе

💳 <b>Как получить доступ:</b>
1. Выберите тариф подписки
2. Оплатите стоимость
3. Отправьте скриншот оплаты
4. Получите данные для доступа

👇 <b>Выберите тариф для продолжения:</b>
    """
    
    # Создаем клавиатуру с кнопками тарифов
    keyboard = [
        [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
        [KeyboardButton("6 месяцев - 600₽"), KeyboardButton("12 месяцев - 1000₽")],
        [KeyboardButton("/support"), KeyboardButton("/instructions")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_tariff_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора тарифа"""
    text = update.message.text
    
    if "1 месяц" in text:
        await send_payment_info(update, "1 месяц", PRICES["1_month"])
    elif "3 месяца" in text:
        await send_payment_info(update, "3 месяца", PRICES["3_months"])
    elif "6 месяцев" in text:
        await send_payment_info(update, "6 месяцев", PRICES["6_months"])
    elif "12 месяцев" in text:
        await send_payment_info(update, "12 месяцев", PRICES["12_months"])

async def send_payment_info(update: Update, period: str, price: int):
    """Отправляет информацию об оплате"""
    payment_text = f"""
💳 <b>Оплата подписки {period}</b>

💰 <b>Сумма к оплате:</b> {price}₽

🏦 <b>Реквизиты для оплаты:</b>
Сбербанк: <code>1111111111111111</code>

📋 <b>ВАЖНО!</b> После оплаты:

1. Сделайте скриншот чека об оплате
2. Напишите мне в Telegram: @o0_Ai_Donna_0o
3. Отправьте скриншот или файл с оплатой
4. Укажите ваш выбранный тариф ({period})

🎁 После проверки оплаты вы получите:
• Логин и пароль для VPN
• Инструкцию по настройке
• Техническую поддержку

⏰ Обычно это занимает не более 15 минут!
    """
    
    await update.message.reply_text(payment_text, parse_mode='HTML')

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /support"""
    support_text = """
📞 <b>Техническая поддержка</b>

🕒 <b>Время работы:</b> 24/7

📱 <b>Telegram:</b> @o0_Ai_Donna_0o

📧 <b>Почта:</b> support@vpnservice.com

🔧 <b>Мы поможем с:</b>
• Настройкой VPN
• Проблемами с подключением
• Вопросами по оплате
• Техническими неполадками

💬 <b>Напишите нам в Telegram</b> для быстрого ответа!
    """
    await update.message.reply_text(support_text, parse_mode='HTML')

async def instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /instructions"""
    instructions_text = """
📖 <b>Инструкция по настройке VPN</b>

🖥 <b>Для Windows:</b>
1. Скачайте OpenVPN с официального сайта
2. Установите программу
3. Загрузите конфиг-файл (получите после оплаты)
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

🔧 <b>Нужна помощь?</b> Напишите /support
    """
    await update.message.reply_text(instructions_text, parse_mode='HTML')

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /price"""
    price_text = f"""
💰 <b>Стоимость подписки</b>

📅 <b>Тарифы:</b>
• 1 месяц - {PRICES['1_month']}₽
• 3 месяца - {PRICES['3_months']}₽
• 6 месяцев - {PRICES['6_months']}₽
• 12 месяцев - {PRICES['12_months']}₽

💡 <b>Выберите тариф</b> кнопками ниже или напишите /start
    """
    
    # Клавиатура с тарифами
    keyboard = [
        [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
        [KeyboardButton("6 месяцев - 600₽"), KeyboardButton("12 месяцев - 1000₽")]
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

🔒 <b>Гарантии:</b>
• Работаем с 2020 года
• Тысячи довольных клиентов
• Круглосуточная поддержка

💬 <b>Начните использовать:</b> /start
    """
    await update.message.reply_text(info_text, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    if any(word in text.lower() for word in ['привет', 'hello', 'hi']):
        await update.message.reply_text("👋 Привет! Используйте /start для начала работы")
    elif 'тариф' in text.lower():
        await price(update, context)
    elif 'поддерж' in text.lower():
        await support(update, context)
    elif 'инструкц' in text.lower():
        await instructions(update, context)
    else:
        await update.message.reply_text(
            "🤔 Не понял ваш запрос.\n"
            "Используйте /start для выбора тарифа или /help для списка команд"
        )

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
        
        # Обработчик текстовых сообщений (тарифы)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tariff_selection))
        
        print("🟢 Бот запущен и работает на Railway!")
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

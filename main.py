import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токены
BOT_TOKEN = "8222449218:AAFgj48oh7Qczvre3l17Tr4FLWmzlWZKVtM"
YOOKASSA_PROVIDER_TOKEN = "test_WID1Xwp2NqxOeQ82EEEvsDhLI_dEcEGKeLrxr3qTKLk"
YOOKASSA_SHOP_ID = "1212021"

# Цены в копейках
PRICES = {
    "1_month": 15000,
    "3_months": 35000, 
    "6_months": 60000,
    "12_months": 100000
}

# Словарь для соответствия тарифов
TARIFF_NAMES = {
    "1_month": "1 месяц",
    "3_months": "3 месяца", 
    "6_months": "6 месяцев",
    "12_months": "12 месяцев"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная команда"""
    user = update.message.from_user
    
    welcome_text = f"""
🔐 <b>VPN Service Bot</b>

👋 Привет, {user.first_name}!

Выберите тариф для подключения:

• 1 месяц - 150₽
• 3 месяца - 350₽  
• 6 месяцев - 600₽
• 12 месяцев - 1000₽

👇 <b>Нажмите на кнопку ниже для выбора тарифа</b>
"""
    
    keyboard = [
        [KeyboardButton("1 месяц - 150₽"), KeyboardButton("3 месяца - 350₽")],
        [KeyboardButton("6 месяцев - 600₽"), KeyboardButton("12 месяцев - 1000₽")],
        [KeyboardButton("📞 Поддержка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ВСЕХ сообщений"""
    text = update.message.text
    user_id = update.message.from_user.id
    
    print(f"Получено сообщение от {user_id}: {text}")  # Отладка
    
    # Сохраняем выбранный тариф в context
    if "1 месяц" in text:
        context.user_data['selected_tariff'] = "1_month"
        await create_invoice(update, "1_month", "VPN подписка на 1 месяц", "Доступ к VPN на 1 месяц", PRICES["1_month"])
    elif "3 месяца" in text:
        context.user_data['selected_tariff'] = "3_months"
        await create_invoice(update, "3_months", "VPN подписка на 3 месяца", "Доступ к VPN на 3 месяца", PRICES["3_months"])
    elif "6 месяцев" in text:
        context.user_data['selected_tariff'] = "6_months"
        await create_invoice(update, "6_months", "VPN подписка на 6 месяцев", "Доступ к VPN на 6 месяцев", PRICES["6_months"])
    elif "12 месяцев" in text:
        context.user_data['selected_tariff'] = "12_months"
        await create_invoice(update, "12_months", "VPN подписка на 12 месяцев", "Доступ к VPN на 12 месяцев", PRICES["12_months"])
    elif "поддерж" in text.lower() or "📞" in text:
        await support(update, context)
    else:
        await start(update, context)

async def create_invoice(update: Update, tariff_id: str, title: str, description: str, price: int):
    """Создание платежа через ЮKassa"""
    try:
        # payload должен быть уникальным для каждого платежа
        import time
        payload = f"{tariff_id}_{int(time.time())}"
        
        prices = [LabeledPrice(label=title, amount=price)]
        
        # Параметры для ЮKassa
        provider_data = {
            "receipt": {
                "customer": {},
                "items": [
                    {
                        "description": description,
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{price/100:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": "1",
                        "payment_mode": "full_payment",
                        "payment_subject": "service"
                    }
                ]
            }
        }
        
        await update.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            need_name=False,
            need_email=True,  # Обязательно для ЮKassa
            need_phone_number=False,
            need_shipping_address=False,
            is_flexible=False,
            provider_data=provider_data
        )
        
        print(f"Создан инвойс для тарифа {tariff_id}, цена: {price/100}₽")
        
    except Exception as e:
        error_text = f"❌ Ошибка при создании платежа: {str(e)}"
        print(error_text)
        await update.message.reply_text(error_text)

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение платежа перед списанием"""
    query = update.pre_checkout_query
    user_id = query.from_user.id
    
    print(f"Предварительная проверка платежа от {user_id}")
    
    # Всегда подтверждаем запрос
    try:
        await query.answer(ok=True)
        print("✅ Платеж подтвержден для списания")
    except Exception as e:
        print(f"❌ Ошибка подтверждения платежа: {e}")
        await query.answer(ok=False, error_message="Произошла ошибка при обработке платежа")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешного платежа"""
    try:
        payment = update.message.successful_payment
        user = update.message.from_user
        
        print(f"Успешный платеж от {user.id}")
        print(f"Данные платежа: {payment}")
        
        # Определяем тариф из payload или из context
        tariff_id = "1_month"  # значение по умолчанию
        if hasattr(payment, 'invoice_payload') and payment.invoice_payload:
            payload_parts = payment.invoice_payload.split('_')
            if payload_parts[0] in PRICES:
                tariff_id = payload_parts[0]
        elif 'selected_tariff' in context.user_data:
            tariff_id = context.user_data['selected_tariff']
        
        tariff_name = TARIFF_NAMES.get(tariff_id, "1 месяц")
        tariff_price = PRICES.get(tariff_id, 15000) // 100
        
        # Генерируем данные VPN
        vpn_username = f"vpn{user.id}"
        vpn_password = generate_password()
        
        success_text = f"""
🎉 <b>ОПЛАТА ПРОШЛА УСПЕШНО!</b>

✅ <b>Тариф:</b> {tariff_name}
💳 <b>Сумма:</b> {tariff_price} ₽
📧 <b>Email для чека:</b> {payment.order_info.email if payment.order_info and payment.order_info.email else 'не указан'}

🔐 <b>ВАШИ ДАННЫЕ ДЛЯ VPN:</b>
├ Логин: <code>{vpn_username}</code>
├ Пароль: <code>{vpn_password}</code>
└ Срок действия: {tariff_name}

📞 <b>Для получения конфигурационного файла и помощи:</b>
Напишите в поддержку: @o0_Ai_Donna_0o

💡 <b>Сохраните эти данные!</b>
"""
        
        await update.message.reply_text(success_text, parse_mode='HTML')
        
        # Очищаем выбранный тариф
        if 'selected_tariff' in context.user_data:
            del context.user_data['selected_tariff']
            
        print(f"✅ Пользователь {user.id} получил VPN данные")
        
    except Exception as e:
        error_text = f"❌ Ошибка обработки платежа: {str(e)}"
        print(error_text)
        await update.message.reply_text(error_text)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда поддержки"""
    support_text = """
📞 <b>Техническая поддержка</b>

🕒 Работаем 24/7
👤 Telegram: @o0_Ai_Donna_0o

🔧 Помощь с:
• Настройкой VPN
• Проблемами подключения
• Оплатой и чеками
• Конфигурационными файлами

💬 <b>Напишите нам прямо сейчас!</b>
"""
    await update.message.reply_text(support_text, parse_mode='HTML')

def generate_password(length=10):
    """Генерация надежного пароля"""
    import string
    import random
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

def main():
    """Запуск бота"""
    try:
        print("🟢 Запуск VPN бота с ЮKassa...")
        print(f"🏪 Shop ID: {YOOKASSA_SHOP_ID}")
        print("💰 Готов к приему платежей!")
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Обработчики в правильном порядке:
        
        # 1. Команды
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("support", support))
        
        # 2. Платежи
        application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
        
        # 3. ВСЕ текстовые сообщения - ПОСЛЕДНИМ
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
        
        print("🤖 Бот запущен и ожидает сообщения...")
        print("💸 Тестовые карты для проверки:")
        print("   ✅ 5555 5555 5555 4444 - успешный платеж")
        print("   ✅ 2200 0000 0000 0004 - успешный платеж")
        
        application.run_polling()
        
    except Exception as e:
        print(f"🔴 Критическая ошибка: {e}")
        import time
        time.sleep(10)
        print("🔄 Перезапуск...")
        main()

if __name__ == '__main__':
    main()

import os
import logging
import redis

from dotenv import load_dotenv

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Filters, Updater, CallbackContext
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from strapi_service import get_products, get_product_image

_database = None

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def start(update: Updater, context: CallbackContext):
    """Обработчик команды старт, показывает приветственное сообщение и меню продуктов"""
    # Получаем продукты только если их нет в контексте или это команда /start
    if 'products' not in context.bot_data or (update.message and update.message.text == '/start'):
        strapi_api_token = context.bot_data['strapi_api_token']
        strapi_url = context.bot_data['strapi_url']
        products = get_products(strapi_api_token, strapi_url)
        context.bot_data['products'] = products
    else:
        products = context.bot_data['products']
    
    product_buttons = [
        [InlineKeyboardButton(
            product['Title'],
            callback_data=product['documentId']
        )] 
        for product in products
    ]
    reply_markup = InlineKeyboardMarkup(product_buttons)

    greeting = "Выберите товар:"
    menu_prompt = "Товары списком:"

    if update.message:
        update.message.reply_text(greeting, reply_markup=reply_markup)
    else:
        query = update.callback_query
        # Сначала отправляем новое сообщение
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=menu_prompt,
            reply_markup=reply_markup
        )
        # Потом удаляем старое
        query.message.delete()

    return 'HANDLE_MENU'


def handle_menu(update, context: CallbackContext):
    """Обработчик выбора товара."""
    query = update.callback_query
    if not query:
        return "HANDLE_MENU"
    
    query.answer()
    
    # Возврат в меню
    if query.data == 'back_to_menu':
        start(update, context)
        return "HANDLE_MENU"
    
    # Получаем товар из кэша
    products = context.bot_data['products']
    product = next(
        (p for p in products if p['documentId'] == query.data),
        None
    )
    
    # Если товар не найден
    if not product:
        query.message.edit_text(
            "Товар не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Назад в меню", callback_data='back_to_menu')
            ]])
        )
        return "HANDLE_MENU"
    
    # Формируем сообщение
    message = (
        f"{product['Title']}\n"
        f"Цена: {product.get('price', 'не указана')} руб.\n"
        f"{product.get('description', '')}"
    )
    
    keyboard = [[
        InlineKeyboardButton("Назад", callback_data='back_to_menu'),
        InlineKeyboardButton("В корзину", callback_data='add_to_cart')
    ]]
    
    # Получаем картинку если она есть
    image_data = None
    if product.get('picture'):
        image_data = get_product_image(
            context.bot_data['strapi_url'],
            product['picture'][0]['url']
        )
    
    # Сначала отправляем новое сообщение
    if image_data:
        context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=image_data,
            caption=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Потом удаляем старое
    query.message.delete()
    
    return "HANDLE_DESCRIPTION"


def handle_users_reply(update, context):
    """
    Функция, которая запускается при любом сообщении от пользователя и решает как его обработать.
    """
    
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return

    if user_reply == '/start':
        user_state = 'START'
    else:
        # Получаем Redis из контекста бота
        redis_db = context.bot_data.get('db')
        user_state = redis_db.get(chat_id) if redis_db else None
        if user_state is None:
            user_state = 'START'
        else:
            user_state = user_state.decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
    }
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(update, context)
        # Получаем Redis из контекста бота
        redis_db = context.bot_data.get('db')
        if redis_db:
            redis_db.set(chat_id, next_state)
    except Exception as err:
        logger.error(f'Ошибка: {err}')


def get_database_connection(redis_db_host, redis_db_port, database_password):
    """
    Возвращает конекшн с базой данных Redis, либо создаёт новый, если он ещё не создан.
    """
    global _database
    if _database is None:
        _database = redis.Redis(
            host=redis_db_host,
            port=redis_db_port,
            password=database_password,
            decode_responses=True  # Автоматически декодируем ответы из bytes в строки
        )
    return _database


def main():
    load_dotenv()
    strapi_url = os.getenv('STRAPI_URL')
    strapi_api_token = os.getenv('STRAPI_API_TOKEN')
    
    database_host = os.getenv("REDIS_HOST")
    database_port = os.getenv("REDIS_DATABASE_PORT")
    database_password = os.getenv("REDIS_DATABASE_PASSWORD")
    token = os.getenv("TG_BOT_TOKEN")
    
    db = get_database_connection(
        database_host,
        database_port,
        database_password
    )
    updater = Updater(token)
    dispatcher = updater.dispatcher

    # Сохраняем данные в context.bot_data
    dispatcher.bot_data['strapi_api_token'] = strapi_api_token
    dispatcher.bot_data['strapi_url'] = strapi_url
    dispatcher.bot_data['db'] = db

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(handle_menu))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

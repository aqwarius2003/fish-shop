import os
import logging
import redis
import requests
from urllib.parse import urljoin
import time

from dotenv import load_dotenv

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Filters, Updater, CallbackContext
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from strapi_service import (
    get_products, get_product_image, get_cart,
    add_to_cart_item, get_products_from_cart, create_client, connect_client_to_cart,
    create_cart, format_cart_content
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


_database = None

def error_handler(update, context):
    """Обработчик ошибок"""
    logger.error(f"Произошла ошибка: {context.error}")


def start(update: Updater, context: CallbackContext):
    """Обработчик команды старт, показывает приветственное сообщение и меню продуктов"""
    # Получаем продукты только если их нет в контексте или это команда /start
    if 'products' not in context.bot_data or (update.message and update.message.text == '/start'):
        strapi_api_token = context.bot_data['strapi_api_token']
        strapi_url = context.bot_data['strapi_url']
        products = get_products(strapi_api_token, strapi_url)
        context.bot_data['products'] = products
        
        # Если это команда /start - создаем клиента в Strapi
        if update.message and update.message.text == '/start':
            tg_id = str(update.message.from_user.id)
            # Проверяем, создан ли клиент с таким tg_id
            client_id = create_client(strapi_api_token, tg_id, strapi_url)
            if client_id:
                logger.info(f"Создан новый клиент с ID: {client_id}")
    else:
        products = context.bot_data['products']

    product_buttons = [
        [InlineKeyboardButton(
            product.get('title'),
            callback_data=str(product.get('id'))
        )]
        for product in products
    ]
    # Добавляем кнопку корзины в основное меню
    product_buttons.append([
        InlineKeyboardButton("🛒 Моя корзина", callback_data='show_cart')
    ])
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
    # Получаем callback_query из update
    # Если пользователь отправил обычное текстовое сообщение, а не нажал на кнопку,
    # то callback_query будет None. В этом случае мы просто возвращаемся в состояние HANDLE_MENU,
    # так как этот обработчик предназначен только для обработки нажатий на кнопки
    query = update.callback_query
    if not query:
        return "HANDLE_MENU"

    # Отправляем пустой ответ на callback_query, чтобы убрать "часики" на кнопке
    query.answer()

    if query.data == 'back_to_menu':
        start(update, context)
        return "HANDLE_MENU"

    if query.data == 'show_cart':
        return show_cart(update, context)
    if query.data.startswith('add_to_cart:'):
        return handle_cart_action(update, context)

    # Получаем товар из кэша
    # Берем список товаров из bot_data, куда он был сохранен ранее
    products = context.bot_data['products']

    # Ищем товар в списке products, у которого id совпадает с данными из callback_query
    # next() вернет первый найденный элемент или None, если ничего не найдено
    # p['id'] преобразуется в строку для сравнения с query.data, который всегда строка
    product = next(
        (p for p in products if str(p['id']) == query.data),
        None
    )
    
    if not product:
        # Отправляем новое сообщение вместо редактирования
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Товар не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Назад в меню", callback_data='back_to_menu')
            ]])
        )
        query.message.delete()
        return "HANDLE_MENU"
    
    # Формируем сообщение
    message = (
        f"{product['title']}\n"
        f"Цена: {product.get('price', 'не указана')} руб.\n"
        f"{product.get('description', '')}"
    )
    
    keyboard = [[
        InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu'),
        InlineKeyboardButton("✔ В корзину", callback_data=f'add_to_cart:{product["id"]}'),
        InlineKeyboardButton("🛒 Моя корзина", callback_data='show_cart')
    ]]
    
    # Получаем картинку
    image_data = None
    image_data = get_product_image(
        context.bot_data['strapi_url'],
        product['small_image_url']
    )
    # Отправляем сообщение
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

    query.message.delete()
    return "HANDLE_DESCRIPTION"


def show_cart(update, context: CallbackContext):
    """Показывает содержимое корзины пользователя."""
    query = update.callback_query
    chat_id = str(query.message.chat_id)

    try:
        # Получаем токен и URL из контекста
        strapi_api_token = context.bot_data['strapi_api_token']
        strapi_url = context.bot_data['strapi_url']
        
        # Получаем корзину пользователя
        cart_id = get_cart(
            chat_id,
            strapi_api_token,
            strapi_url
        )
        
        # Удаляем предыдущее сообщение
        try:
            query.message.delete()
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения: {e}")
            
        # Формируем сообщение и кнопки
        if not cart_id:
            # Если корзина не найдена
            message_text = "Ваша корзина пуста"
        else:
            # Получаем товары из корзины
            cart_data = get_products_from_cart(
                chat_id,
                strapi_api_token,
                strapi_url
            )
            message_text = format_cart_content(cart_data)
        
        # Отправляем сообщение с кнопкой возврата в меню
        context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu')
            ]])
        )

        return "HANDLE_MENU"
    except Exception as e:
        logger.error(f"Ошибка при показе корзины: {e}")
        context.bot.send_message(
            chat_id=chat_id,
            text="Произошла ошибка при отображении корзины",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu')
            ]])
        )
        return "HANDLE_MENU"


def handle_cart_action(update, context: CallbackContext):
    """Обрабатывает действия с корзиной (добавление товара)."""
    query = update.callback_query
    query.answer()
    tg_id = str(query.message.chat_id)

    # Извлекаем ID продукта из данных callback
    product_id = query.data.split(':')[1]
    
    # Получаем токен и URL из контекста
    strapi_api_token = context.bot_data['strapi_api_token']
    strapi_url = context.bot_data['strapi_url']
    
    # Создаём клиента, если его нет
    client_id = create_client(tg_id, strapi_api_token, strapi_url)
    
    # Получаем или создаём корзину
    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
    if not cart_id:
        cart_id = create_cart(tg_id, strapi_api_token, strapi_url)
    
    # Связываем клиента с корзиной
    connect_client_to_cart(client_id, cart_id, strapi_api_token, strapi_url)
    
    # Добавляем товар в корзину
    result = add_to_cart_item(tg_id, product_id, strapi_api_token, strapi_url)
    
    # Удаляем предыдущее сообщение
    try:
        query.message.delete()
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")
    
    # Сообщение о статусе операции
    message_text = "✅ Товар добавлен в корзину!" if result else "❌ Не удалось добавить товар в корзину."
        

    context.bot.send_message(
        chat_id=tg_id,
        text=message_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu'),
            InlineKeyboardButton("Корзина", callback_data='show_cart')
        ]])
    )
    
    return "HANDLE_MENU"


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
        'HANDLE_DESCRIPTION': handle_menu,  # Используем тот же обработчик
    }
    
    try:
        # Используем стандартный обработчик состояния
        state_handler = states_functions[user_state]
        next_state = state_handler(update, context)
        
        # Сохраняем новое состояние
        redis_db = context.bot_data.get('db')
        if redis_db and next_state:
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
            decode_responses=True 
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

    # Добавляем обработчик ошибок
    dispatcher.add_error_handler(error_handler)

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

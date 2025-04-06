import os
import logging
import redis
from dotenv import load_dotenv
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Filters, Updater, CallbackContext
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from strapi_service import (
    get_products, get_product_image, get_cart,
    add_to_cart_item, get_products_from_cart, create_client, connect_client_to_cart,
    create_cart, format_cart_content, delete_cart_item
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


def start(update: Updater, context: CallbackContext, strapi_api_token: str, strapi_url: str):
    """Обработчик команды старт, показывает приветственное сообщение и меню продуктов"""
    if 'products' not in context.bot_data or (update.message and update.message.text == '/start'):
        products = get_products(strapi_api_token, strapi_url)
        context.bot_data['products'] = products
        
        if update.message and update.message.text == '/start':
            tg_id = str(update.message.from_user.id)
            client_id = create_client(tg_id, strapi_api_token, strapi_url)
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
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=menu_prompt,
            reply_markup=reply_markup
        )
        query.message.delete()

    return 'HANDLE_MENU'


def handle_menu(update, context: CallbackContext, strapi_api_token: str, strapi_url: str):
    """Обработчик выбора товара."""
    # Если пользователь отправил обычное текстовое сообщение, а не нажал на кнопку,
    # то callback_query будет None. В этом случае мы просто возвращаемся в состояние HANDLE_MENU,
    # так как этот обработчик предназначен только для обработки нажатий на кнопки
    query = update.callback_query
    if not query:
        return "HANDLE_MENU"
    query.answer()

    if query.data == 'back_to_menu':
        start(update, context, strapi_api_token, strapi_url)
        return "HANDLE_MENU"

    if query.data == 'show_cart':
        show_cart(update, context, strapi_api_token, strapi_url)
        return "GET_CART_MENU"
    if query.data == 'clear_cart':
        clear_cart(update, context, strapi_api_token, strapi_url)
        return "GET_CART_MENU"
    if query.data.startswith('add_to_cart:'):
        handle_cart_action(update, context, strapi_api_token, strapi_url)
        return "GET_CART_MENU"
    
    if query.data.startswith('delete_item:'):
        handle_delete_item(update, context, strapi_api_token, strapi_url)
        return "GET_CART_MENU"

    products = context.bot_data['products']

    # Ищем товар в списке products, у которого id совпадает с данными из callback_query
    # next() вернет первый найденный элемент или None, если ничего не найдено
    # p['id'] преобразуется в строку для сравнения с query.data, который всегда строка
    product = next(
        (p for p in products if str(p['id']) == query.data),
        None
    )

    if not product:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Товар не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Назад в меню", callback_data='back_to_menu')
            ]])
        )
        query.message.delete()
        return "HANDLE_MENU"

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
        strapi_url,
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


def safe_delete_message(message, log_prefix=""):
    """Функция безопасного удаления сообщений с обработкой ошибок."""
    try:
        message.delete()
    except Exception as e:
        logger.error(f"{log_prefix}Ошибка при удалении сообщения: {e}")


def display_cart(chat_id, strapi_api_token, strapi_url):
    """Вспомогательная функция для формирования отображения содержимого корзины.
    
    Returns:
        tuple: (текст сообщения, разметка кнопок)
    """
    cart_id = get_cart(
        chat_id,
        strapi_api_token,
        strapi_url
    )
    
    if not cart_id:
        message_text = "Ваша корзина пуста"
        product_buttons = []
    else:
        cart_data = get_products_from_cart(
            chat_id,
            strapi_api_token,
            strapi_url
        )
        message_text = format_cart_content(cart_data)
        
        product_buttons = [
            [InlineKeyboardButton(
                f"❌ Удалить {item['title'][:20]}{'...' if len(item['title']) > 20 else ''}",
                callback_data=f"delete_item:{item['cart_item_id']}"
            )]
            for item in cart_data
        ]
    
    navigation_buttons = [
        InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu'),
        InlineKeyboardButton("Очистить корзину", callback_data='clear_cart')
    ]
    
    buttons = product_buttons + [navigation_buttons]
    markup = InlineKeyboardMarkup(buttons)
    
    return message_text, markup


def show_cart(update, context: CallbackContext, strapi_api_token: str, strapi_url: str):
    """Показывает содержимое корзины пользователя."""
    query = update.callback_query
    chat_id = str(query.message.chat_id)

    try:
        safe_delete_message(query.message, "show_cart: ")
            
        message_text, markup = display_cart(chat_id, strapi_api_token, strapi_url)
        
        context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=markup
        )

        return "GET_CART_MENU"
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


def handle_cart_action(update, context: CallbackContext, strapi_api_token: str, strapi_url: str):
    """Обрабатывает действия с корзиной (добавление товара)."""
    query = update.callback_query
    query.answer()
    tg_id = str(query.message.chat_id)

    product_id = query.data.split(':')[1]
    
    client_id = create_client(tg_id, strapi_api_token, strapi_url)
    
    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
    if not cart_id:
        cart_id = create_cart(tg_id, strapi_api_token, strapi_url)
    
    connect_client_to_cart(client_id, cart_id, strapi_api_token, strapi_url)
    
    result = add_to_cart_item(tg_id, product_id, strapi_api_token, strapi_url)
    
    try:
        query.message.delete()
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")
    
    message_text = "✅ Товар добавлен в корзину!" if result else "❌ Не удалось добавить товар в корзину."
        
    context.bot.send_message(
        chat_id=tg_id,
        text=message_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu'),
            InlineKeyboardButton("Корзина", callback_data='show_cart')
        ]])
    )
    
    return "GET_CART_MENU"


def handle_delete_item(update, context: CallbackContext, strapi_api_token: str, strapi_url: str):
    """Обрабатывает удаление отдельного товара из корзины."""
    query = update.callback_query
    tg_id = str(query.message.chat_id)
    
    cart_item_id = query.data.split(':')[1]
    
    try:
        result = delete_cart_item(
            cart_item_id=cart_item_id, 
            strapi_api_token=strapi_api_token, 
            strapi_url=strapi_url
        )
        
        safe_delete_message(query.message, "handle_delete_item: ")
        
        if not result:
            context.bot.send_message(
                chat_id=tg_id,
                text="❌ Не удалось изменить количество товара",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Назад в корзину", callback_data='show_cart')
                ]])
            )
            return "GET_CART_MENU"
        
        message_text, markup = display_cart(tg_id, strapi_api_token, strapi_url)
        
        context.bot.send_message(
            chat_id=tg_id,
            text=message_text,
            reply_markup=markup
        )
        
        return "GET_CART_MENU"
        
    except Exception as e:
        logger.error(f"Ошибка при удалении товара: {e}")
        context.bot.send_message(
            chat_id=tg_id,
            text="Произошла ошибка при обработке товара",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в корзину", callback_data='show_cart')
            ]])
        )
        return "GET_CART_MENU"


def clear_cart(update, context: CallbackContext, strapi_api_token: str, strapi_url: str):
    """Обработчик для очистки корзины пользователя."""
    query = update.callback_query
    tg_id = str(query.message.chat_id)

    try:
        result = delete_cart_item(
            tg_id=tg_id, 
            strapi_api_token=strapi_api_token, 
            strapi_url=strapi_url, 
            delete_all=True
        )
        
        safe_delete_message(query.message, "clear_cart: ")
        
        if result:
            message_text = "✅ Корзина успешно очищена!"
        else:
            message_text = (
                "❌ Не удалось очистить корзину. "
                "Пожалуйста, попробуйте позже."
            )
        
        context.bot.send_message(
            chat_id=tg_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в меню", 
                                   callback_data='back_to_menu'),
                InlineKeyboardButton("Показать корзину", 
                                   callback_data='show_cart')
            ]])
        )
        
        return "GET_CART_MENU"
        
    except Exception as e:
        logger.error(f"Ошибка при очистке корзины: {e}")
        context.bot.send_message(
            chat_id=tg_id,
            text="Произошла ошибка при очистке корзины",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu')
            ]])
        )
        return "HANDLE_MENU"


def handle_users_reply(update, context):
    """
    Функция, которая запускается при любом сообщении от пользователя и решает как его обработать.
    """
    strapi_api_token = context.bot_data['strapi_api_token']
    strapi_url = context.bot_data['strapi_url']
    redis_db = context.bot_data.get('db')

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
        user_state = redis_db.get(chat_id) if redis_db else None
        if user_state is None:
            user_state = 'START'
        else:
            user_state = user_state.decode("utf-8")

    states_functions = {
        'START': partial(start, strapi_api_token=strapi_api_token, strapi_url=strapi_url),
        'HANDLE_MENU': partial(handle_menu, strapi_api_token=strapi_api_token, strapi_url=strapi_url),
        'HANDLE_DESCRIPTION': partial(handle_menu, strapi_api_token=strapi_api_token, strapi_url=strapi_url),
        'GET_CART_MENU': partial(show_cart, strapi_api_token=strapi_api_token, strapi_url=strapi_url)
    }
    
    try:
        state_handler = states_functions[user_state]
        next_state = state_handler(update, context)
        
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
    
    logger.info("Запуск бота...")
    
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

    dispatcher.add_error_handler(error_handler)

    dispatcher.bot_data['strapi_api_token'] = strapi_api_token
    dispatcher.bot_data['strapi_url'] = strapi_url
    dispatcher.bot_data['db'] = db

    start_handler = partial(start, strapi_api_token=strapi_api_token, strapi_url=strapi_url)
    menu_handler = partial(handle_menu, strapi_api_token=strapi_api_token, strapi_url=strapi_url)
    
    dispatcher.add_handler(CommandHandler('start', start_handler))
    dispatcher.add_handler(CallbackQueryHandler(menu_handler))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

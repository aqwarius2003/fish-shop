import os
import logging
import redis
from email_validator import EmailNotValidError, validate_email
from environs import Env
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Filters, Updater, CallbackContext
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from strapi_service import (
    get_products, get_product_image, get_cart,
    add_to_cart_item, get_products_from_cart, create_client,
    create_cart, format_cart_content, delete_cart_item
)


STATE_START = 'START'
STATE_HANDLE_MENU = 'HANDLE_MENU'
STATE_HANDLE_DESCRIPTION = 'HANDLE_DESCRIPTION'
STATE_GET_CART_MENU = 'GET_CART_MENU'
STATE_WAITING_EMAIL = 'WAITING_EMAIL'


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


_database = None


def get_database_connection(host, port, password):
    """Возвращает подключение к Redis."""
    global _database
    if _database is None:
        _database = redis.Redis(
            host=host, port=port, password=password, decode_responses=True
        )
    return _database

def start(update, context, strapi_api_token, strapi_url):
    """Показывает меню товаров."""
    if 'products' not in context.bot_data or (update.message and update.message.text == '/start'):
        products = get_products(strapi_api_token, strapi_url)
        context.bot_data['products'] = products
    else:
        products = context.bot_data['products']

    product_buttons = [
        [InlineKeyboardButton(product.get('title'), callback_data=str(product.get('id')))]
        for product in products
    ]
    product_buttons.append([
        InlineKeyboardButton("🛒 Моя корзина", callback_data='show_cart')
    ])

    if update.message:
        update.message.reply_text("Выберите товар:", reply_markup=InlineKeyboardMarkup(product_buttons))
    else:
        query = update.callback_query
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Товары списком:",
            reply_markup=InlineKeyboardMarkup(product_buttons)
        )
        try:
            query.message.delete()
        except:
            pass

    return STATE_HANDLE_MENU


def handle_menu(update, context, strapi_api_token, strapi_url):
    """Обработчик выбора товара."""
    query = update.callback_query
    if not query:
        return STATE_HANDLE_MENU

    query.answer()
    logger.info(f"handle_menu вызван с query.data = '{query.data}'")

    if query.data == 'back_to_menu':
        return start(update, context, strapi_api_token, strapi_url)
    if query.data == 'show_cart':
        return show_cart(update, context, strapi_api_token, strapi_url)
    if query.data.startswith('add_to_cart:'):
        return handle_cart_action(update, context, strapi_api_token, strapi_url)

    products = context.bot_data['products']
    product = next((p for p in products if str(p['id']) == query.data), None)
    if not product:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Товар не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Назад в меню", callback_data='back_to_menu')
            ]])
        )
        query.message.delete()
        return STATE_HANDLE_MENU

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

    image_data = get_product_image(strapi_url, product['small_image_url'])
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

    try:
        query.message.delete()
    except:
        pass
    return STATE_HANDLE_DESCRIPTION


def show_cart(update, context, strapi_api_token, strapi_url):
    """Показывает корзину пользователя."""
    chat_id = update.callback_query.message.chat_id if update.callback_query else update.message.chat_id
    tg_id = str(chat_id)

    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)

    if not cart_id:
        message_text = "Ваша корзина пуста"
        product_buttons = []
    else:
        cart_data = get_products_from_cart(tg_id, strapi_api_token, strapi_url)
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

    if cart_id and product_buttons:
        product_buttons.append([
            InlineKeyboardButton("💳 Оплатить", callback_data='checkout')
        ])
        logger.info(f"Добавлена кнопка Оплатить с callback_data='checkout' для корзины {cart_id}")

    buttons = product_buttons + [navigation_buttons]
    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        try:
            update.callback_query.message.delete()
        except:
            pass

    context.bot.send_message(
        chat_id=chat_id,
        text=message_text,
        reply_markup=markup
    )

    return STATE_GET_CART_MENU


def handle_cart_action(update, context, strapi_api_token, strapi_url):
    """Добавляет товар в корзину."""
    query = update.callback_query
    tg_id = str(query.message.chat_id)
    product_id = query.data.split(':')[1]

    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
    if not cart_id:
        cart_id = create_cart(tg_id, strapi_api_token, strapi_url)

    add_to_cart_item(tg_id, product_id, strapi_api_token, strapi_url)
    try:
        query.message.delete()
    except:
        pass

    context.bot.send_message(
        chat_id=tg_id,
        text="✅ Товар добавлен в корзину!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu'),
            InlineKeyboardButton("Корзина", callback_data='show_cart')
        ]])
    )

    return STATE_GET_CART_MENU


def handle_delete_item(update, context, strapi_api_token, strapi_url):
    """Удаляет товар из корзины."""
    query = update.callback_query
    tg_id = str(query.message.chat_id)
    cart_item_id = query.data.split(':')[1]

    delete_cart_item(
        cart_item_id=cart_item_id, 
        strapi_api_token=strapi_api_token, 
        strapi_url=strapi_url
    )

    return show_cart(update, context, strapi_api_token, strapi_url)


def clear_cart(update, context, strapi_api_token, strapi_url):
    """Очищает корзину пользователя."""
    query = update.callback_query
    tg_id = str(query.message.chat_id)

    delete_cart_item(
        tg_id=tg_id, 
        strapi_api_token=strapi_api_token, 
        strapi_url=strapi_url, 
        delete_all=True
    )

    try:
        query.message.delete()
    except:
        pass

    context.bot.send_message(
        chat_id=tg_id,
        text="✅ Корзина очищена!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu'),
            InlineKeyboardButton("Показать корзину", callback_data='show_cart')
        ]])
    )

    return STATE_GET_CART_MENU


def handle_email_input(update, context, strapi_api_token, strapi_url):
    """Обрабатывает ввод email."""
    if not update.message:
        return STATE_HANDLE_MENU

    email = update.message.text
    chat_id = str(update.effective_user.id)

    try:
        valid = validate_email(email, check_deliverability=False)
        normalized_email = valid.normalized
        create_client(chat_id, strapi_api_token, strapi_url, normalized_email)

        try:
            update.message.delete()
            context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id - 1)
        except Exception:
            pass

        context.bot.send_message(
            chat_id=chat_id,
            text=f"Ваш email {normalized_email} принят. Заказ оформлен."
        )

        return start(update, context, strapi_api_token, strapi_url)

    except EmailNotValidError:
        context.bot.send_message(
            chat_id=chat_id,
            text="Неверный формат email. Пожалуйста, введите корректный email:"
        )
        return STATE_WAITING_EMAIL


def delete_message(update, context):
    """Удаляет сообщение, если это возможно"""
    try:
        if update.callback_query:
            update.callback_query.message.delete()
    except Exception:
        pass


def handle_users_reply(update, context):
    """Единая функция обработки сообщений пользователя."""
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

    user_state = STATE_START if user_reply == '/start' else (redis_db.get(chat_id) if redis_db else STATE_START)
    if not user_state:
        user_state = STATE_START

    logger.info(f"Обработка сообщения от пользователя {chat_id}, состояние: {user_state}")

    if update.callback_query:
        if user_reply.startswith('delete_item:'):
            delete_message(update, context)
            next_state = handle_delete_item(update, context, strapi_api_token, strapi_url)
            if next_state and redis_db:
                redis_db.set(chat_id, next_state)
            return

        if user_reply == 'clear_cart':
            delete_message(update, context)
            next_state = clear_cart(update, context, strapi_api_token, strapi_url)
            if next_state and redis_db:
                redis_db.set(chat_id, next_state)
            return

        if user_reply == 'back_to_menu':
            delete_message(update, context)
            next_state = start(update, context, strapi_api_token, strapi_url)
            if next_state and redis_db:
                redis_db.set(chat_id, next_state)
            return

        if user_reply == 'checkout':
            delete_message(update, context)
            context.bot.send_message(
                chat_id=chat_id,
                text="Пожалуйста, введите ваш email для оформления заказа:"
            )
            if redis_db:
                redis_db.set(chat_id, STATE_WAITING_EMAIL)
            return

    states_functions = {
        STATE_START: partial(start, strapi_api_token=strapi_api_token, strapi_url=strapi_url),
        STATE_HANDLE_MENU: partial(handle_menu, strapi_api_token=strapi_api_token, strapi_url=strapi_url),
        STATE_HANDLE_DESCRIPTION: partial(handle_menu, strapi_api_token=strapi_api_token, strapi_url=strapi_url),
        STATE_GET_CART_MENU: partial(show_cart, strapi_api_token=strapi_api_token, strapi_url=strapi_url),
        STATE_WAITING_EMAIL: partial(handle_email_input, strapi_api_token=strapi_api_token, strapi_url=strapi_url)
    }

    state_handler = states_functions.get(user_state, states_functions[STATE_START])
    next_state = state_handler(update, context)

    if next_state and redis_db:
        redis_db.set(chat_id, next_state)


def main():
    """Запуск бота."""
    env = Env()
    env.read_env()
    strapi_url = env.str('STRAPI_URL')
    strapi_api_token = env.str('STRAPI_API_TOKEN')
    database_host = env.str("REDIS_HOST")
    database_port = env.str("REDIS_DATABASE_PORT")
    database_password = env.str("REDIS_DATABASE_PASSWORD")
    token = env.str("TG_BOT_TOKEN")

    logger.info("Запуск бота...")

    db = get_database_connection(database_host, database_port, database_password)

    updater = Updater(token)
    dispatcher = updater.dispatcher

    dispatcher.bot_data['strapi_api_token'] = strapi_api_token
    dispatcher.bot_data['strapi_url'] = strapi_url
    dispatcher.bot_data['db'] = db

    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_users_reply))
    dispatcher.add_error_handler(lambda update, context: logger.error(f"Ошибка: {context.error}"))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

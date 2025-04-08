import os
import logging
from io import BytesIO
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional, Union

import requests
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

def get_products(strapi_api_token: str, strapi_url: str) -> List[Dict[str, Any]]:
    """Получает список продуктов из Strapi CMS только с нужными полями."""
    logger.info("Вызвана функция get_products")
    products_url = urljoin(strapi_url, '/api/products')
    headers = {'Authorization': f'Bearer {strapi_api_token}'}

    params = {
        'fields': ['id', 'title', 'description', 'price'],
        'populate': {
            'picture': {
                'fields': ['formats.small.url']
            }
        }
    }

    response = requests.get(products_url, headers=headers, params=params)
    response.raise_for_status()
    items = response.json()
    
    # API возвращает список товаров напрямую
    products = [
        {
            'id': item.get('id'),
            'title': item.get('title'),
            'description': item.get('description'),
            'price': item.get('price'),
            'small_image_url': item.get('picture', {}).get('formats', {}).get('small', {}).get('url')
        }
        for item in items
    ]

    return products


def get_product_image(strapi_url: str, image_url: str) -> BytesIO:
    """Получает картинку товара по URL."""
    full_image_url = urljoin(strapi_url, image_url)
    response = requests.get(full_image_url)
    response.raise_for_status()
    return BytesIO(response.content)


def create_client(tg_id: str, strapi_api_token: str, strapi_url: str, email: str) -> Optional[int]:
    """
    Создает нового клиента с указанным tg_id и email,
    или возвращает ID существующего клиента.
    """
    url = urljoin(strapi_url, '/api/clients')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }

    # Ищем существующего клиента
    params = {"filters[tg_id][$eq]": tg_id}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    clients = response.json()
    
    # Если клиент существует, возвращаем его ID
    if clients and len(clients) > 0:
        return clients[0]['id']
    
    # Создаем нового клиента
    data = {
        "tg_id": tg_id,
        "email": email
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    client_data = response.json()
    
    # Возвращаем ID нового клиента
    if 'id' in client_data:
        return client_data['id']
    
    return client_data['data']['id']


def create_cart(tg_id: str, strapi_api_token: str, strapi_url: str) -> Optional[int]:
    """Создает новую корзину для пользователя."""
    url = urljoin(strapi_url, '/api/carts')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "tg_id": tg_id
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    return response.json()['id']


def get_cart(tg_id: str, strapi_api_token: str, strapi_url: str) -> Optional[int]:
    """Получает ID корзины по tg_id пользователя."""
    url = urljoin(strapi_url, '/api/carts')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }

    params = {
        "filters[tg_id][$eq]": tg_id
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    carts = response.json()

    if carts and len(carts) > 0:
        return carts[0]['id']

    return None


def find_cart_item(cart_id: int, product_id: int, strapi_api_token: str, strapi_url: str) -> List[Dict[str, Any]]:
    """Поиск товара в корзине."""
    url = urljoin(strapi_url, '/api/cart-items')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }

    params = {
        "filters[cart][id][$eq]": cart_id,
        "filters[product][id][$eq]": product_id
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()


def add_to_cart_item(tg_id: str, product_id: Union[int, str], strapi_api_token: str, strapi_url: str, quantity: int = 1) -> Optional[int]:
    """Добавляет товар в корзину и связывает с корзиной."""
    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
    if not cart_id:
        cart_id = create_cart(tg_id, strapi_api_token, strapi_url)

    # Ищем товар в корзине
    url_check = urljoin(strapi_url, '/api/cart-items')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }

    params_check = {
        "filters[cart][id][$eq]": cart_id,
        "filters[product][id][$eq]": product_id
    }

    check_response = requests.get(url_check, headers=headers, params=params_check)
    check_response.raise_for_status()
    check_data = check_response.json()

    if check_data and len(check_data) > 0:
        cart_item_id = check_data[0]['id']
        current_quantity = check_data[0]['quantity']

        url_update = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
        update_data = {
            "quantity": current_quantity + quantity
        }
        update_response = requests.put(url_update, headers=headers, json=update_data)
        update_response.raise_for_status()

        return cart_item_id

    url = urljoin(strapi_url, '/api/cart-items')
    data = {
        "product": product_id,
        "cart": cart_id,
        "quantity": quantity
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    # API всегда возвращает объект с ID напрямую
    return response.json()['id']


def get_products_from_cart(tg_id: str, strapi_api_token: str, strapi_url: str) -> List[Dict[str, Any]]:
    """Получает товары из корзины пользователя."""
    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
    if not cart_id:
        return []

    url = urljoin(strapi_url, '/api/cart-items')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }

    params = {
        "filters[cart][id][$eq]": cart_id,
        "populate": "product"
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    cart_items = response.json()

    result = []
    for item in cart_items:
        if 'product' in item and 'quantity' in item:
            product = item['product']
            quantity = item['quantity']

            result.append({
                'id': product.get('id'),
                'title': product.get('title', 'Название отсутствует'),
                'price': product.get('price', 0),
                'quantity': quantity,
                'cart_item_id': item.get('id')
            })

    return result


def format_cart_content(cart_items: List[Dict[str, Any]]) -> str:
    """Форматирует содержимое корзины для отображения."""
    if not cart_items:
        return "Корзина пуста"

    total_sum = 0
    result = "Ваша корзина:\n\n"

    for item in cart_items:
        title = item.get('title', 'Название отсутствует')
        price = item.get('price', 0)
        quantity = item.get('quantity', 1)
        item_total = price * quantity
        total_sum += item_total

        result += f"• {title}\n"
        result += f"  {quantity} шт. × {price} руб. = {item_total} руб.\n\n"

    result += f"Итого: {total_sum} руб."
    return result


def delete_cart_item(cart_item_id: Optional[Union[int, str]] = None, 
                  tg_id: Optional[str] = None, 
                  strapi_api_token: str = None, 
                  strapi_url: str = None, 
                  delete_all: bool = False) -> bool:
    """Функция для удаления товаров из корзины.

    Может работать в двух режимах:
    1. Если указан cart_item_id - удаляет или уменьшает количество конкретного товара
    2. Если указан tg_id и delete_all=True - удаляет все товары из корзины пользователя
    """
    if not strapi_api_token or not strapi_url:
        logger.error("API токен или URL Strapi не указаны")
        return False

    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }

    # Режим 1: Работа с конкретным товаром в корзине
    if cart_item_id:
        try:
            get_url = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
            get_response = requests.get(get_url, headers=headers)
            get_response.raise_for_status()

            cart_item = get_response.json()
            current_quantity = cart_item.get('quantity', 1)

            if current_quantity <= 1 or delete_all:
                delete_url = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
                delete_response = requests.delete(delete_url, headers=headers)
                delete_response.raise_for_status()
            else:
                update_url = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
                update_data = {"quantity": current_quantity - 1}
                update_response = requests.put(update_url, headers=headers, json=update_data)
                update_response.raise_for_status()

            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении товара: {e}", exc_info=True)
            return False

    # Режим 2: Удаление всех товаров из корзины пользователя
    elif tg_id and delete_all:
        try:
            cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
            if not cart_id:
                return True  # Если корзины нет, считаем задачу выполненной

            cart_items_url = urljoin(strapi_url, '/api/cart-items')
            params = {"filters[cart][id][$eq]": cart_id}

            items_response = requests.get(cart_items_url, headers=headers, params=params)
            items_response.raise_for_status()
            cart_items = items_response.json()

            if not cart_items:
                return True

            logger.info(f"Удаляем {len(cart_items)} товаров из корзины пользователя {tg_id}")

            for item in cart_items:
                item_id = item.get('id')
                delete_url = urljoin(strapi_url, f'/api/cart-items/{item_id}')
                delete_response = requests.delete(delete_url, headers=headers)
                delete_response.raise_for_status()

            return True
        except Exception as e:
            logger.error(f"Ошибка при очистке корзины: {e}", exc_info=True)
            return False

    else:
        logger.error("Не указаны необходимые параметры для работы с корзиной")
        return False

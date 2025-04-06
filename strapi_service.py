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

    try:
        response = requests.get(products_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get('data', data) if isinstance(data, dict) else data

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

    except Exception as e:
        logger.error(f"Ошибка при получении списка товаров: {e}")
        return []


def get_product_image(strapi_url: str, image_url: str) -> BytesIO:
    """Получает картинку товара по URL."""
    try:
        full_image_url = urljoin(strapi_url, image_url)
        response = requests.get(full_image_url)
        return BytesIO(response.content)
    except Exception as e:
        logger.error(f"Ошибка при получении картинки: {e}")
        return None


def create_client(tg_id: str, strapi_api_token: str, strapi_url: str) -> Optional[int]:
    """Создает клиента, если его еще нет в базе."""
    url = urljoin(strapi_url, '/api/clients')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }
    params = {
        "filters[tg_id][$eq]": tg_id
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    clients = data.get('data', data) if isinstance(data, dict) else data

    if clients and isinstance(clients, list) and clients:
        return clients[0]['id']
    
    data = {
        "tg_id": tg_id,
        "email": f"{tg_id}@telegram.bot"
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    resp_data = response.json()
    client_data = resp_data.get('data', resp_data) if isinstance(resp_data, dict) else resp_data
    
    if isinstance(client_data, dict) and 'id' in client_data:
        return client_data['id']
    return None


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

    resp_data = response.json()
    cart_data = resp_data.get('data', resp_data) if isinstance(resp_data, dict) else resp_data

    if isinstance(cart_data, dict) and 'id' in cart_data:
        return cart_data['id']
    return None


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

    data = response.json()
    carts = data.get('data', data) if isinstance(data, dict) else data

    if carts and isinstance(carts, list) and carts:
        return carts[0]['id']

    return None


def find_cart_item(cart_id: int, product_id: int, strapi_api_token: str, strapi_url: str) -> List[Dict[str, Any]]:
    """Поиск товара в корзине."""
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
    data = check_response.json()
    return data.get('data', data) if isinstance(data, dict) else data


def add_to_cart_item(tg_id: str, product_id: Union[int, str], strapi_api_token: str, strapi_url: str, quantity: int = 1) -> Optional[int]:
    """Добавляет товар в корзину и связывает с корзиной."""
    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
    if not cart_id:
        cart_id = create_cart(tg_id, strapi_api_token, strapi_url)

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
    data = check_response.json()
    check_data = data.get('data', data) if isinstance(data, dict) else data

    if check_data and isinstance(check_data, list) and check_data:
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
    
    resp_data = response.json()
    item_data = resp_data.get('data', resp_data) if isinstance(resp_data, dict) else resp_data
    
    if isinstance(item_data, dict) and 'id' in item_data:
        return item_data['id']
    return None
        

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
    
    data = response.json()
    cart_items = data.get('data', data) if isinstance(data, dict) else data
    
    result = []
    if cart_items and isinstance(cart_items, list):
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


def connect_client_to_cart(client_id: int, cart_id: int, strapi_api_token: str, strapi_url: str) -> bool:
    """Связывает клиента с корзиной."""
    if not client_id or not cart_id:
        return False
    
    url = urljoin(strapi_url, f'/api/carts/{cart_id}')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "client": client_id
    }
    
    response = requests.put(url, headers=headers, json=data)
    return response.status_code < 300


def format_cart_content(cart_items: List[Dict[str, Any]]) -> str:
    """Форматирует содержимое корзины для отображения.
    
    Returns:
        str: текстовое представление корзины
    """
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
    """Универсальная функция для работы с товарами в корзине.
    
    Может работать в нескольких режимах:
    1. Если указан cart_item_id, уменьшает количество товара на 1 или удаляет его, если он единственный
    2. Если указан tg_id и delete_all=True, удаляет все товары из корзины пользователя
    
    Args:
        cart_item_id: ID элемента корзины (не ID товара!)
        tg_id: ID пользователя в Telegram
        strapi_api_token: токен API Strapi
        strapi_url: базовый URL Strapi
        delete_all: если True, удаляет все товары из корзины
        
    Returns:
        bool: True, если операция успешна, иначе False
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
            # Сначала получаем текущее количество товара
            get_url = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
            get_response = requests.get(get_url, headers=headers)
            get_response.raise_for_status()
            
            cart_item = get_response.json()
            current_quantity = cart_item.get('quantity', 1)
            
            # Если товар всего один или нужно удалить все товары, удаляем его полностью
            if current_quantity <= 1 or delete_all:
                delete_url = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
                delete_response = requests.delete(delete_url, headers=headers)
                delete_response.raise_for_status()
                logger.info(f"Товар с ID {cart_item_id} полностью удален из корзины")
            else:
                # Если товаров несколько, уменьшаем количество на 1
                update_url = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
                update_data = {"quantity": current_quantity - 1}
                update_response = requests.put(update_url, headers=headers, json=update_data)
                update_response.raise_for_status()
                logger.info(f"Количество товара с ID {cart_item_id} уменьшено до {current_quantity - 1}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при работе с товаром в корзине: {e}")
            return False
    
    # Режим 2: Удаление всех товаров из корзины пользователя
    elif tg_id and delete_all:
        cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
        if not cart_id:
            return True  # Если корзины нет, считаем задачу выполненной
        
        try:
            cart_items_url = urljoin(strapi_url, '/api/cart-items')
            params = {"filters[cart][id][$eq]": cart_id}
            
            items_response = requests.get(cart_items_url, headers=headers, params=params)
            items_response.raise_for_status()
            cart_items = items_response.json()
            
            if not cart_items or not isinstance(cart_items, list) or not cart_items:
                return True
            
            logger.info(f"Удаляем {len(cart_items)} товаров из корзины пользователя {tg_id}")
            
            for item in cart_items:
                delete_url = urljoin(strapi_url, f'/api/cart-items/{item["id"]}')
                delete_response = requests.delete(delete_url, headers=headers)
                delete_response.raise_for_status()
            
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка API при очистке корзины: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при очистке корзины: {e}")
            return False
    
    else:
        logger.error("Не указаны необходимые параметры для работы с корзиной")
        return False


if __name__ == "__main__":
    load_dotenv()
    strapi_url = os.getenv('STRAPI_URL')
    strapi_api_token = os.getenv('STRAPI_API_TOKEN')

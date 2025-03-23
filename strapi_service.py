import os
import logging
from io import BytesIO
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


def get_products(strapi_api_token, strapi_url):
    """Получает список продуктов из Strapi CMS только с нужными полями."""
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
                # Если медиа отсутствует – вернётся None
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


def create_client(tg_id, strapi_api_token, strapi_url):
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
    clients = response.json()

    if clients and isinstance(clients, list) and len(clients) > 0:
        return clients[0]['id']
    
    # Клиент не найден, создаем нового
    data = {
        "tg_id": tg_id,
        "email": f"{tg_id}@telegram.bot"
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    resp_data = response.json()
    if isinstance(resp_data, dict) and 'id' in resp_data:
        return resp_data['id']
    return None


def create_cart(tg_id, strapi_api_token, strapi_url):
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
    if isinstance(resp_data, dict) and 'id' in resp_data:
        return resp_data['id']
    return None


def get_cart(tg_id, strapi_api_token, strapi_url):
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
    if carts and isinstance(carts, list) and len(carts) > 0:
        return carts[0]['id']
    
    return None


def find_cart_item(cart_id, product_id, strapi_api_token, strapi_url):
    """Поиск товара в корзине."""
    url_check = urljoin(strapi_url, '/api/cart-items')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }
    
    # Параметры для поиска товара в корзине
    params_check = {
        "filters[cart][id][$eq]": cart_id,
        "filters[product][id][$eq]": product_id
    }
    check_response = requests.get(url_check, headers=headers, params=params_check)
    check_response.raise_for_status()
    return check_response.json()


def add_to_cart_item(tg_id, product_id, strapi_api_token, strapi_url, quantity=1):
    """Добавляет товар в корзину и связывает с корзиной."""
    cart_id = get_cart(tg_id, strapi_api_token, strapi_url)
    if not cart_id:
        cart_id = create_cart(tg_id, strapi_api_token, strapi_url)
    
    url_check = urljoin(strapi_url, '/api/cart-items')
    headers = {
        'Authorization': f'Bearer {strapi_api_token}',
        'Content-Type': 'application/json'
    }
    
    # Параметры для поиска товара в корзине
    params_check = {
        "filters[cart][id][$eq]": cart_id,
        "filters[product][id][$eq]": product_id
    }
    
    check_response = requests.get(url_check, headers=headers, params=params_check)
    check_response.raise_for_status()
    check_data = check_response.json()
    
    if check_data and isinstance(check_data, list) and len(check_data) > 0:
        # Товар найден, обновляем количество
        cart_item_id = check_data[0]['id']
        current_quantity = check_data[0]['quantity']
        
        # Обновляем количество
        url_update = urljoin(strapi_url, f'/api/cart-items/{cart_item_id}')
        update_data = {
            "quantity": current_quantity + quantity
        }
        update_response = requests.put(url_update, headers=headers, json=update_data)
        update_response.raise_for_status()
        return cart_item_id
    
    # Если товар не найден, добавляем новый
    url = urljoin(strapi_url, '/api/cart-items')
    data = {
        "product": product_id,
        "cart": cart_id,
        "quantity": quantity
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    resp_data = response.json()
    if isinstance(resp_data, dict) and 'id' in resp_data:
        return resp_data['id']
    return None
        

def connect_cart_to_cart_item(cart_id, cart_item_id, strapi_api_token, strapi_url):
    """Связывает корзину cart_item с корзиной cart. 
    В Strapi 5.11 связь устанавливается при создании cart_item, поэтому эта функция теперь только для обратной совместимости."""
    # В Strapi 5.11 эта функция не нужна, так как связь устанавливается автоматически
    # при создании cart_item через поле "cart"
    return True


def get_products_from_cart(tg_id, strapi_api_token, strapi_url):
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
    
    # По логам видно, что данные приходят в виде списка объектов
    result = []
    cart_items = response.json()
    
    if cart_items and isinstance(cart_items, list):
        for item in cart_items:
            if 'product' in item and 'quantity' in item:
                product = item['product']
                quantity = item['quantity']
                result.append({
                    'id': product.get('id'),
                    'title': product.get('title', 'Название отсутствует'),
                    'price': product.get('price', 0),
                    'quantity': quantity
                })
    
    return result

def connect_client_to_cart(client_id, cart_id, strapi_api_token, strapi_url):
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


def get_cart_id(tg_id, strapi_api_token, strapi_url):
    """Получает ID корзины для пользователя."""
    return get_cart(tg_id, strapi_api_token, strapi_url)


def format_cart_content(cart_items):
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


if __name__ == "__main__":
    load_dotenv()
    strapi_url = os.getenv('STRAPI_URL')
    strapi_api_token = os.getenv('STRAPI_API_TOKEN')

import logging
import requests
from io import BytesIO
from urllib.parse import urljoin

logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_products(strapi_api_token, strapi_url):
    """Получает список продуктов из Strapi CMS только с нужными полями."""
    products_url = urljoin(strapi_url, '/api/products')
    headers = {'Authorization': f'Bearer {strapi_api_token}'}
    
    # Ограничиваем поля продукта и медиа
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

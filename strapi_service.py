import logging
import requests
from io import BytesIO
from urllib.parse import urljoin

logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_products(strapi_api_token, strapi_url):
    """Получает список продуктов из Strapi CMS с нужными полями."""
    products_url = urljoin(strapi_url, '/api/products')
    headers = {'Authorization': f'Bearer {strapi_api_token}'}
    
    # Запрашиваем только нужные поля и связи
    params = {
        'populate': {
            'picture': {
                'fields': ['url']  # Получаем только URL картинки, без лишних метаданных
            }
        },
        'fields': ['Title', 'price', 'description', 'documentId']
    }
    
    try:
        response = requests.get(products_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()['data']
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
        
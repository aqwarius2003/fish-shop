# Fish Shop Telegram Bot

Telegram бот для интернет-магазина рыбы с интеграцией Strapi CMS.

## Функциональность

- Просмотр каталога товаров
- Добавление товаров в корзину
- Управление корзиной (удаление, очистка)
- Оформление заказа с указанием email

## Технологии

- Python 3.8+
- Telegram Bot API
- Strapi CMS
- Redis для хранения состояний
- Docker (опционально)

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/aqwarius2003/fish-shop.git
cd fish-shop
```

### 2. Установка Node.js

⚠️ Важно: Node.js необходим для работы Strapi CMS.

- Установите [Node.js 18.20.7](https://nodejs.org/download/release/v18.20.7/)
- Проверьте установку: `node --version`

### 3. Установка Strapi CMS


```bash
# Создаем новый проект Strapi
npx create-strapi-app@5.11.2 fish-shop-cms --quickstart
```

### 4. Настройка Strapi

1. Откройте админ-панель: http://localhost:1337/admin
2. Создайте администратора
3. Настройте права доступа:
   - Settings → Users & Permissions → Roles → Public
   - Включите: find, findOne для Product
   - Включите: upload для Upload
4. Создайте API токен:
   - Settings → API Tokens
   - Name: Bot API Token
   - Type: Full access

### 5. Создание моделей данных

В админ-панели Strapi нужно создать следующие модели:

1. **Product** (Товар)
   - `title` (string) - название товара
   - `description` (text) - описание товара
   - `picture` (media) - изображение товара
   - `price` (number) - цена товара

2. **Cart** (Корзина)
   - `tg_id` (string) - ID пользователя в Telegram
   - Связь один-к-одному с моделью Client

3. **CartItem** (Элемент корзины)
   - `quantity` (number) - количество товара
   - Связь многие-к-одному с моделями Product и Cart

4. **Client** (Клиент)
   - `tg_id` (string) - ID пользователя в Telegram
   - `email` (email) - email клиента
   - Связь один-к-одному с моделью Cart

### 6. Установка Python

- Скачайте [Python 3.10+](https://www.python.org/downloads/)
- При установке отметьте "Add Python to PATH"
- Проверьте установку: `python --version`

### 7. Установка зависимостей Python

```bash
# Создаем виртуальное окружение
python -m venv .venv

# Активируем виртуальное окружение
# Для Windows:
.venv\Scripts\activate
# Для Mac/Linux:
source .venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 8. Настройка Redis

#### Windows
- Скачайте [Redis для Windows](https://github.com/microsoftarchive/redis/releases/latest)
- Установите как службу

#### Mac/Linux
```bash
# Mac
brew install redis

# Linux
sudo apt-get install redis-server
```

### 9. Настройка Telegram бота

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота
3. Создайте файл `.env` в папке проекта:
```env
TG_BOT_TOKEN=ваш_токен_бота
STRAPI_URL=http://localhost:1337
STRAPI_API_TOKEN=ваш_токен_strapi
REDIS_HOST=localhost
REDIS_DATABASE_PORT=6379
REDIS_DATABASE_PASSWORD=
```

## Запуск проекта

1. Запустите Redis
2. Запустите Strapi:
```bash
cd fish-shop-cms
npm run develop
```

3. В новом терминале запустите бота:
```bash
cd fish-shop
python tg_bot.py
```

## Структура проекта

- `tg_bot.py` - основной файл бота
- `strapi_service.py` - сервис для работы с Strapi API

## Возможные проблемы

1. `python not found` - проверьте PATH
2. `npm not found` - переустановите Node.js
3. Ошибки Strapi - проверьте версии (Node.js 18.20.7, Strapi 5.11.2)
4. Проблемы с Redis - проверьте запуск службы

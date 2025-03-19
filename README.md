# Fish Shop Bot

Телеграм-бот для онлайн магазина морепродуктов

## Подготовка окружения

### 1. Установка Python

1. Скачайте Python 3.10 или выше с [официального сайта](https://www.python.org/downloads/)
2. Запустите установщик
3. ✅ Обязательно поставьте галочку "Add Python to PATH" при установке
4. Нажмите "Install Now"
5. Проверьте установку, открыв командную строку (Win+R → cmd → Enter) и введите:
```bash
python --version
# Должно показать версию Python, например: Python 3.10.0
```

### 2. Установка Node.js

Рекомендуемый способ - установка через nvm (Node Version Manager):

#### Windows
1. Установите nvm-windows. Скачайте установщик [nvm-setup.exe](https://github.com/coreybutler/nvm-windows/releases/latest)
2. Запустите установщик и следуйте инструкциям
3. Откройте новое окно терминала и выполните команды:
```bash
# Установка нужной версии Node.js
nvm install 18.20.7

# Использование установленной версии
nvm use 18.20.7
```

#### Mac/Linux
1. Установите nvm через терминал:
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
```
2. Перезапустите терминал или выполните:
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```
3. Установите Node.js:
```bash
# Установка нужной версии Node.js
nvm install 18.20.7

# Использование установленной версии
nvm use 18.20.7
```

Альтернативный способ - установка через установщик:
1. Скачайте Node.js версии 18.20.7 с [официального сайта](https://nodejs.org/download/release/v18.20.7/):
   - Для Windows: node-v18.20.7-x64.msi
   - Для Mac: node-v18.20.7.pkg
2. Запустите установщик и следуйте инструкциям

После установки проверьте версии в терминале:
```bash
node --version
# Должно показать: v18.20.7

npm --version
# Должно показать версию npm, например: 9.9.2
```

### 3. Создание проекта

1. Скачайте проект с GitHub и перейдите в его папку:
```bash
# Скачиваем проект
git clone https://github.com/ваш-репозиторий/fish-shop.git
cd fish-shop

# Создаем виртуальное окружение Python
python -m venv .venv

# Активируем виртуальное окружение
# Для Windows:
.venv\Scripts\activate
# Для Mac/Linux:
source .venv/bin/activate

# Устанавливаем зависимости из requirements.txt
pip install -r requirements.txt
```

## Установка и настройка Strapi CMS

### 1. Создание проекта Strapi

```bash
# Создаем новый проект Strapi версии 5.11.1
npx create-strapi-app@5.11.2 fish-shop-cms --quickstart

# Когда установка завершится, автоматически откроется окно браузера
# Создайте административного пользователя:
# - Email: ваш_email
# - Password: придумайте_пароль (минимум 8 символов)
```

⚠️ Важно: Для корректной работы проекта необходимы именно эти версии:
- Node.js: 18.20.7
- Strapi: 5.11.1

### 2. Создание моделей данных

1. Скопируйте файл `createModels.js` в папку `fish-shop-cms`:
```bash
# Для Windows:
copy createModels.js fish-shop-cms\
```
# Для Mac/Linux:
```bash
cp createModels.js fish-shop-cms/
```

2. Перейдите в папку Strapi и запустите скрипт:
```bash
cd fish-shop-cms
node createModels.js
```

### 3. Настройка прав доступа

1. В браузере откройте админ-панель: http://localhost:1337/admin
2. Войдите с созданными ранее учетными данными
3. В левом меню найдите Settings (⚙️)
4. Выберите "Users & Permissions Plugin" → "Roles" → "Public"
5. Найдите секцию "Product" и включите галочки:
   - ✅ find
   - ✅ findOne
6. В секции "Upload" включите:
   - ✅ upload
7. Нажмите "Save" (💾) в правом верхнем углу

### 4. Создание API токена

1. В левом меню Settings (⚙️) выберите "API Tokens"
2. Нажмите "+ Create new API Token"
3. Заполните:
   - Name: Bot API Token
   - Description: Token for Telegram bot (можно пропустить)
   - Token duration: Unlimited
   - Token type: Full access
4. Нажмите "Save" (💾)
5. Скопируйте токен (больше его увидеть нельзя!)

### 5. Добавление тестовых товаров

1. В левом меню выберите "Content Manager"
2. Слева вверху нажмите "Collection Types" → "Product"
3. Нажмите "+ Create new entry"
4. Заполните поля:
   - Title: Название товара (например, "Семга слабосоленая")
   - Price: Цена (например, 1200)
   - Description: Описание товара
   - Picture: Перетащите фото товара или нажмите для выбора
5. Нажмите "Save" (💾)
6. Нажмите "Publish" (🌍)
7. Повторите для других товаров

### 6. Настройка переменных окружения

1. Создайте бота в Telegram:
   - Откройте [@BotFather](https://t.me/BotFather) в Telegram
   - Отправьте команду `/newbot`
   - Введите имя бота (например, "Fish Shop Bot")
   - Введите username бота (должен заканчиваться на 'bot', например "my_fish_shop_bot")
   - Сохраните полученный токен (например: `5555555555:AAHjYYYYYYYYYYYYYYYYYYYY`)

2. Установите Redis:
   - Для Windows: скачайте [Redis для Windows](https://github.com/microsoftarchive/redis/releases/latest)
   - Для Mac: `brew install redis`
   - Для Linux: `sudo apt-get install redis-server`

3. В папке `fish-shop` создайте файл `.env`:
```bash
# Для Windows:
echo. > .env
# Для Mac/Linux:
touch .env
```

4. Откройте файл в текстовом редакторе и добавьте:
```env
# Strapi
STRAPI_URL=http://localhost:1337
STRAPI_API_TOKEN=ваш_скопированный_токен_из_[пункта_4](#4-создание-api-токена)

# Telegram
TG_BOT_TOKEN=токен_полученный_от_[botfather](1. Создайте бота в Telegram:)

# Redis
REDIS_HOST=localhost
REDIS_DATABASE_PORT=6379
REDIS_DATABASE_PASSWORD=  # оставьте пустым для локальной разработки
```

### 7. Наполнение CMS тестовыми данными

Добавьте несколько товаров в Strapi CMS.

Добавьте 3-4 товара на ваш выбор например [сайта](https://svoe-rodnoe.ru), соблюдая структуру данных.

## Запуск

1. Запустите Redis:
   - Windows: Redis запускается как служба после установки
   - Mac/Linux: `redis-server`

2. Запустите Strapi (в первом терминале):
```bash
cd fish-shop-cms
npm run develop
```

3. В новом терминале запустите бота:
```bash
cd fish-shop
# Активируйте виртуальное окружение, если оно не активно:
# Для Windows:
.venv\Scripts\activate
# Для Mac/Linux:
source .venv/bin/activate

# Запустите бота
python tg_bot
```

## Возможные проблемы

1. `python not found` - Python не добавлен в PATH. Переустановите Python с галочкой "Add Python to PATH"
2. `npm not found` - Node.js не установлен или не добавлен в PATH. Переустановите Node.js
3. Ошибка при установке зависимостей Python - попробуйте обновить pip:
```bash
python -m pip install --upgrade pip
```

4. Не открывается админка Strapi - проверьте, что порт 1337 свободен:
```bash
# Для Windows:
netstat -ano | findstr :1337
# Для Mac/Linux:
lsof -i :1337
```


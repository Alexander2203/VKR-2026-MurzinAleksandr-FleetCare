# FleetCare - установка и запуск

## 1) Установить Python и PostgreSQL
- Скачайте и установите **Python 3.10+** с сайта python.org (отметьте “Add to PATH” на Windows).
- Установите **PostgreSQL 13+** (запомните логин/пароль `postgres` и порт, по умолчанию 5432).
- Создайте БД:

```sql
CREATE DATABASE fleetcare;
```

## 2) Клонирование проекта
```bash
git clone <repo_url> && cd fleetcare
```

## 3) Виртуальное окружение
**Windows (PowerShell):**
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 4) Установка зависимостей
```bash
pip install -r requirements.txt
```

## 5) .env - переменные окружения
Создайте файл `.env` в корне проекта:

```
# Django
DJANGO_SECRET_KEY=1223
POSTGRES_DB=fleetcare
POSTGRES_USER=postgres
POSTGRES_PASSWORD=1234
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Бот и API
API_BASE=http://127.0.0.1:8000/api
TELEGRAM_BOT_TOKEN=your_token
```

> При необходимости скорректируйте доступ к БД и адрес API.

## 6) Миграции БД
```bash
python manage.py makemigrations
python manage.py migrate
```

## 7) Создание администратора
```bash
python manage.py createsuperuser
```

## 8) Запуск веб-сервера (Django)
```bash
python manage.py runserver
```
Админка: `http://127.0.0.1:8000/admin/` (логин - суперпользователь из шага 7).

## 9) Запуск Telegram-бота
В новом терминале (с активным venv):
```bash
python bot.py
```

### Проверка
- В Telegram найдите своего бота (из BotFather), отправьте `/start`, поделитесь номером телефона (или введите).
- В админке добавьте **Driver** с вашим телефоном и привязанным **Automobile**.
- Создайте **Slot** (свободные окна).
- Проверьте сценарии: «Запись на ТО», «Отменить запись», «Информация о ТО».
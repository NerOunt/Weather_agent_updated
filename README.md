# Бот погоды

## Как пользоваться

После `/start` и `/help` бот показывает меню:

- `🌤 Погода сейчас`
- `📅 Прогноз на сегодня`
- `ℹ️ Помощь`

При запуске бот также регистрирует команды в меню Telegram:

- `/start`
- `/help`
- `/weather`
- `/today`

Reply-кнопки Telegram появляются после первого ответа бота. Это ограничение Telegram: бот не может показать такую клавиатуру пользователю до первого сообщения в чат.

Основной сценарий без ручного ввода команд:

1. Нажмите `🌤 Погода сейчас`.
2. Бот попросит ввести город.
3. Напишите `Казань`.
4. Бот покажет текущую погоду.

Другой вариант:

1. Нажмите `📅 Прогноз на сегодня`.
2. Напишите `Санкт-Петербург`.
3. Бот покажет краткий прогноз на сегодня.

Можно просто написать город обычным сообщением:

```text
Сочи
```

Бот ответит текущей погодой для Сочи.

## Команды

Команды оставлены как дополнительный способ:

- `/start` — запуск бота
- `/help` — список команд и кнопок
- `/weather` — погода сейчас для города по умолчанию
- `/weather <город>` — погода сейчас для указанного города
- `/today` — прогноз на сегодня для города по умолчанию
- `/today <город>` — прогноз на сегодня для указанного города

Если город не указан, используется `DEFAULT_CITY` из `.env`.

Примеры:

```text
/start
/help
/weather
/weather Москва
/weather Санкт-Петербург
/today
/today Казань
```

## Структура проекта

```text
weather-agent/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── bot.py
├── config.py
├── keyboards.py
├── weather.py
└── utils.py
```

## Создание Telegram-бота

1. Откройте Telegram и найдите `@BotFather`.
2. Отправьте команду `/newbot`.
3. Укажите название, например `Бот погоды`.
4. Укажите username для бота.
5. BotFather выдаст `TELEGRAM_BOT_TOKEN`.

Если Telegram token случайно опубликован:

1. Откройте `@BotFather`.
2. Отправьте `/mybots`.
3. Выберите нужного бота.
4. Откройте `API Token`.
5. Нажмите `Revoke current token`.
6. Новый token сохраните только в `.env`.

## Команды в BotFather

В `@BotFather` можно задать список команд через `/setcommands`:

```text
start - Запуск бота
help - Список команд
weather - Погода сейчас
today - Прогноз на сегодня
```

## Установка

Создайте виртуальное окружение:

```bash
python -m venv .venv
```

Активируйте его.

Windows:

```bat
.venv\Scripts\activate
```

Если PowerShell запрещает `Activate.ps1`, можно запускать Python напрямую:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

## Настройка .env

Создайте `.env` из примера:

```bash
cp .env.example .env
```

На Windows, если `cp` недоступен:

```powershell
Copy-Item .env.example .env
```

Заполните `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
WEATHER_API_KEY=your_openweather_api_key_here
DEFAULT_CITY=Москва
DEFAULT_TIMEZONE=Europe/Moscow
```

Не публикуйте `.env` в GitHub. Он добавлен в `.gitignore`.

## Запуск

```bash
python bot.py
```

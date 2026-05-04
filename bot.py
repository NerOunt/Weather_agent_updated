import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, MenuButtonCommands, Message, Update
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from ai_agent import handle_natural_language_query
from config import load_settings
from keyboards import (
    HELP_BUTTON,
    POPULAR_CITIES_BUTTON,
    TODAY_BUTTON,
    WEATHER_NOW_BUTTON,
    main_menu_keyboard,
    popular_cities_keyboard,
)
from utils import (
    extract_city_from_command,
    format_today_forecast,
    format_weather_message,
)
from weather import CityNotFoundError, OpenWeatherClient, WeatherError


START_TEXT = """Здравствуйте! Это Погодный бот 🌤

Бот показывает текущую погоду и краткий прогноз на сегодня для выбранного города.

Как пользоваться:
— нажмите «Погода сейчас», чтобы узнать текущую погоду;
— нажмите «Прогноз на сегодня», чтобы получить прогноз;
— выберите город из списка популярных;
— или просто напишите название города в чат.

Примеры:
Москва
Краснодар
Санкт-Петербург
Казань

Выберите нужное действие на клавиатуре ниже 👇"""

HELP_TEXT = """Справка по Погодному боту 🌤

Бот умеет показывать погоду для любого города.

Вы можете:
— нажать кнопку «Погода сейчас» и ввести город;
— нажать кнопку «Прогноз на сегодня» и ввести город;
— выбрать город из списка популярных;
— просто написать название города;
— задать вопрос обычным языком.

Примеры:
Краснодар
Какая погода сегодня в Москве?
Что надеть сегодня в Казани?
Будет ли дождь в Сочи?
Нужен ли зонт в Санкт-Петербурге?

Команды также доступны:
/weather <город> — текущая погода
/today <город> — прогноз на сегодня
/help — справка"""

CITY_NOT_FOUND_TEXT = "Не удалось найти город. Попробуйте написать иначе, например: Краснодар"
WEATHER_UNAVAILABLE_TEXT = "Не удалось получить погоду. Попробуйте позже."
AI_UNAVAILABLE_TEXT = "ИИ-обработка сейчас недоступна. Напишите город, например: Краснодар."
UNKNOWN_TEXT = (
    "Я могу помочь с погодой. Напишите город или задайте вопрос, например: "
    "Какая погода в Краснодаре?"
)
WEATHER_CITY_PROMPT = "Введите город, для которого нужно показать погоду сейчас."
TODAY_CITY_PROMPT = "Введите город, для которого нужно показать прогноз на сегодня."
BOT_COMMANDS = [
    BotCommand(command="start", description="Запуск бота"),
    BotCommand(command="help", description="Список команд"),
    BotCommand(command="weather", description="Погода сейчас"),
    BotCommand(command="today", description="Прогноз на сегодня"),
]
QUESTION_WORDS = {
    "какая",
    "какой",
    "какое",
    "что",
    "будет",
    "будут",
    "нужен",
    "нужна",
    "нужно",
    "надеть",
    "одеть",
    "погода",
    "погоду",
    "прогноз",
    "дождь",
    "зонт",
    "сегодня",
    "завтра",
    "покажи",
    "расскажи",
}


class CityInput(StatesGroup):
    waiting_for_weather_city = State()
    waiting_for_today_city = State()


logging.basicConfig(level=logging.INFO)

settings = load_settings()
weather_client = OpenWeatherClient(settings.weather_api_key)
bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()


def looks_like_city(text: str) -> bool:
    value = text.strip()
    if not value or "?" in value:
        return False

    lowered = value.lower()
    words = lowered.replace("-", " ").split()
    if any(word in QUESTION_WORDS for word in words):
        return False
    if len(words) > 3:
        return False

    return all(ch.isalpha() or ch in {" ", "-"} for ch in value)


async def send_current_weather(message: Message, city: str) -> None:
    try:
        weather = await weather_client.get_current_weather(city)
    except CityNotFoundError:
        await message.answer(CITY_NOT_FOUND_TEXT, reply_markup=main_menu_keyboard())
        return
    except WeatherError:
        await message.answer(WEATHER_UNAVAILABLE_TEXT, reply_markup=main_menu_keyboard())
        return

    await message.answer(format_weather_message(weather), reply_markup=main_menu_keyboard())


async def send_today_forecast(message: Message, city: str) -> None:
    try:
        forecast = await weather_client.get_today_forecast(city)
    except CityNotFoundError:
        await message.answer(CITY_NOT_FOUND_TEXT, reply_markup=main_menu_keyboard())
        return
    except WeatherError:
        await message.answer(WEATHER_UNAVAILABLE_TEXT, reply_markup=main_menu_keyboard())
        return

    await message.answer(format_today_forecast(forecast), reply_markup=main_menu_keyboard())


async def send_umbrella_advice(message: Message, city: str) -> None:
    try:
        forecast = await weather_client.get_today_forecast(city)
    except CityNotFoundError:
        await message.answer(CITY_NOT_FOUND_TEXT, reply_markup=main_menu_keyboard())
        return
    except WeatherError:
        await message.answer(WEATHER_UNAVAILABLE_TEXT, reply_markup=main_menu_keyboard())
        return

    if forecast.get("precipitation_possible"):
        advice = "Зонт лучше взять: сегодня возможны осадки."
    else:
        advice = "Зонт, скорее всего, не понадобится: заметных осадков в прогнозе нет."

    await message.answer(
        f"{advice}\n\n{format_today_forecast(forecast)}",
        reply_markup=main_menu_keyboard(),
    )


async def handle_ai_weather_query(message: Message, text: str) -> None:
    result = await handle_natural_language_query(text, settings.default_city)
    intent = result.get("intent")
    city = result.get("city") or settings.default_city

    if result.get("error") == "groq_unavailable":
        await message.answer(AI_UNAVAILABLE_TEXT, reply_markup=main_menu_keyboard())
        return

    if result.get("error") == "groq_error":
        await send_current_weather(message, text)
        return

    if intent == "current_weather":
        await send_current_weather(message, city)
        return
    if intent == "today_forecast":
        await send_today_forecast(message, city)
        return
    if intent == "clothing_advice":
        await send_current_weather(message, city)
        return
    if intent == "umbrella_advice":
        await send_umbrella_advice(message, city)
        return
    if intent == "help":
        await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())
        return

    await message.answer(UNKNOWN_TEXT, reply_markup=main_menu_keyboard())


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(START_TEXT, reply_markup=main_menu_keyboard())


@dp.message(Command("help"))
async def help_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())


@dp.message(Command("weather"))
async def weather_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    city = extract_city_from_command(message.text, settings.default_city)
    await send_current_weather(message, city)


@dp.message(Command("today"))
async def today_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    city = extract_city_from_command(message.text, settings.default_city)
    await send_today_forecast(message, city)


@dp.message(F.text == WEATHER_NOW_BUTTON)
async def weather_button_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(CityInput.waiting_for_weather_city)
    await message.answer(WEATHER_CITY_PROMPT, reply_markup=main_menu_keyboard())


@dp.message(F.text == TODAY_BUTTON)
async def today_button_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(CityInput.waiting_for_today_city)
    await message.answer(TODAY_CITY_PROMPT, reply_markup=main_menu_keyboard())


@dp.message(F.text == POPULAR_CITIES_BUTTON)
async def popular_cities_button_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выберите город:", reply_markup=popular_cities_keyboard())


@dp.message(F.text == HELP_BUTTON)
async def help_button_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())


@dp.callback_query(F.data.startswith("popular_city:"))
async def popular_city_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    city = callback.data.split(":", maxsplit=1)[1]
    await callback.answer()

    if callback.message is not None:
        await send_current_weather(callback.message, city)


@dp.message(CityInput.waiting_for_weather_city)
async def weather_city_input_handler(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if not city:
        await message.answer(WEATHER_CITY_PROMPT, reply_markup=main_menu_keyboard())
        return

    await state.clear()
    await send_current_weather(message, city)


@dp.message(CityInput.waiting_for_today_city)
async def today_city_input_handler(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if not city:
        await message.answer(TODAY_CITY_PROMPT, reply_markup=main_menu_keyboard())
        return

    await state.clear()
    await send_today_forecast(message, city)


@dp.message(F.text)
async def plain_city_text_handler(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    await state.clear()
    if looks_like_city(text):
        await send_current_weather(message, text)
        return

    await handle_ai_weather_query(message, text)


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "OK"


@app.get("/health/", response_class=PlainTextResponse)
async def health_with_slash() -> str:
    return "OK"


@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "OK"


@app.head("/")
async def root_head() -> PlainTextResponse:
    return PlainTextResponse("")


@app.get("/webhook", response_class=PlainTextResponse)
async def webhook_check() -> str:
    return "OK"


@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, bool]:
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


def build_webhook_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    if base_url.endswith("/webhook"):
        return base_url
    return f"{base_url}/webhook"


@app.on_event("startup")
async def on_startup() -> None:
    webhook_url = build_webhook_url(settings.webhook_url)
    await bot.set_webhook(webhook_url, drop_pending_updates=False)
    await bot.set_my_commands(BOT_COMMANDS)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logging.info("Telegram webhook is set: %s", webhook_url)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await bot.session.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bot:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False,
    )

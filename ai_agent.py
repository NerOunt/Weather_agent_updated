import json
import os
import re
from typing import Any

try:
    from groq import AsyncGroq
except ImportError:  # pragma: no cover - local env may not have optional package yet
    AsyncGroq = None


SYSTEM_PROMPT = """Ты — модуль понимания запросов Telegram-бота «Погодный бот».
Твоя задача — понять запрос пользователя о погоде.
Не выдумывай температуру, ветер, осадки или прогноз.
Если нужна погода, верни intent и city.
Если город не указан, используй default_city.
Если запрос не про погоду, верни intent=unknown.
Отвечай строго JSON без Markdown.

Возможные intent:
- current_weather
- today_forecast
- clothing_advice
- umbrella_advice
- help
- unknown

Примеры:
Пользователь: "Какая погода в Краснодаре?"
Ответ: {"intent":"current_weather","city":"Краснодар","needs_weather":true}

Пользователь: "Что надеть сегодня в Москве?"
Ответ: {"intent":"clothing_advice","city":"Москва","needs_weather":true}

Пользователь: "Будет ли дождь сегодня в Сочи?"
Ответ: {"intent":"umbrella_advice","city":"Сочи","needs_weather":true}

Пользователь: "Покажи прогноз на сегодня в Казани"
Ответ: {"intent":"today_forecast","city":"Казань","needs_weather":true}

Пользователь: "Помощь"
Ответ: {"intent":"help","city":null,"needs_weather":false}

Пользователь: "Расскажи анекдот"
Ответ: {"intent":"unknown","city":null,"needs_weather":false}"""

ALLOWED_INTENTS = {
    "current_weather",
    "today_forecast",
    "clothing_advice",
    "umbrella_advice",
    "help",
    "unknown",
}


def _fallback_result(error: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "intent": "unknown",
        "city": None,
        "needs_weather": False,
    }
    if error:
        result["error"] = error
    return result


def _parse_json(content: str) -> dict[str, Any]:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def handle_natural_language_query(text: str, default_city: str) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    if not api_key or AsyncGroq is None:
        return _fallback_result("groq_unavailable")

    client = AsyncGroq(api_key=api_key)
    user_prompt = (
        f"default_city: {default_city}\n"
        f"Запрос пользователя: {text}\n"
        "Верни только JSON."
    )

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
        except Exception:
            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
            )
        content = completion.choices[0].message.content or "{}"
        data = _parse_json(content)
    except Exception:
        return _fallback_result("groq_error")

    intent = data.get("intent")
    if intent not in ALLOWED_INTENTS:
        intent = "unknown"

    city = data.get("city")
    if isinstance(city, str):
        city = city.strip() or None
    else:
        city = None

    needs_weather = bool(data.get("needs_weather"))
    if intent in {"current_weather", "today_forecast", "clothing_advice", "umbrella_advice"}:
        needs_weather = True
        city = city or default_city

    if intent in {"help", "unknown"}:
        needs_weather = False

    return {
        "intent": intent,
        "city": city,
        "needs_weather": needs_weather,
    }

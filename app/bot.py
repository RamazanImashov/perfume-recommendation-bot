
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app.config import load_config
from app.keyboards import (
    circumstance_keyboard,
    effect_keyboard,
    event_keyboard,
    location_keyboard,
    main_keyboard,
    remove_keyboard,
    season_keyboard,
    time_keyboard,
)
from app.services.layering import analyze_layering
from app.services.recommender import (
    CIRCUMSTANCE_MAP,
    EFFECT_MAP,
    EVENT_MAP,
    SEASON_MAP,
    TIME_MAP,
    adjust_sprays,
    recommend,
)
from app.services.weather import get_coordinates, get_weather
from app.states import LayeringForm, PerfumeForm


router = Router()
config = load_config()


def is_owner(message: Message) -> bool:
    if config.owner_id is None:
        return True
    return bool(message.from_user and message.from_user.id == config.owner_id)


async def deny_if_not_owner(message: Message) -> bool:
    if not is_owner(message):
        await message.answer("Бот закрыт для личного использования.")
        return True
    return False


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    await state.clear()
    await message.answer(
        "Я подберу топ-3 аромата под погоду, место, время суток, сезон, мероприятие и твой образ. Еще умею проверять наслаивание двух ароматов.",
        reply_markup=main_keyboard(),
    )


@router.message(Command("cancel"))
@router.message(F.text == "Отмена")
async def cancel(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    await state.clear()
    await message.answer("Ок, отменил.", reply_markup=main_keyboard())


@router.message(F.text == "Подобрать аромат")
async def choose_location(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    await state.set_state(PerfumeForm.location)
    await message.answer(
        "Отправь геолокацию или напиши город. Например: Santa Clara, Bishkek, Almaty.",
        reply_markup=location_keyboard(),
    )


@router.message(F.text == "Наслаивание")
async def start_layering(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    await state.clear()
    await state.set_state(LayeringForm.first)
    await message.answer(
        "Напиши первый аромат. Например: Oud Wood.",
        reply_markup=remove_keyboard,
    )


@router.message(LayeringForm.first)
async def get_layering_first(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    first = (message.text or "").strip()
    if len(first) < 2:
        await message.answer("Напиши название первого аромата.")
        return

    await state.update_data(layering_first=first)
    await state.set_state(LayeringForm.second)
    await message.answer("Теперь напиши второй аромат. Например: Lost Cherry.")


@router.message(LayeringForm.second)
async def get_layering_second(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    second = (message.text or "").strip()
    data = await state.get_data()
    first = data.get("layering_first", "")

    result = analyze_layering(first, second)
    await state.clear()
    await message.answer(format_layering_result(result), reply_markup=main_keyboard())


@router.message(PerfumeForm.location, F.location)
async def location_from_geo(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    latitude = message.location.latitude
    longitude = message.location.longitude

    try:
        weather = await get_weather(latitude, longitude)
    except Exception:
        await message.answer("Не смог получить погоду. Попробуй написать город вручную.")
        return

    await state.update_data(weather=weather, place="твоя геолокация")
    await state.set_state(PerfumeForm.event)
    await message.answer("Куда идешь?", reply_markup=event_keyboard())


@router.message(PerfumeForm.location)
async def location_from_text(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    if message.text == "Ввести город вручную":
        await message.answer("Напиши город текстом. Например: Santa Clara.")
        return

    city = (message.text or "").strip()
    if len(city) < 2:
        await message.answer("Напиши город нормально или отправь геолокацию.")
        return

    try:
        coordinates = await get_coordinates(city)
        if not coordinates:
            await message.answer("Не нашел город. Попробуй написать на английском или отправь геолокацию.")
            return
        weather = await get_weather(coordinates["latitude"], coordinates["longitude"])
    except Exception:
        await message.answer("Не смог получить погоду. Попробуй еще раз или отправь геолокацию.")
        return

    place = f"{coordinates['name']}, {coordinates.get('country', '')}".strip().strip(",")
    await state.update_data(weather=weather, place=place)
    await state.set_state(PerfumeForm.event)
    await message.answer("Куда идешь?", reply_markup=event_keyboard())


@router.message(PerfumeForm.event)
async def get_event(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    event = EVENT_MAP.get(message.text or "")
    if not event:
        await message.answer("Выбери вариант из кнопок.", reply_markup=event_keyboard())
        return

    await state.update_data(event=event, event_label=message.text)
    await state.set_state(PerfumeForm.outfit)
    await message.answer(
        "Опиши, что ты одел. Пример: черные широкие джинсы, белые кроссовки, темно-зеленое поло, кожаная куртка.",
        reply_markup=remove_keyboard,
    )


@router.message(PerfumeForm.outfit)
async def get_outfit(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    outfit_text = (message.text or "").strip()
    if len(outfit_text) < 5:
        await message.answer("Опиши образ чуть подробнее: цвет верха, низ, обувь, стиль.")
        return

    await state.update_data(outfit_text=outfit_text)
    await state.set_state(PerfumeForm.circumstance)
    await message.answer("Где в основном будешь?", reply_markup=circumstance_keyboard())


@router.message(PerfumeForm.circumstance)
async def get_circumstance(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    circumstance = CIRCUMSTANCE_MAP.get(message.text or "")
    if not circumstance:
        await message.answer("Выбери вариант из кнопок.", reply_markup=circumstance_keyboard())
        return

    await state.update_data(circumstance=circumstance, circumstance_label=message.text)
    await state.set_state(PerfumeForm.effect)
    await message.answer("Какой эффект нужен?", reply_markup=effect_keyboard())


@router.message(PerfumeForm.effect)
async def get_effect(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    effect = EFFECT_MAP.get(message.text or "")
    if not effect:
        await message.answer("Выбери вариант из кнопок.", reply_markup=effect_keyboard())
        return

    await state.update_data(effect=effect, effect_label=message.text)
    await state.set_state(PerfumeForm.time_of_day)
    await message.answer("Когда будешь носить?", reply_markup=time_keyboard())


@router.message(PerfumeForm.time_of_day)
async def get_time_of_day(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    time_of_day = TIME_MAP.get(message.text or "")
    if not time_of_day:
        await message.answer("Выбери вариант из кнопок.", reply_markup=time_keyboard())
        return

    await state.update_data(time_of_day=time_of_day, time_label=message.text)
    await state.set_state(PerfumeForm.season)
    await message.answer("Какой сезон учитывать?", reply_markup=season_keyboard())


@router.message(PerfumeForm.season)
async def get_season(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    season = SEASON_MAP.get(message.text or "")
    if not season:
        await message.answer("Выбери вариант из кнопок.", reply_markup=season_keyboard())
        return

    await state.update_data(season=season, season_label=message.text)
    data = await state.get_data()

    recommendations = recommend(
        weather=data["weather"],
        event=data["event"],
        outfit_text=data["outfit_text"],
        circumstance=data["circumstance"],
        effect=data["effect"],
        time_of_day=data["time_of_day"],
        season=data["season"],
        limit=3,
    )

    await state.clear()
    await message.answer(format_result(data, recommendations), reply_markup=main_keyboard())


def format_result(data: dict, recommendations: list[dict]) -> str:
    weather = data.get("weather", {})
    temp = weather.get("temperature", "неизвестно")
    rain = weather.get("rain", 0) or weather.get("precipitation", 0)
    humidity = weather.get("humidity", "неизвестно")
    wind = weather.get("wind_speed", "неизвестно")

    lines = [
        "Топ-3 аромата под ситуацию:",
        "",
        f"Место: {data.get('place', 'не указано')}",
        f"Погода: {temp}°C, дождь: {rain}, влажность: {humidity}%, ветер: {wind} км/ч",
        f"Мероприятие: {data.get('event_label')}",
        f"Образ: {data.get('outfit_text')}",
        f"Обстоятельства: {data.get('circumstance_label')}",
        f"Эффект: {data.get('effect_label')}",
        f"Время: {data.get('time_label')}",
        f"Сезон: {data.get('season_label')}",
        "",
    ]

    for index, item in enumerate(recommendations, start=1):
        perfume = item["perfume"]
        sprays = adjust_sprays(perfume.get("sprays", "2–3"), data.get("circumstance", ""), weather)

        name = perfume.get("name", "Без названия")
        brand = perfume.get("brand", "")
        description = perfume.get("description") or perfume.get("summary") or "Описание не указано."
        best_for = perfume.get("best_for", "Подходит под текущий сценарий.")
        minus = perfume.get("minus", "")

        lines.extend([
            f"{index}. {name} — {brand}",
            f"Баллы: {item.get('score', 0)}",
            f"Тип: {description}",
            f"Лучше всего: {best_for}",
            f"Сколько: {sprays}",
            f"Куда: {perfume.get('apply', 'на шею и грудь')}",
            "Почему:",
        ])

        for reason in item.get("reasons", []):
            lines.append(f"— {reason}")

        if item.get("warnings"):
            lines.append("Осторожно:")
            for warning in item.get("warnings", []):
                lines.append(f"— {warning}")

        if minus:
            lines.append(f"Минус: {minus}")

        lines.append("")

    return "\n".join(lines).strip()


def format_layering_result(result: dict) -> str:
    if not result.get("ok"):
        return result.get("message", "Не получилось проверить сочетание.")

    first = result["first"]
    second = result["second"]

    lines = [
        "Наслаивание:",
        f"{first.get('name')} — {first.get('brand')}",
        f"+ {second.get('name')} — {second.get('brand')}",
        "",
        f"Вердикт: {result.get('verdict')}",
        f"Оценка: {result.get('score')}/100",
        "",
        "Как наносить:",
        result.get("order", "Начни с 1+1 пшик и протестируй."),
        "",
        "Почему:",
    ]

    for reason in result.get("reasons", []):
        lines.append(f"— {reason}")

    if result.get("warnings"):
        lines.append("")
        lines.append("Осторожно:")
        for warning in result.get("warnings", []):
            lines.append(f"— {warning}")

    lines.append("")
    lines.append("Правило: не смешивай сразу много. Сначала тест 1+1 пшик и 20–30 минут подождать раскрытие.")
    return "\n".join(lines)


bot = Bot(token=config.bot_token)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


async def start_polling():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


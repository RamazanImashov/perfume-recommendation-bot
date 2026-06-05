import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app.config import load_config
from app.data.perfumes import PERFUMES
from app.keyboards import (
    circumstance_keyboard,
    effect_keyboard,
    event_keyboard,
    location_keyboard,
    main_keyboard,
    recommendation_mode_keyboard,
    remove_keyboard,
    season_keyboard,
    time_keyboard,
)
from app.services.layering import analyze_pair_by_names, recommend_layering
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
from app.states import ManualLayeringForm, PerfumeForm


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
    await message.answer("Выбери действие.", reply_markup=main_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == "Отмена")
async def cancel(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    await state.clear()
    await message.answer("Отменил.", reply_markup=main_keyboard())


@router.message(F.text == "Все мои парфюмы")
async def show_all_perfumes(message: Message):
    if await deny_if_not_owner(message):
        return

    lines = ["Твои парфюмы:"]
    for perfume in PERFUMES:
        lines.append(f"{perfume.get('id', '-')}. {perfume.get('name')} — {perfume.get('brand')}")

    await message.answer("\n".join(lines), reply_markup=main_keyboard())


@router.message(F.text == "Подобрать аромат")
async def choose_location(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    await state.set_state(PerfumeForm.location)
    await message.answer("Отправь геолокацию или напиши город.", reply_markup=location_keyboard())


@router.message(F.text == "Наслаивание вручную")
async def manual_layering_start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    await state.set_state(ManualLayeringForm.first_perfume)
    await message.answer("Напиши первый аромат. Например: Oud Wood", reply_markup=remove_keyboard)


@router.message(ManualLayeringForm.first_perfume)
async def manual_layering_first(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    first = (message.text or "").strip()
    if len(first) < 2:
        await message.answer("Напиши название первого аромата.")
        return

    await state.update_data(first_perfume=first)
    await state.set_state(ManualLayeringForm.second_perfume)
    await message.answer("Напиши второй аромат. Например: Lost Cherry")


@router.message(ManualLayeringForm.second_perfume)
async def manual_layering_second(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    data = await state.get_data()
    first = data.get("first_perfume", "")
    second = (message.text or "").strip()

    result = analyze_pair_by_names(first, second)
    await state.clear()

    if not result:
        await message.answer(
            "Не нашел один из ароматов. Проверь название или нажми «Все мои парфюмы».",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(format_manual_layering_result(result), reply_markup=main_keyboard())


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
    await message.answer("Опиши образ: цвет верха, низ, обувь, стиль.", reply_markup=remove_keyboard)


@router.message(PerfumeForm.outfit)
async def get_outfit(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    outfit_text = (message.text or "").strip()
    if len(outfit_text) < 5:
        await message.answer("Опиши образ чуть подробнее.")
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
    await state.set_state(PerfumeForm.time)
    await message.answer("Время суток?", reply_markup=time_keyboard())


@router.message(PerfumeForm.time)
async def get_time(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    time_of_day = TIME_MAP.get(message.text or "")
    if not time_of_day:
        await message.answer("Выбери вариант из кнопок.", reply_markup=time_keyboard())
        return

    await state.update_data(time_of_day=time_of_day, time_label=message.text)
    await state.set_state(PerfumeForm.season)
    await message.answer("Сезон?", reply_markup=season_keyboard())


@router.message(PerfumeForm.season)
async def get_season(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    season = SEASON_MAP.get(message.text or "")
    if not season:
        await message.answer("Выбери вариант из кнопок.", reply_markup=season_keyboard())
        return

    await state.update_data(season=season, season_label=message.text)
    await state.set_state(PerfumeForm.mode)
    await message.answer("Что подобрать?", reply_markup=recommendation_mode_keyboard())


@router.message(PerfumeForm.mode)
async def get_mode(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return

    mode = message.text or ""
    if mode not in {"Обычный парфюм", "Наслаивание"}:
        await message.answer("Выбери вариант из кнопок.", reply_markup=recommendation_mode_keyboard())
        return

    data = await state.get_data()
    await state.clear()

    if mode == "Обычный парфюм":
        recommendations = recommend(
            weather=data["weather"],
            event=data["event"],
            outfit_text=data["outfit_text"],
            circumstance=data["circumstance"],
            effect=data["effect"],
            time_of_day=data.get("time_of_day", "auto"),
            season=data.get("season", "auto"),
            limit=3,
        )
        await message.answer(format_perfume_result(data, recommendations), reply_markup=main_keyboard())
        return

    recommendations = recommend_layering(
        weather=data["weather"],
        event=data["event"],
        outfit_text=data["outfit_text"],
        circumstance=data["circumstance"],
        effect=data["effect"],
        time_of_day=data.get("time_of_day", "auto"),
        season=data.get("season", "auto"),
        limit=3,
    )
    await message.answer(format_layering_result(data, recommendations), reply_markup=main_keyboard())


def format_perfume_result(data: dict, recommendations: list[dict]) -> str:
    weather = data.get("weather", {})
    temp = weather.get("temperature", "неизвестно")
    place = data.get("place", "локация")
    circumstance = data.get("circumstance", "")

    lines = [
        f"{place}: {temp}°C",
        "Топ-3:",
        "",
    ]

    for index, item in enumerate(recommendations, start=1):
        perfume = item["perfume"]
        sprays = adjust_sprays(perfume.get("sprays", "2–3"), circumstance, weather)
        reasons = item.get("reasons", [])
        warnings = item.get("warnings", [])

        lines.append(f"{index}. {perfume.get('name')} — {perfume.get('brand')}")
        lines.append(f"Пшики: {sprays}")
        lines.append(f"Куда: {perfume.get('apply', 'шея/грудь')}")
        if reasons:
            lines.append("Почему: " + "; ".join(reasons[:2]) + ".")
        if warnings:
            lines.append("Осторожно: " + "; ".join(warnings[:1]) + ".")
        lines.append("")

    return "\n".join(lines).strip()


def format_layering_result(data: dict, recommendations: list[dict]) -> str:
    weather = data.get("weather", {})
    temp = weather.get("temperature", "неизвестно")
    place = data.get("place", "локация")

    lines = [
        f"{place}: {temp}°C",
        "Топ-3 наслаивания:",
        "",
    ]

    for index, item in enumerate(recommendations, start=1):
        base = item["base"]
        top = item["top"]
        reasons = item.get("reasons", [])
        warnings = item.get("warnings", [])

        lines.append(f"{index}. {base.get('name')} + {top.get('name')}")
        lines.append(f"Как: {item.get('apply')}")
        if reasons:
            lines.append("Почему: " + "; ".join(reasons[:2]) + ".")
        if warnings:
            lines.append("Осторожно: " + "; ".join(warnings[:1]) + ".")
        lines.append("")

    return "\n".join(lines).strip()


def format_manual_layering_result(result: dict) -> str:
    base = result["base"]
    top = result["top"]

    lines = [
        f"{base.get('name')} + {top.get('name')}",
        f"Оценка: {result.get('score')}/100",
        f"Как: {result.get('apply')}",
    ]

    if result.get("reasons"):
        lines.append("Почему: " + "; ".join(result["reasons"][:2]) + ".")

    if result.get("warnings"):
        lines.append("Осторожно: " + "; ".join(result["warnings"][:1]) + ".")

    return "\n".join(lines)


bot = Bot(token=config.bot_token)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


async def start_polling():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_polling())

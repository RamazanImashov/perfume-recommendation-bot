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
    brand_keyboard,
    circumstance_keyboard,
    effect_keyboard,
    event_keyboard,
    location_keyboard,
    main_keyboard,
    perfume_keyboard,
    perfume_list_keyboard,
    recommendation_mode_keyboard,
    recommendation_result_keyboard,
    remove_keyboard,
    season_keyboard,
    time_keyboard,
)
from app.services.layering import (
    analyze_pair,
    get_preset_layering_pairs,
    recommend_layering,
)
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
from app.states import ManualLayeringForm, PerfumeForm, PerfumeListForm, RecommendationBrowseForm


router = Router()
config = load_config()


# ---------- access ----------

def is_owner(message: Message) -> bool:
    if config.owner_id is None:
        return True
    return bool(message.from_user and message.from_user.id == config.owner_id)


async def deny_if_not_owner(message: Message) -> bool:
    if not is_owner(message):
        await message.answer("Бот закрыт для личного использования.")
        return True
    return False


# ---------- common ----------

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    await state.clear()
    await message.answer("Выбери действие.", reply_markup=main_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == "Отмена")
@router.message(F.text == "Главное меню")
async def cancel(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    await state.clear()
    await message.answer("Главное меню.", reply_markup=main_keyboard())


# ---------- perfume catalog ----------

@router.message(F.text == "Все мои парфюмы")
async def perfume_list_menu(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    await state.clear()
    await message.answer("Как показать список?", reply_markup=perfume_list_keyboard())


@router.message(F.text == "Все по брендам")
async def show_all_perfumes(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    await state.clear()
    await _send_perfume_list(message, PERFUMES, "Все парфюмы по брендам")


@router.message(F.text == "Фильтр по бренду")
async def choose_brand_filter(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    brands = sorted({p.get("brand", "Unknown") for p in PERFUMES})
    await state.set_state(PerfumeListForm.brand)
    await message.answer("Выбери бренд.", reply_markup=brand_keyboard(brands))


@router.message(PerfumeListForm.brand)
async def show_by_brand(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    brand = (message.text or "").strip()
    brands = {p.get("brand", "Unknown") for p in PERFUMES}
    if brand not in brands:
        await message.answer("Выбери бренд из кнопок.", reply_markup=brand_keyboard(sorted(brands)))
        return
    await state.clear()
    selected = [p for p in PERFUMES if p.get("brand") == brand]
    await _send_perfume_list(message, selected, f"Бренд: {brand}")


@router.message(F.text.in_({"Мужские", "Женские", "Унисекс"}))
async def show_by_gender(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    await state.clear()
    gender_map = {"Мужские": "men", "Женские": "women", "Унисекс": "unisex"}
    gender = gender_map[message.text]
    selected = [p for p in PERFUMES if p.get("gender") == gender]
    await _send_perfume_list(message, selected, message.text)


async def _send_perfume_list(message: Message, perfumes: list[dict], title: str) -> None:
    text = format_perfume_catalog(perfumes, title)
    chunks = _split_text(text, limit=3800)
    for chunk in chunks[:-1]:
        await message.answer(chunk)
    await message.answer(chunks[-1], reply_markup=main_keyboard())


def format_perfume_catalog(perfumes: list[dict], title: str) -> str:
    if not perfumes:
        return f"{title}: ничего не найдено. Female-only ароматов пока нет; есть unisex."

    sorted_perfumes = sorted(perfumes, key=lambda p: (p.get("brand", ""), p.get("name", "")))
    lines = [f"{title}: {len(sorted_perfumes)}", ""]
    current_brand = None
    for perfume in sorted_perfumes:
        brand = perfume.get("brand", "Unknown")
        if brand != current_brand:
            current_brand = brand
            lines.append(f"{brand}")
        gender_label = {"men": "мужской", "women": "женский", "unisex": "унисекс"}.get(perfume.get("gender", ""), perfume.get("gender", ""))
        lines.append(f"— {perfume.get('name')} ({gender_label})")
    return "\n".join(lines)


# ---------- recommendation flow ----------

@router.message(F.text == "Подобрать аромат")
async def choose_location(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    await state.set_state(PerfumeForm.location)
    await message.answer("Отправь геолокацию или напиши город.", reply_markup=location_keyboard())


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
    context = _make_context(data, mode)
    text = _format_recommendations_from_context(context, start=0, limit=3)
    await state.set_state(RecommendationBrowseForm.active)
    await state.update_data(recommendation_context=context, recommendation_offset=3)
    await message.answer(text, reply_markup=recommendation_result_keyboard())


@router.message(F.text == "Другие варианты")
async def more_recommendations(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    data = await state.get_data()
    context = data.get("recommendation_context")
    offset = int(data.get("recommendation_offset", 0))
    if not context:
        await message.answer("Сначала сделай подбор.", reply_markup=main_keyboard())
        return
    text = _format_recommendations_from_context(context, start=offset, limit=3)
    await state.set_state(RecommendationBrowseForm.active)
    await state.update_data(recommendation_offset=offset + 3)
    await message.answer(text, reply_markup=recommendation_result_keyboard())


def _make_context(data: dict, mode: str) -> dict:
    return {
        "mode": mode,
        "weather": data["weather"],
        "place": data.get("place", "локация"),
        "event": data["event"],
        "outfit_text": data["outfit_text"],
        "circumstance": data["circumstance"],
        "effect": data["effect"],
        "time_of_day": data.get("time_of_day", "auto"),
        "season": data.get("season", "auto"),
    }


def _format_recommendations_from_context(context: dict, start: int, limit: int) -> str:
    internal_limit = start + limit
    if context["mode"] == "Обычный парфюм":
        recs = recommend(
            weather=context["weather"],
            event=context["event"],
            outfit_text=context["outfit_text"],
            circumstance=context["circumstance"],
            effect=context["effect"],
            time_of_day=context["time_of_day"],
            season=context["season"],
            limit=internal_limit,
        )[start: start + limit]
        return format_perfume_result(context, recs, start_index=start + 1)

    recs = recommend_layering(
        weather=context["weather"],
        event=context["event"],
        outfit_text=context["outfit_text"],
        circumstance=context["circumstance"],
        effect=context["effect"],
        time_of_day=context["time_of_day"],
        season=context["season"],
        limit=internal_limit,
    )[start: start + limit]
    return format_layering_result(context, recs, start_index=start + 1)


def format_perfume_result(data: dict, recommendations: list[dict], start_index: int = 1) -> str:
    weather = data.get("weather", {})
    temp = weather.get("temperature", "неизвестно")
    place = data.get("place", "локация")
    circumstance = data.get("circumstance", "")
    title = "Топ вариантов:" if start_index > 1 else "Топ-3:"

    lines = [f"{place}: {temp}°C", title, ""]
    if not recommendations:
        return "Больше вариантов не нашел."

    for index, item in enumerate(recommendations, start=start_index):
        perfume = item["perfume"]
        sprays = adjust_sprays(perfume.get("sprays", "2–3"), circumstance, weather)
        reasons = item.get("reasons", [])
        warnings = item.get("warnings", [])
        lines.append(f"{index}. {perfume.get('name')} — {perfume.get('brand')}")
        lines.append(f"Пшики: {sprays}")
        if reasons:
            lines.append("Почему: " + "; ".join(reasons[:2]) + ".")
        if warnings:
            lines.append("Риск: " + "; ".join(warnings[:1]) + ".")
        lines.append("")
    return "\n".join(lines).strip()


def format_layering_result(data: dict, recommendations: list[dict], start_index: int = 1) -> str:
    weather = data.get("weather", {})
    temp = weather.get("temperature", "неизвестно")
    place = data.get("place", "локация")
    title = "Другие пары:" if start_index > 1 else "Топ-3 наслаивания:"

    lines = [f"{place}: {temp}°C", title, ""]
    if not recommendations:
        return "Больше пар не нашел."

    for index, item in enumerate(recommendations, start=start_index):
        base = item["base"]
        top = item["top"]
        reasons = item.get("reasons", [])
        warnings = item.get("warnings", [])
        lines.append(f"{index}. {base.get('name')} + {top.get('name')}")
        lines.append(f"Как: {item.get('apply')}")
        if reasons:
            lines.append("Почему: " + "; ".join(reasons[:2]) + ".")
        if warnings:
            lines.append("Риск: " + "; ".join(warnings[:1]) + ".")
        lines.append("")
    return "\n".join(lines).strip()


# ---------- manual layering ----------

@router.message(F.text == "Наслаивание вручную")
async def manual_layering_start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    brands = sorted({p.get("brand", "Unknown") for p in PERFUMES})
    await state.set_state(ManualLayeringForm.first_brand)
    await message.answer("Выбери бренд первого аромата.", reply_markup=brand_keyboard(brands))


@router.message(ManualLayeringForm.first_brand)
async def manual_first_brand(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    brand = (message.text or "").strip()
    perfumes = _perfumes_by_brand(brand)
    if not perfumes:
        await message.answer("Выбери бренд из кнопок.", reply_markup=brand_keyboard(sorted({p.get("brand", "Unknown") for p in PERFUMES})))
        return
    await state.update_data(first_brand=brand)
    await state.set_state(ManualLayeringForm.first_perfume)
    await message.answer("Выбери первый аромат.", reply_markup=perfume_keyboard(perfumes))


@router.message(ManualLayeringForm.first_perfume)
async def manual_first_perfume(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    perfume = _perfume_from_label(message.text or "")
    if not perfume:
        await message.answer("Выбери аромат из кнопок.")
        return
    brands = sorted({p.get("brand", "Unknown") for p in PERFUMES})
    await state.update_data(first_perfume_id=perfume.get("id"))
    await state.set_state(ManualLayeringForm.second_brand)
    await message.answer("Выбери бренд второго аромата.", reply_markup=brand_keyboard(brands))


@router.message(ManualLayeringForm.second_brand)
async def manual_second_brand(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    brand = (message.text or "").strip()
    perfumes = _perfumes_by_brand(brand)
    if not perfumes:
        await message.answer("Выбери бренд из кнопок.", reply_markup=brand_keyboard(sorted({p.get("brand", "Unknown") for p in PERFUMES})))
        return
    await state.update_data(second_brand=brand)
    await state.set_state(ManualLayeringForm.second_perfume)
    await message.answer("Выбери второй аромат.", reply_markup=perfume_keyboard(perfumes))


@router.message(ManualLayeringForm.second_perfume)
async def manual_second_perfume(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    second = _perfume_from_label(message.text or "")
    data = await state.get_data()
    first = _perfume_by_id(data.get("first_perfume_id"))
    await state.clear()
    if not first or not second:
        await message.answer("Не смог найти один из ароматов.", reply_markup=main_keyboard())
        return
    if first.get("id") == second.get("id"):
        await message.answer("Выбери два разных аромата.", reply_markup=main_keyboard())
        return
    result = analyze_pair(first, second)
    await message.answer(format_manual_layering_result(result), reply_markup=main_keyboard())


@router.message(F.text == "Готовые пары наслаивания")
async def preset_layering(message: Message, state: FSMContext):
    if await deny_if_not_owner(message):
        return
    await state.clear()
    pairs = get_preset_layering_pairs()
    await message.answer(format_preset_layering_pairs(pairs), reply_markup=main_keyboard())


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
        lines.append("Риск: " + "; ".join(result["warnings"][:1]) + ".")
    return "\n".join(lines)


def format_preset_layering_pairs(pairs: list[dict]) -> str:
    lines = ["Готовые пары наслаивания:", ""]
    for index, item in enumerate(pairs, start=1):
        base = item["base"]
        top = item["top"]
        label = item.get("label")
        best_for = item.get("best_for")
        lines.append(f"{index}. {base.get('name')} + {top.get('name')}")
        if label:
            lines.append(f"Идея: {label}")
        lines.append(f"Как: {item.get('apply')}")
        if best_for:
            lines.append(f"Когда: {best_for}")
        lines.append("")
    return "\n".join(lines).strip()


# ---------- helpers ----------

def _split_text(text: str, limit: int = 3800) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > limit:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks or [""]


def _perfumes_by_brand(brand: str) -> list[dict]:
    return sorted([p for p in PERFUMES if p.get("brand") == brand], key=lambda p: p.get("name", ""))


def _perfume_by_id(perfume_id: int | str | None) -> dict | None:
    for perfume in PERFUMES:
        if str(perfume.get("id")) == str(perfume_id):
            return perfume
    return None


def _perfume_from_label(label: str) -> dict | None:
    clean = label.strip()
    for perfume in PERFUMES:
        if clean == f"{perfume.get('name')} — {perfume.get('brand')}":
            return perfume
    for perfume in PERFUMES:
        if clean.lower() == str(perfume.get("name", "")).lower():
            return perfume
    return None


bot = Bot(token=config.bot_token)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


async def start_polling():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_polling())

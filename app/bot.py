from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import load_config
from app.data.perfumes import PERFUMES
from app.keyboards import (
    advanced_keyboard,
    brand_keyboard,
    circumstance_keyboard,
    effect_keyboard,
    event_keyboard,
    exposure_keyboard,
    feedback_rating_keyboard,
    feedback_tags_keyboard,
    location_keyboard,
    main_keyboard,
    perfume_keyboard,
    perfume_list_keyboard,
    preset_layering_keyboard,
    recommendation_mode_keyboard,
    recommendation_result_keyboard,
    remove_keyboard,
    season_keyboard,
    target_time_keyboard,
    time_keyboard,
)
from app.models.perfume import EVENT_SCORE_KEYS, build_perfume_profile
from app.models.recommendation import FeedbackRecord
from app.models.situation import Situation
from app.services.ai_client import AIClient
from app.services.explanations import comparison_reason, explanation_lines, risk_line
from app.services.history import OwnerHistory
from app.services.layering import (
    analyze_pair_situation,
    get_preset_layering_pairs,
    recommend_layering_situation,
)
from app.services.personalization import build_personal_snapshot
from app.services.recommender import (
    CIRCUMSTANCE_MAP,
    EFFECT_MAP,
    EVENT_MAP,
    SEASON_MAP,
    TIME_MAP,
    apply_ai_adjustments,
    diversify_results,
    find_perfume,
    recommend_situation,
)
from app.services.scoring import score_perfume as score_profile
from app.services.situation_parser import build_situation
from app.services.weather import get_coordinates, get_weather
from app.states import PerfumeForm, PerfumeListForm, PresetLayeringBrowseForm, RecommendationBrowseForm, ReverseForm, WhyNotForm
from app.storage import create_fsm_storage, create_personal_storage

logger = logging.getLogger(__name__)
router = Router()
config = load_config()
personal_storage = create_personal_storage(config)
history = OwnerHistory(personal_storage)
ai_client = AIClient(config)


def is_owner(message: Message) -> bool:
    if config.owner_id is None:
        return not config.is_production
    return bool(message.from_user and message.from_user.id == config.owner_id)


async def deny_if_not_owner(message: Message) -> bool:
    if not is_owner(message):
        await message.answer("Бот закрыт для личного использования.")
        return True
    return False


class OwnerOnlyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and not is_owner(event):
            await event.answer("Бот закрыт для личного использования.")
            return None
        return await handler(event, data)


router.message.outer_middleware(OwnerOnlyMiddleware())


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.clear()
    await message.answer("Выбери действие.", reply_markup=main_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == "Отмена")
@router.message(F.text == "Главное меню")
async def cancel(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.clear()
    await message.answer("Главное меню.", reply_markup=main_keyboard())


@router.message(Command("variety"))
async def set_variety(message: Message):
    if await deny_if_not_owner(message): return
    await history.set_preference("repeat_mode", "diversity")
    await message.answer("Режим: Разнообразие.", reply_markup=main_keyboard())


@router.message(Command("favorites"))
async def set_favorites(message: Message):
    if await deny_if_not_owner(message): return
    await history.set_preference("repeat_mode", "favorites")
    await message.answer("Режим: Повторять любимые.", reply_markup=main_keyboard())


# ---------- catalog ----------

@router.message(F.text == "Все мои парфюмы")
async def perfume_list_menu(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.clear()
    await message.answer("Как показать список?", reply_markup=perfume_list_keyboard())


@router.message(F.text == "Все по брендам")
async def show_all_perfumes(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.clear()
    await _send_perfume_list(message, PERFUMES, "Все парфюмы по брендам")


@router.message(F.text == "Фильтр по бренду")
async def choose_brand_filter(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    brands = _brands()
    await state.set_state(PerfumeListForm.brand)
    await message.answer("Выбери бренд.", reply_markup=brand_keyboard(brands))


@router.message(PerfumeListForm.brand)
async def show_by_brand(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    brand = (message.text or "").strip()
    perfumes = _perfumes_by_brand(brand)
    if not perfumes:
        await message.answer("Выбери бренд из кнопок.", reply_markup=brand_keyboard(_brands()))
        return
    await state.clear()
    await _send_perfume_list(message, perfumes, f"Бренд: {brand}")


@router.message(F.text.in_({"Мужские", "Женские", "Унисекс"}))
async def show_by_gender(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.clear()
    gender_map = {"Мужские": "men", "Женские": "women", "Унисекс": "unisex"}
    selected = [p for p in PERFUMES if p.get("gender") == gender_map[message.text]]
    await _send_perfume_list(message, selected, message.text)


async def _send_perfume_list(message: Message, perfumes: list[dict], title: str) -> None:
    for chunk in _split_text(format_perfume_catalog(perfumes, title), 3800)[:-1]:
        await message.answer(chunk)
    chunks = _split_text(format_perfume_catalog(perfumes, title), 3800)
    await message.answer(chunks[-1], reply_markup=main_keyboard())


def format_perfume_catalog(perfumes: list[dict], title: str) -> str:
    if not perfumes: return f"{title}: ничего не найдено."
    sorted_perfumes = sorted(perfumes, key=lambda p: (str(p.get("brand", "")).lower(), str(p.get("name", "")).lower()))
    lines = [f"{title}: {len(sorted_perfumes)}", ""]
    current_brand = None
    for perfume in sorted_perfumes:
        brand = perfume.get("brand", "Unknown")
        if brand != current_brand:
            current_brand = brand
            lines.append(str(brand))
        gender = {"men": "мужской", "women": "женский", "unisex": "унисекс"}.get(perfume.get("gender"), str(perfume.get("gender", "")))
        lines.append(f"— {perfume.get('name')} ({gender})")
    return "\n".join(lines)


# ---------- recommendation flow ----------

@router.message(F.text == "Подобрать аромат")
async def choose_location(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.clear()
    previous = await history.get_last_location() if history.enabled else None
    await state.set_state(PerfumeForm.location)
    await message.answer("Отправь геолокацию или напиши город.", reply_markup=location_keyboard(bool(previous)))


async def _save_location_to_state(state: FSMContext, *, latitude: float, longitude: float, place: str, timezone_name: str | None) -> None:
    payload = {"latitude": latitude, "longitude": longitude, "place": place, "timezone": timezone_name}
    await state.update_data(**payload)
    if history.enabled:
        await history.save_last_location(payload)


@router.message(PerfumeForm.location, F.location)
async def location_from_geo(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    lat, lon = message.location.latitude, message.location.longitude
    try:
        weather = await get_weather(lat, lon)
    except Exception:
        await message.answer("Не смог получить погоду. Попробуй город вручную.")
        return
    await _save_location_to_state(state, latitude=lat, longitude=lon, place="твоя геолокация", timezone_name=weather.get("timezone"))
    await state.set_state(PerfumeForm.event)
    await message.answer("Куда идешь?", reply_markup=event_keyboard())


@router.message(PerfumeForm.location)
async def location_from_text(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    text = (message.text or "").strip()
    if text == "Ввести город вручную":
        await message.answer("Напиши город текстом.")
        return
    if text == "Использовать прошлую локацию":
        previous = await history.get_last_location()
        if not previous:
            await message.answer("Прошлой локации нет.", reply_markup=location_keyboard(False))
            return
        await _save_location_to_state(state, **previous)
        await state.set_state(PerfumeForm.event)
        await message.answer("Куда идешь?", reply_markup=event_keyboard())
        return
    if len(text) < 2:
        await message.answer("Напиши город нормально или отправь геолокацию.")
        return
    try:
        coordinates = await get_coordinates(text)
        if not coordinates:
            await message.answer("Не нашел город. Попробуй английское название.")
            return
    except Exception:
        await message.answer("Не смог найти город. Попробуй ещё раз.")
        return
    place = f"{coordinates['name']}, {coordinates.get('country', '')}".strip().strip(",")
    await _save_location_to_state(state, latitude=coordinates["latitude"], longitude=coordinates["longitude"], place=place, timezone_name=coordinates.get("timezone"))
    await state.set_state(PerfumeForm.event)
    await message.answer("Куда идешь?", reply_markup=event_keyboard())


@router.message(PerfumeForm.event)
async def get_event(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    event = EVENT_MAP.get(message.text or "")
    if not event:
        await message.answer("Выбери вариант из кнопок.", reply_markup=event_keyboard()); return
    await state.update_data(event=event, event_label=message.text)
    await state.set_state(PerfumeForm.outfit)
    await message.answer("Опиши образ: верх, низ, обувь, цвета и стиль.", reply_markup=remove_keyboard)


@router.message(PerfumeForm.outfit)
async def get_outfit(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Опиши образ чуть подробнее."); return
    await state.update_data(outfit_text=text)
    await state.set_state(PerfumeForm.circumstance)
    await message.answer("Где в основном будешь?", reply_markup=circumstance_keyboard())


@router.message(PerfumeForm.circumstance)
async def get_circumstance(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    value = CIRCUMSTANCE_MAP.get(message.text or "")
    if not value:
        await message.answer("Выбери вариант из кнопок.", reply_markup=circumstance_keyboard()); return
    await state.update_data(circumstance=value)
    await state.set_state(PerfumeForm.effect)
    await message.answer("Какой эффект нужен?", reply_markup=effect_keyboard())


@router.message(PerfumeForm.effect)
async def get_effect(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    value = EFFECT_MAP.get(message.text or "")
    if not value:
        await message.answer("Выбери вариант из кнопок.", reply_markup=effect_keyboard()); return
    await state.update_data(effect=value)
    await state.set_state(PerfumeForm.target_time)
    await message.answer("Когда будешь носить аромат?", reply_markup=target_time_keyboard())


def _local_now(timezone_name: str | None) -> datetime:
    try:
        return datetime.now(ZoneInfo(timezone_name)) if timezone_name else datetime.now().astimezone()
    except Exception:
        return datetime.now().astimezone()


def _resolve_quick_target(label: str, timezone_name: str | None) -> datetime | None:
    now = _local_now(timezone_name)
    if label == "Сейчас": return now
    if label == "Через 1 час": return now + timedelta(hours=1)
    if label == "Через 2 часа": return now + timedelta(hours=2)
    if label == "Вечером":
        target = now.replace(hour=19, minute=0, second=0, microsecond=0)
        return target if target > now else target + timedelta(days=1)
    return None


async def _after_target_time(message: Message, state: FSMContext, target: datetime) -> None:
    data = await state.get_data()
    try:
        weather = await get_weather(data["latitude"], data["longitude"], target, data.get("timezone"))
    except Exception:
        weather = {"temperature": 20, "humidity": None, "rain": 0, "precipitation": 0, "cloud_cover": None, "wind_speed": None, "is_day": True, "source": "fallback"}
    await state.update_data(target_datetime=target.isoformat(), weather=weather, time_of_day="auto", season="auto", outdoor_exposure=None)
    await state.set_state(PerfumeForm.advanced)
    await message.answer("Дополнительные настройки?", reply_markup=advanced_keyboard())


@router.message(PerfumeForm.target_time)
async def get_target_time(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    if message.text == "Указать время":
        await state.set_state(PerfumeForm.manual_target_time)
        await message.answer("Напиши время HH:MM, например 20:30.", reply_markup=remove_keyboard)
        return
    data = await state.get_data()
    target = _resolve_quick_target(message.text or "", data.get("timezone"))
    if target is None:
        await message.answer("Выбери вариант из кнопок.", reply_markup=target_time_keyboard()); return
    await _after_target_time(message, state, target)


@router.message(PerfumeForm.manual_target_time)
async def manual_target_time(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    text = (message.text or "").strip()
    try:
        hour, minute = [int(x) for x in text.split(":", 1)]
        if not (0 <= hour <= 23 and 0 <= minute <= 59): raise ValueError
    except Exception:
        await message.answer("Формат HH:MM, например 20:30."); return
    data = await state.get_data()
    now = _local_now(data.get("timezone"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target < now - timedelta(minutes=10): target += timedelta(days=1)
    await _after_target_time(message, state, target)


@router.message(PerfumeForm.advanced)
async def get_advanced(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    if message.text == "Авто — продолжить":
        data = await state.get_data()
        if data.get("reverse_perfume_id") is not None:
            await _finish_reverse_with_situation(message, state, _situation_from_data(data))
            return
        await state.set_state(PerfumeForm.mode)
        await message.answer("Что подобрать?", reply_markup=recommendation_mode_keyboard()); return
    if message.text == "Настроить вручную":
        await state.set_state(PerfumeForm.time)
        await message.answer("Время суток?", reply_markup=time_keyboard()); return
    await message.answer("Выбери вариант из кнопок.", reply_markup=advanced_keyboard())


@router.message(PerfumeForm.time)
async def get_time(message: Message, state: FSMContext):
    value = TIME_MAP.get(message.text or "")
    if not value: await message.answer("Выбери вариант.", reply_markup=time_keyboard()); return
    await state.update_data(time_of_day=value)
    await state.set_state(PerfumeForm.season)
    await message.answer("Сезон?", reply_markup=season_keyboard())


@router.message(PerfumeForm.season)
async def get_season(message: Message, state: FSMContext):
    value = SEASON_MAP.get(message.text or "")
    if not value: await message.answer("Выбери вариант.", reply_markup=season_keyboard()); return
    await state.update_data(season=value)
    await state.set_state(PerfumeForm.exposure)
    await message.answer("Сколько времени на улице?", reply_markup=exposure_keyboard())


@router.message(PerfumeForm.exposure)
async def get_exposure(message: Message, state: FSMContext):
    mapping = {"Авто": None, "Мало улицы": "low", "Средне": "medium", "Много улицы": "high"}
    if message.text not in mapping: await message.answer("Выбери вариант.", reply_markup=exposure_keyboard()); return
    await state.update_data(outdoor_exposure=mapping[message.text])
    data = await state.get_data()
    if data.get("reverse_perfume_id") is not None:
        await _finish_reverse_with_situation(message, state, _situation_from_data(data))
        return
    await state.set_state(PerfumeForm.mode)
    await message.answer("Что подобрать?", reply_markup=recommendation_mode_keyboard())


async def _personal_snapshot() -> dict | None:
    if not history.enabled: return None
    prefs = await history.get_preferences()
    return build_personal_snapshot(await history.get_history(), prefs.get("repeat_mode", "diversity"))


def _situation_from_data(data: dict) -> Situation:
    target_raw = data.get("target_datetime")
    target = datetime.fromisoformat(target_raw) if isinstance(target_raw, str) else target_raw
    return build_situation(
        event=data.get("event", "casual"), outfit_text=data.get("outfit_text", "casual"), circumstance=data.get("circumstance", "outdoor"),
        effect=data.get("effect", "any"), weather=data.get("weather", {}), place=data.get("place", ""), target_datetime=target,
        latitude=data.get("latitude"), longitude=data.get("longitude"), timezone=data.get("timezone"), manual_time=data.get("time_of_day", "auto"),
        manual_season=data.get("season", "auto"), outdoor_exposure=data.get("outdoor_exposure"),
    )


async def _ordinary_results(situation: Situation, limit: int, snapshot: dict | None):
    raw = recommend_situation(situation, limit=max(6, limit), personal_snapshot=snapshot, diversity=False)
    if ai_client.enabled:
        candidates = [{"name": r.name, "score": r.score, "facts": {"brand": r.brand}, "breakdown": r.breakdown.model_dump(), "warnings": r.hard_warnings} for r in raw[:6]]
        adjustments = await ai_client.rerank(situation, candidates)
        raw = apply_ai_adjustments(raw, adjustments)
    if limit <= 3:
        return diversify_results(raw, limit)
    return raw[:limit]


@router.message(PerfumeForm.mode)
async def get_mode(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    mode = message.text or ""
    if mode not in {"Обычный парфюм", "Наслаивание"}:
        await message.answer("Выбери вариант.", reply_markup=recommendation_mode_keyboard()); return
    data = await state.get_data()
    situation = _situation_from_data(data)
    snapshot = await _personal_snapshot()
    if mode == "Обычный парфюм":
        results = await _ordinary_results(situation, 3, snapshot)
        text = format_perfume_results(situation, results)
        payload = {"mode": mode, "situation": situation.model_dump(mode="json"), "items": [r.model_dump(mode="json") for r in results]}
    else:
        results = recommend_layering_situation(situation, 3, snapshot)
        text = format_layering_results(situation, results)
        payload = {"mode": mode, "situation": situation.model_dump(mode="json"), "items": [r.model_dump(mode="json") for r in results]}
    await state.set_state(RecommendationBrowseForm.active)
    await state.update_data(recommendation_context=payload, recommendation_offset=3)
    if history.enabled:
        await history.save_last_situation(situation.model_dump(mode="json"))
        await history.save_last_recommendation(payload)
    await message.answer(text, reply_markup=recommendation_result_keyboard())


@router.message(F.text == "Другие варианты")
async def more_recommendations(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    data = await state.get_data()
    context = data.get("recommendation_context") or (await history.get_last_recommendation() if history.enabled else None)
    if not context:
        await message.answer("Сначала сделай подбор.", reply_markup=main_keyboard()); return
    offset = int(data.get("recommendation_offset", len(context.get("items") or [])))
    situation = Situation.model_validate(context["situation"])
    snapshot = await _personal_snapshot()
    if context["mode"] == "Обычный парфюм":
        displayed = {item.get("name") for item in context.get("items", [])}
        all_results = await _ordinary_results(situation, min(len(PERFUMES), offset + 9), snapshot)
        results = [r for r in all_results if r.name not in displayed][:3]
        text = format_perfume_results(situation, results, start_index=offset + 1, title="Другие варианты")
        context.setdefault("items", []).extend(r.model_dump(mode="json") for r in results)
    else:
        displayed = {tuple(sorted((item.get("base_name", ""), item.get("top_name", "")))) for item in context.get("items", [])}
        all_results = recommend_layering_situation(situation, min(465, offset + 12), snapshot)
        results = [r for r in all_results if tuple(sorted((r.base_name, r.top_name))) not in displayed][:3]
        text = format_layering_results(situation, results, start_index=offset + 1, title="Другие пары")
        context.setdefault("items", []).extend(r.model_dump(mode="json") for r in results)
    await state.set_state(RecommendationBrowseForm.active)
    await state.update_data(recommendation_context=context, recommendation_offset=offset + len(results))
    if history.enabled:
        await history.save_last_recommendation(context)
    await message.answer(text, reply_markup=recommendation_result_keyboard())


def format_perfume_results(situation: Situation, results, start_index: int = 1, title: str = "Топ-3") -> str:
    if not results: return "Больше вариантов не нашёл."
    lines = [f"{situation.location or 'Локация'}: {situation.temperature:g}°C · {title}", ""]
    for idx, result in enumerate(results, start=start_index):
        lines.append(f"{idx}. {result.name} — {result.brand}")
        lines.append(f"{result.score:.0f}/100 · Уверенность: {result.confidence_label} · {result.role}")
        reasons = explanation_lines(result, situation, 2)
        if reasons: lines.append("Почему: " + "; ".join(reasons) + ".")
        lines.append(f"Как: {result.spray_count} пш. — " + ", ".join(result.spray_locations))
        risk = risk_line(result)
        if risk != "существенных рисков нет": lines.append("Риск: " + risk + ".")
        lines.append("")
    return "\n".join(lines).strip()


def format_layering_results(situation: Situation, results, start_index: int = 1, title: str = "Топ-3 наслаивания") -> str:
    if not results: return "Больше пар не нашёл."
    lines = [f"{situation.location or 'Локация'}: {situation.temperature:g}°C · {title}", ""]
    for idx, result in enumerate(results, start=start_index):
        lines.append(f"{idx}. {result.base_name} + {result.top_name}")
        lines.append(f"{result.score:.0f}/100 · Уверенность: {result.confidence_label}")
        if result.reasons: lines.append("Почему: " + "; ".join(result.reasons[:2]) + ".")
        lines.append("Как: " + result.spray_plan)
        if result.warnings: lines.append("Риск: " + result.warnings[0] + ".")
        lines.append("")
    return "\n".join(lines).strip()


# ---------- repeat last ----------

@router.message(F.text == "Как в прошлый раз")
async def repeat_last(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    saved = await history.get_last_situation() if history.enabled else None
    if not saved:
        await message.answer("Сохранённого контекста нет. Сделай обычный подбор.", reply_markup=main_keyboard()); return
    situation = Situation.model_validate(saved)
    if situation.latitude is not None and situation.longitude is not None:
        now = _local_now(situation.timezone)
        try:
            weather = await get_weather(situation.latitude, situation.longitude, now, situation.timezone)
            situation = build_situation(event=situation.event, outfit_text=situation.outfit.raw_text, circumstance=situation.circumstance, effect=situation.desired_effect, weather=weather, place=situation.location, target_datetime=now, latitude=situation.latitude, longitude=situation.longitude, timezone=situation.timezone, outdoor_exposure=situation.outdoor_exposure)
        except Exception:
            pass
    results = await _ordinary_results(situation, 3, await _personal_snapshot())
    payload = {"mode": "Обычный парфюм", "situation": situation.model_dump(mode="json"), "items": [r.model_dump(mode="json") for r in results]}
    await state.set_state(RecommendationBrowseForm.active)
    await state.update_data(recommendation_context=payload, recommendation_offset=3)
    await message.answer(format_perfume_results(situation, results), reply_markup=recommendation_result_keyboard())


# ---------- feedback ----------

@router.message(F.text == "Как прошло?")
async def feedback_start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    context = (await state.get_data()).get("recommendation_context") or (await history.get_last_recommendation() if history.enabled else None)
    if not context or not context.get("items"):
        await message.answer("Нет последней рекомендации.", reply_markup=main_keyboard()); return
    await state.update_data(feedback_context=context, feedback_rating=None, feedback_tags=[])
    await message.answer("Как прошло с первым вариантом?", reply_markup=feedback_rating_keyboard())


RATING_MAP = {"Отлично": "excellent", "Нормально": "normal", "Не понравилось": "dislike", "Слишком сильный": "too_strong", "Слишком слабый": "too_weak"}
TAG_MAP = {"Получил комплимент": "compliment", "Самому понравилось": "liked_myself", "Устал от аромата": "fatigued", "Хочу повторить": "repeat"}


@router.message(F.text.in_(set(RATING_MAP)))
async def feedback_rating(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.update_data(feedback_rating=RATING_MAP[message.text], feedback_tags=[])
    await message.answer("Можно добавить 1–2 сигнала или нажать «Готово».", reply_markup=feedback_tags_keyboard())


@router.message(F.text.in_(set(TAG_MAP) | {"Готово"}))
async def feedback_tags(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    data = await state.get_data()
    if not data.get("feedback_rating"):
        return
    tags = list(data.get("feedback_tags") or [])
    if message.text != "Готово":
        tag = TAG_MAP[message.text]
        if tag not in tags: tags.append(tag)
        await state.update_data(feedback_tags=tags)
        if len(tags) < 2:
            await message.answer("Добавь ещё один сигнал или нажми «Готово».", reply_markup=feedback_tags_keyboard()); return
    context = data.get("feedback_context") or {}
    item = (context.get("items") or [{}])[0]
    situation = Situation.model_validate(context.get("situation") or {})
    if history.enabled:
        record = FeedbackRecord(
            perfume=item.get("name") if context.get("mode") == "Обычный парфюм" else None,
            layering=[item.get("base_name"), item.get("top_name")] if context.get("mode") == "Наслаивание" else [],
            timestamp=datetime.now(timezone.utc), event=situation.event, temperature=situation.temperature, humidity=situation.humidity,
            circumstance=situation.circumstance, outfit_profile=situation.outfit.model_dump(), effect=situation.desired_effect,
            sprays=str(item.get("spray_count") or item.get("spray_plan") or ""), rating=data["feedback_rating"], feedback_tags=tags,
            recommendation_score=float(item.get("score") or 0), application_order=item.get("application_order") or [],
        )
        await history.append_feedback(record)
        text = "Сохранил. Это будет влиять на следующие рекомендации."
    else:
        text = "Принял. Persistent storage не настроен, поэтому после cold start история не сохранится."
    await state.clear()
    await message.answer(text, reply_markup=main_keyboard())


# ---------- preset layering ----------

PRESET_PAGE_SIZE = 6


def _format_preset_page(pairs: list[dict], offset: int) -> str:
    page = pairs[offset:offset + PRESET_PAGE_SIZE]
    if not page:
        return "Больше готовых пар нет."
    lines = [f"Готовые пары {offset + 1}–{offset + len(page)} из {len(pairs)}:", ""]
    for index, item in enumerate(page, offset + 1):
        lines += [
            f"{index}. {item['base']['name']} + {item['top']['name']}",
            f"Оценка: {item['score']:.0f}/100",
            f"Идея: {item.get('label', '')}",
            f"Когда: {item.get('best_for', '')}",
            f"Как: {item.get('apply', '')}",
            "",
        ]
    return "\n".join(lines).strip()


@router.message(F.text == "Готовые пары наслаивания")
async def preset_layering(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    situation = await _require_last_situation(message, state, notify=False)
    pairs = get_preset_layering_pairs(situation)
    await state.set_state(PresetLayeringBrowseForm.active)
    await state.update_data(preset_offset=PRESET_PAGE_SIZE, preset_situation=situation.model_dump(mode="json") if situation else None)
    await message.answer(_format_preset_page(pairs, 0), reply_markup=preset_layering_keyboard(len(pairs) > PRESET_PAGE_SIZE))


@router.message(PresetLayeringBrowseForm.active, F.text == "Ещё готовые пары")
async def more_preset_layering(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    data = await state.get_data()
    offset = int(data.get("preset_offset", 0))
    raw_situation = data.get("preset_situation")
    situation = Situation.model_validate(raw_situation) if raw_situation else None
    pairs = get_preset_layering_pairs(situation)
    await state.update_data(preset_offset=offset + PRESET_PAGE_SIZE)
    has_more = offset + PRESET_PAGE_SIZE < len(pairs)
    await message.answer(_format_preset_page(pairs, offset), reply_markup=preset_layering_keyboard(has_more))


# ---------- why not / reverse ----------

async def _require_last_situation(message: Message, state: FSMContext | None = None, *, notify: bool = True) -> Situation | None:
    if state is not None:
        data = await state.get_data()
        context = data.get("recommendation_context")
        if context and context.get("situation"):
            return Situation.model_validate(context["situation"])
    saved = await history.get_last_situation() if history.enabled else None
    if not saved:
        if notify:
            await message.answer("Сначала сделай обычный подбор — нужен текущий контекст.", reply_markup=main_keyboard())
        return None
    return Situation.model_validate(saved)


@router.message(F.text == "Почему не этот аромат?")
async def why_not_start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    if not await _require_last_situation(message, state): return
    await state.set_state(WhyNotForm.brand); await message.answer("Выбери бренд кандидата.", reply_markup=brand_keyboard(_brands()))


@router.message(WhyNotForm.brand)
async def why_brand(message: Message, state: FSMContext):
    ps = _perfumes_by_brand(message.text or "")
    if not ps: return
    await state.set_state(WhyNotForm.perfume); await message.answer("Выбери аромат.", reply_markup=perfume_keyboard(ps))


@router.message(WhyNotForm.perfume)
async def why_perfume(message: Message, state: FSMContext):
    candidate = _perfume_from_label(message.text or "")
    situation = await _require_last_situation(message, state)
    await state.clear()
    if not candidate or not situation: return
    snapshot = await _personal_snapshot(); top = recommend_situation(situation, 1, snapshot, diversity=False)[0]; other = score_profile(candidate, situation, snapshot)
    lines = [f"{top.name}: {top.score:.0f}/100", f"{other.name}: {other.score:.0f}/100", ""] + comparison_reason(top, other)
    await message.answer("\n".join(lines), reply_markup=main_keyboard())


@router.message(F.text == "Хочу надеть конкретный аромат")
async def reverse_start(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    await state.set_state(ReverseForm.brand); await message.answer("Выбери бренд.", reply_markup=brand_keyboard(_brands()))


@router.message(ReverseForm.brand)
async def reverse_brand(message: Message, state: FSMContext):
    ps = _perfumes_by_brand(message.text or "")
    if not ps:
        await message.answer("Выбери бренд из кнопок.", reply_markup=brand_keyboard(_brands()))
        return
    await state.set_state(ReverseForm.perfume); await message.answer("Выбери аромат.", reply_markup=perfume_keyboard(ps))


def _best_profile_time(profile) -> str:
    values = {
        "утро": profile.morning_score, "день": profile.day_score,
        "вечер": profile.evening_score, "ночь": profile.night_score,
    }
    return max(values, key=values.get)


def _best_profile_event(profile) -> str:
    labels = {
        "study": "учёба", "work": "работа", "meeting": "встреча", "walk": "прогулка",
        "cafe": "кафе", "date": "свидание", "restaurant": "ресторан", "party": "вечеринка",
        "club": "клуб", "birthday": "день рождения", "active": "активный день", "casual": "обычный день",
    }
    event = max(EVENT_SCORE_KEYS, key=lambda key: getattr(profile, EVENT_SCORE_KEYS[key]))
    return labels[event]


def _adaptation_advice(result, profile, situation: Situation) -> str:
    temp = situation.feels_like if situation.feels_like is not None else situation.temperature
    if temp > profile.comfortable_temperature_max:
        return "Перенеси на вечер, нанеси 1 пшик на грудь под одежду и избегай тесного помещения."
    if temp < profile.comfortable_temperature_min:
        return "Нанеси на кожу под одежду. Для улицы добавь один пшик на затылок."
    if situation.circumstance in {"small_room", "close_distance"} and profile.projection >= 3.8:
        return "Оставь 1 пшик на груди под одеждой. Не наноси на переднюю часть шеи."
    if situation.outdoor_exposure == "high" and profile.projection <= 3.2:
        return "Добавь один пшик на затылок или верхнюю одежду с расстояния."
    if result.score < 60:
        return f"Сократи нанесение до 1 пшика и используй ближе к периоду «{_best_profile_time(profile)}»."
    return "Используй рекомендованную дозировку без дополнительного усиления."


async def _finish_reverse_with_situation(message: Message, state: FSMContext, situation: Situation) -> None:
    data = await state.get_data()
    perfume = _perfume_by_id(data.get("reverse_perfume_id"))
    if not perfume:
        await state.clear()
        await message.answer("Не нашёл выбранный аромат. Выбери его ещё раз.", reply_markup=main_keyboard())
        return
    snapshot = await _personal_snapshot()
    result = score_profile(perfume, situation, snapshot)
    profile = build_perfume_profile(perfume)
    pairs = [
        analyze_pair_situation(perfume, other, situation, snapshot)
        for other in PERFUMES if other.get("id") != perfume.get("id")
    ]
    pairs.sort(key=lambda item: (-item.score, item.base_name, item.top_name))
    lines = [
        f"{result.name}: {result.score:.0f}/100",
        f"Лучшее время: {_best_profile_time(profile)}",
        f"Лучший сценарий: {_best_profile_event(profile)}",
        f"Как: {result.spray_count} пш. — {', '.join(result.spray_locations)}",
        f"Главный риск: {risk_line(result)}.",
        f"Адаптация: {_adaptation_advice(result, profile, situation)}",
    ]
    if pairs:
        lines.append("Подходящие наслоения:")
        lines.extend(f"{index}. {pair.base_name} + {pair.top_name}, {pair.score:.0f}/100, {pair.spray_plan}" for index, pair in enumerate(pairs[:3], 1))
    await state.clear()
    await message.answer("\n".join(lines), reply_markup=main_keyboard())


@router.message(ReverseForm.perfume)
async def reverse_perfume(message: Message, state: FSMContext):
    perfume = _perfume_from_label(message.text or "")
    if not perfume:
        await message.answer("Выбери аромат из кнопок.")
        return
    situation = await _require_last_situation(message, state, notify=False)
    await state.update_data(reverse_perfume_id=perfume.get("id"))
    if situation:
        await _finish_reverse_with_situation(message, state, situation)
        return
    await state.clear()
    await state.update_data(reverse_perfume_id=perfume.get("id"))
    await state.set_state(PerfumeForm.location)
    previous = await history.get_last_location() if history.enabled else None
    await message.answer(
        "Для точной оценки нужны погода, событие и образ. Отправь геолокацию или напиши город.",
        reply_markup=location_keyboard(bool(previous)),
    )


# ---------- debug ----------

@router.message(Command("debug_recommendation"))
async def debug_recommendation(message: Message, state: FSMContext):
    if await deny_if_not_owner(message): return
    context = (await state.get_data()).get("recommendation_context") or (await history.get_last_recommendation() if history.enabled else None)
    if not context or not context.get("items"):
        await message.answer("Нет последней рекомендации."); return
    item = context["items"][0]
    payload = {"situation": context.get("situation"), "result": {"score": item.get("score"), "confidence": item.get("confidence"), "breakdown": item.get("breakdown"), "warnings": item.get("hard_warnings") or item.get("warnings"), "ai_adjustment": item.get("ai_adjustment")}}
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    for chunk in _split_text(text, 3800): await message.answer(chunk)


# ---------- helpers ----------

def _brands() -> list[str]:
    return sorted({str(p.get("brand", "Unknown")) for p in PERFUMES}, key=str.lower)


def _perfumes_by_brand(brand: str) -> list[dict]:
    return sorted([p for p in PERFUMES if p.get("brand") == brand], key=lambda p: str(p.get("name", "")).lower())


def _perfume_by_id(perfume_id) -> dict | None:
    return next((p for p in PERFUMES if str(p.get("id")) == str(perfume_id)), None)


def _perfume_from_label(label: str) -> dict | None:
    clean = (label or "").strip()
    return next((p for p in PERFUMES if clean == f"{p.get('name')} — {p.get('brand')}"), None) or find_perfume(clean)


def _split_text(text: str, limit: int = 3800) -> list[str]:
    chunks, current, length = [], [], 0
    for line in text.splitlines():
        add = len(line) + 1
        if current and length + add > limit:
            chunks.append("\n".join(current)); current, length = [], 0
        current.append(line); length += add
    if current: chunks.append("\n".join(current))
    return chunks or [""]


bot = Bot(token=config.bot_token)
dp = Dispatcher(storage=create_fsm_storage(config))
dp.include_router(router)


async def start_polling():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_polling())

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import aiohttp


WARDROBE_PATH = Path(os.getenv("WARDROBE_PATH", "app/data/wardrobe.json"))


def _ensure_store() -> None:
    WARDROBE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not WARDROBE_PATH.exists():
        WARDROBE_PATH.write_text("[]", encoding="utf-8")


def load_wardrobe() -> list[dict]:
    try:
        _ensure_store()
        return json.loads(WARDROBE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_wardrobe(items: list[dict]) -> None:
    _ensure_store()
    WARDROBE_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_wardrobe() -> None:
    save_wardrobe([])


def add_wardrobe_item(item: dict) -> dict:
    items = load_wardrobe()
    item = dict(item)
    item.setdefault("id", str(uuid.uuid4())[:8])
    items.append(item)
    save_wardrobe(items)
    return item


def format_wardrobe_list(items: list[dict]) -> str:
    if not items:
        return "Гардероб пуст. Нажми «Добавить вещь» и отправь фото."

    lines = [f"Гардероб: {len(items)} вещей", ""]
    for index, item in enumerate(items, start=1):
        category = item.get("category", "вещь")
        colors = ", ".join(item.get("colors", [])) or "цвет не определен"
        style = ", ".join(item.get("style_tags", [])) or "стиль не определен"
        desc = item.get("description", "")
        lines.append(f"{index}. {category}: {colors}")
        lines.append(f"Стиль: {style}")
        if desc:
            lines.append(f"Описание: {desc[:130]}")
        lines.append("")
    return "\n".join(lines).strip()


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


async def analyze_clothing_image(
    image_bytes: bytes,
    nvidia_api_key: str | None,
    nvidia_model: str,
    nvidia_base_url: str,
    user_caption: str = "",
) -> dict:
    if not nvidia_api_key or not nvidia_model:
        return _fallback_item(user_caption)

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{image_b64}"

    prompt = (
        "Ты анализируешь одну вещь из гардероба пользователя. "
        "Ответь строго JSON без markdown. Поля: "
        "category, colors, style_tags, season_tags, formality, weather_tags, description, pairing_tips. "
        "colors/style_tags/season_tags/weather_tags/pairing_tips должны быть списками строк. "
        "Пиши на русском кратко. "
        f"Комментарий пользователя: {user_caption or 'нет'}"
    )

    payload = {
        "model": nvidia_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }

    headers = {
        "Authorization": f"Bearer {nvidia_api_key}",
        "Content-Type": "application/json",
    }

    url = f"{nvidia_base_url}/chat/completions"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=60) as response:
            raw = await response.text()
            if response.status >= 400:
                return _fallback_item(user_caption, error=f"NVIDIA API error {response.status}: {raw[:200]}")
            data = json.loads(raw)

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = _extract_json(content)
    if not parsed:
        return _fallback_item(user_caption, error="Не смог разобрать JSON от модели.")

    return _normalize_item(parsed, user_caption)


def _normalize_item(item: dict, user_caption: str = "") -> dict:
    def as_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    return {
        "category": str(item.get("category") or "вещь"),
        "colors": as_list(item.get("colors")),
        "style_tags": as_list(item.get("style_tags")),
        "season_tags": as_list(item.get("season_tags")),
        "formality": str(item.get("formality") or "casual"),
        "weather_tags": as_list(item.get("weather_tags")),
        "description": str(item.get("description") or user_caption or ""),
        "pairing_tips": as_list(item.get("pairing_tips")),
        "user_caption": user_caption,
    }


def _fallback_item(user_caption: str = "", error: str | None = None) -> dict:
    item = {
        "category": "вещь",
        "colors": [],
        "style_tags": [],
        "season_tags": [],
        "formality": "casual",
        "weather_tags": [],
        "description": user_caption or "Фото добавлено, но AI-анализ не выполнен.",
        "pairing_tips": [],
        "user_caption": user_caption,
    }
    if error:
        item["analysis_error"] = error
    return item


async def recommend_outfit_with_ai(
    wardrobe_items: list[dict],
    weather: dict,
    place: str,
    occasion: str,
    mood: str,
    circumstances: str,
    nvidia_api_key: str | None,
    nvidia_model: str,
    nvidia_base_url: str,
) -> str:
    if not wardrobe_items:
        return "Гардероб пуст. Сначала добавь вещи через «Добавить вещь»."

    if not nvidia_api_key or not nvidia_model:
        return _fallback_outfit(wardrobe_items, weather, place, occasion, mood, circumstances)

    compact_items = []
    for index, item in enumerate(wardrobe_items, start=1):
        compact_items.append({
            "n": index,
            "category": item.get("category"),
            "colors": item.get("colors", []),
            "style_tags": item.get("style_tags", []),
            "season_tags": item.get("season_tags", []),
            "formality": item.get("formality"),
            "weather_tags": item.get("weather_tags", []),
            "description": item.get("description", ""),
        })

    prompt = (
        "Ты персональный стилист. Подбери образ из гардероба пользователя. "
        "Не выдумывай вещи, используй только список. Ответь кратко на русском. "
        "Формат: 1) Образ, 2) Почему подходит, 3) Что исправить/добавить, 4) Риск. "
        f"Место: {place}. Погода: {weather}. Событие: {occasion}. Настроение: {mood}. Обстановка: {circumstances}. "
        f"Гардероб JSON: {json.dumps(compact_items, ensure_ascii=False)}"
    )

    payload = {
        "model": nvidia_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.35,
        "max_tokens": 900,
    }
    headers = {"Authorization": f"Bearer {nvidia_api_key}", "Content-Type": "application/json"}
    url = f"{nvidia_base_url}/chat/completions"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=60) as response:
                raw = await response.text()
                if response.status >= 400:
                    return _fallback_outfit(wardrobe_items, weather, place, occasion, mood, circumstances, f"NVIDIA API error {response.status}")
                data = json.loads(raw)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "Не получил ответ от модели.").strip()
    except Exception as exc:
        return _fallback_outfit(wardrobe_items, weather, place, occasion, mood, circumstances, str(exc))


def _fallback_outfit(items: list[dict], weather: dict, place: str, occasion: str, mood: str, circumstances: str, error: str | None = None) -> str:
    temp = weather.get("temperature", "?")
    chosen = items[:4]
    lines = [f"{place}: {temp}°C", "AI-анализ недоступен, даю базовый подбор:", ""]
    for item in chosen:
        colors = ", ".join(item.get("colors", [])) or "цвет не определен"
        lines.append(f"— {item.get('category', 'вещь')}: {colors}")
    lines.append("")
    lines.append(f"Сценарий: {occasion}. Настроение: {mood}. Обстановка: {circumstances}.")
    if error:
        lines.append(f"Технически: {error}")
    return "\n".join(lines)

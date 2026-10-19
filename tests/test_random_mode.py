import importlib
import random
from unittest.mock import AsyncMock

import pytest

from app.data.perfumes import PERFUMES


def keyboard_texts(keyboard):
    return {button.text for row in keyboard.keyboard for button in row}


def test_random_mode_keyboards_have_expected_actions():
    from app.keyboards import main_keyboard, random_result_keyboard

    assert "🎲 Рандом" in keyboard_texts(main_keyboard())
    assert keyboard_texts(random_result_keyboard()) == {
        "🎲 Ещё рандом",
        "Наслоение с этим ароматом",
        "Информация об аромате",
        "Главное меню",
    }


def test_weighted_random_scores_whole_catalog_and_excludes_previous():
    from app.services.randomizer import random_candidate, random_weight

    scored = [random_weight(perfume) for perfume in PERFUMES]
    assert all(0 < candidate.weight for candidate in scored)
    assert all(0 <= candidate.versatility_score <= 100 for candidate in scored)
    assert len({round(candidate.weight, 4) for candidate in scored}) > 1

    previous_id = PERFUMES[0]["id"]
    for seed in range(20):
        picked = random_candidate(PERFUMES, exclude_id=previous_id, rng=random.Random(seed))
        assert picked.perfume["id"] != previous_id
        assert 0 <= picked.versatility_score <= 100


@pytest.fixture
def bot_module(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "load_config", lambda: config.Config(bot_token="123456:test"))
    bot = importlib.import_module("app.bot")
    monkeypatch.setattr(bot, "config", config.Config(bot_token="123456:test"))
    return bot


@pytest.fixture
def state():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage

    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))


@pytest.mark.asyncio
async def test_random_handler_ignores_and_removes_saved_scenario(bot_module, state, monkeypatch):
    first, second = PERFUMES[:2]
    await state.update_data(recommendation_context={"situation": {"temperature": -50}})

    calls = []
    def fake_random_candidate(perfumes, exclude_id=None, rng=None):
        from app.services.randomizer import RandomCandidate, random_weight
        calls.append(exclude_id)
        perfume = first if exclude_id != first["id"] else second
        weighted = random_weight(perfume)
        return RandomCandidate(perfume=perfume, versatility_score=weighted.versatility_score, weight=weighted.weight)

    monkeypatch.setattr(bot_module, "random_candidate", fake_random_candidate)
    history = AsyncMock()
    monkeypatch.setattr(bot_module, "history", history)
    message = AsyncMock(); message.text = "🎲 Рандом"

    await bot_module.random_perfume(message, state)
    data = await state.get_data()
    assert data == {"last_random_perfume_id": first["id"]}
    assert "Универсальность" in message.answer.call_args.args[0]
    assert first["name"] in message.answer.call_args.args[0]
    assert "🎲 Ещё рандом" in keyboard_texts(message.answer.call_args.kwargs["reply_markup"])

    message.text = "🎲 Ещё рандом"
    await bot_module.random_perfume(message, state)
    assert calls == [None, first["id"]]
    assert (await state.get_data())["last_random_perfume_id"] == second["id"]
    history.assert_not_called()


@pytest.mark.asyncio
async def test_random_layering_and_info_use_only_random_perfume(bot_module, state):
    perfume = PERFUMES[0]
    await state.update_data(last_random_perfume_id=perfume["id"])
    message = AsyncMock(); message.text = "Наслоение с этим ароматом"

    await bot_module.random_layering(message, state)
    layering_text = message.answer.call_args.args[0]
    assert perfume["name"] in layering_text
    assert "+" in layering_text
    assert "Как:" in layering_text
    assert "Главное меню" in keyboard_texts(message.answer.call_args.kwargs["reply_markup"])
    assert set((await state.get_data())) == {"last_random_perfume_id"}

    message.text = "Информация об аромате"
    await bot_module.random_perfume_info(message, state)
    info_text = message.answer.call_args.args[0]
    assert perfume["name"] in info_text
    assert perfume["brand"] in info_text
    assert "Диапазон температуры" in info_text

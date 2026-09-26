import importlib
from unittest.mock import AsyncMock

import pytest

from app.data.perfumes import PERFUMES
from app.services.layering import PRESET_LAYERING_PAIRS, analyze_pair_situation, recommend_layering_situation
from app.services.recommender import find_perfume
from app.services.scoring import score_perfume
from app.services.situation_parser import build_situation

EXPECTED = {
    'Bleu de Chanel Eau de Parfum': ('Chanel', {'citrus', 'ambery_cedar', 'sandalwood', 'musk'}),
    'Blue Seduction': ('Antonio Banderas', {'bergamot', 'cassis', 'mint', 'watermelon', 'cardamom', 'cedar', 'cappuccino'}),
}


def situation(temp=22):
    return build_situation(
        event='meeting', outfit_text='', circumstance='indoor', effect='clean',
        weather={'temperature': temp, 'humidity': 55}, manual_time='day', manual_season='summer',
    )


@pytest.mark.parametrize('name', EXPECTED)
def test_new_perfumes_have_complete_profiles_and_score(name):
    perfume = find_perfume(name)
    assert perfume is not None
    brand, required_notes = EXPECTED[name]
    assert perfume['brand'] == brand
    assert perfume['gender'] == 'men'
    assert perfume['volume_label'] == '5 мл'
    assert required_notes <= set(perfume['known_notes'])
    assert perfume['fact_sources']
    result = score_perfume(perfume, situation())
    assert 0 <= result.score <= 100
    assert result.spray_count >= 1


def test_collection_and_layering_cover_new_perfumes():
    assert len(PERFUMES) == 46
    assert len({p['id'] for p in PERFUMES}) == 46
    assert len(recommend_layering_situation(situation(), limit=2000)) == 1035
    for name in EXPECTED:
        assert any(name in (pair['first'], pair['second']) for pair in PRESET_LAYERING_PAIRS)
        for other in PERFUMES:
            if other['name'] == name:
                continue
            result = analyze_pair_situation(find_perfume(name), other, situation())
            assert 0 <= result.score <= 100


@pytest.fixture
def bot_module(monkeypatch):
    from app import config
    monkeypatch.setattr(config, 'load_config', lambda: config.Config(bot_token='123456:test'))
    bot = importlib.import_module('app.bot')
    monkeypatch.setattr(bot, 'config', config.Config(bot_token='123456:test'))
    return bot


def keyboard_texts(keyboard):
    return {button.text for row in keyboard.keyboard for button in row}


def test_manual_layering_is_back_in_main_menu_and_state(bot_module):
    from app.keyboards import main_keyboard
    from app.states import ManualLayeringForm
    assert 'Наслаивание вручную' in keyboard_texts(main_keyboard())
    assert ManualLayeringForm.first_brand.state
    assert ManualLayeringForm.second_perfume.state


@pytest.mark.asyncio
async def test_manual_layering_selects_two_perfumes_and_returns_analysis(bot_module):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=1, user_id=1))
    message = AsyncMock()

    await bot_module.manual_layering_start(message, state)
    message.text = 'Chanel'
    await bot_module.manual_first_brand(message, state)
    message.text = 'Bleu de Chanel Eau de Parfum — Chanel'
    await bot_module.manual_first_perfume(message, state)
    message.text = 'Antonio Banderas'
    await bot_module.manual_second_brand(message, state)
    message.text = 'Blue Seduction — Antonio Banderas'
    await bot_module.manual_second_perfume(message, state)

    output = message.answer.call_args.args[0]
    assert 'Bleu de Chanel Eau de Parfum' in output
    assert 'Blue Seduction' in output
    assert '/100' in output and 'Как:' in output
    assert output.count('5 мл') == 2
    await storage.close()


@pytest.mark.asyncio
async def test_manual_layering_uses_and_preserves_current_situation(bot_module):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=1, user_id=1))
    current = situation(31)
    context = {'mode': 'Обычный парфюм', 'situation': current.model_dump(mode='json'), 'items': []}
    await state.update_data(first_perfume_id=45, recommendation_context=context)
    message = AsyncMock()
    message.text = 'Blue Seduction — Antonio Banderas'
    await bot_module.manual_second_perfume(message, state)
    output = message.answer.call_args.args[0]
    assert 'Уверенность:' in output
    assert 'Оценка дана без погоды и события.' not in output
    assert (await state.get_data())['recommendation_context'] == context
    await storage.close()


@pytest.mark.asyncio
async def test_manual_layering_rejects_same_perfume(bot_module):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=1, user_id=1))
    await state.update_data(first_perfume_id=45)
    message = AsyncMock()
    message.text = 'Bleu de Chanel Eau de Parfum — Chanel'
    await bot_module.manual_second_perfume(message, state)
    assert message.answer.call_args.args[0] == 'Нужны два разных аромата.'
    await storage.close()

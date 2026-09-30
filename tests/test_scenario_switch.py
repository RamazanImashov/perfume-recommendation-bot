from datetime import datetime
from unittest.mock import AsyncMock
import importlib

import pytest
from app.keyboards import recommendation_result_keyboard
from app.models.situation import Situation


@pytest.fixture
def ui(monkeypatch):
    from app import config
    monkeypatch.setattr(config, 'load_config', lambda: config.Config(bot_token='123456:test'))
    bot = importlib.import_module('app.bot')
    monkeypatch.setattr(bot, 'config', config.Config(bot_token='123456:test'))
    monkeypatch.setattr(bot, '_personal_snapshot', AsyncMock(return_value=None))
    return bot


@pytest.fixture
def state():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.base import StorageKey
    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))


@pytest.mark.parametrize('mode,label', [
    ('Обычный парфюм', 'Наслоения под этот сценарий'),
    ('Наслаивание', 'Ароматы под этот сценарий'),
])
def test_mode_keyboard(mode, label):
    labels = [b.text for row in recommendation_result_keyboard(mode).keyboard for b in row]
    assert label in labels
    assert 'Другие варианты' in labels
    assert 'Как прошло?' in labels


@pytest.mark.asyncio
@pytest.mark.parametrize('saved', [False, True])
async def test_switch_both_directions_preserves_context(ui, state, monkeypatch, saved):
    situation = Situation(event='restaurant', season='autumn', time_of_day='evening',
                          temperature=13, humidity=60, timezone='Asia/Bishkek',
                          target_datetime=datetime.fromisoformat('2026-10-03T20:30:00+06:00'),
                          circumstance='indoor', desired_effect='expensive', importance='high')
    context = {'mode':'Обычный парфюм', 'situation':situation.model_dump(mode='json'),
               'items':[{'name':'old perfume'}]}
    history = AsyncMock(); history.enabled = saved
    history.get_last_recommendation.return_value = context
    monkeypatch.setattr(ui, 'history', history)
    if not saved:
        await state.update_data(recommendation_context=context, recommendation_offset=12)
    message = AsyncMock(); message.text = 'Наслоения под этот сценарий'
    await ui.switch_recommendation_mode(message, state)
    data = await state.get_data()
    assert data['recommendation_context']['mode'] == 'Наслаивание'
    assert data['recommendation_context']['situation'] == context['situation']
    assert len(data['recommendation_context']['items']) == 3
    assert all('base_name' in x for x in data['recommendation_context']['items'])
    assert data['recommendation_offset'] == 3
    assert 'Ароматы под этот сценарий' in str(message.answer.call_args.kwargs['reply_markup'])
    await ui.more_recommendations(message, state)
    assert (await state.get_data())['recommendation_offset'] == 6
    message.text = 'Ароматы под этот сценарий'
    await ui.switch_recommendation_mode(message, state)
    data = await state.get_data()
    assert data['recommendation_context']['mode'] == 'Обычный парфюм'
    assert data['recommendation_context']['situation'] == context['situation']
    assert data['recommendation_offset'] == 3
    assert all('name' in x and 'base_name' not in x for x in data['recommendation_context']['items'])
    if saved:
        assert history.save_last_recommendation.call_args.args[0] == data['recommendation_context']


@pytest.mark.asyncio
async def test_switch_without_scenario(ui, state, monkeypatch):
    history = AsyncMock(); history.enabled = False
    monkeypatch.setattr(ui, 'history', history)
    message = AsyncMock(); message.text = 'Наслоения под этот сценарий'
    await ui.switch_recommendation_mode(message, state)
    assert 'Сначала' in message.answer.call_args.args[0]
    assert 'recommendation_context' not in await state.get_data()

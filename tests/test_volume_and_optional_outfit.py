from copy import deepcopy

import pytest

from app.data.perfumes import PERFUMES
from app.models.perfume import build_perfume_profile
from app.services.layering import analyze_pair_situation
from app.services.scoring import score_perfume, confidence_for
from app.services.situation_parser import build_situation

SMALL_IDS = {1, 2, 3, 4, 5, 8, 10, 11, 12, 19, 32, 33, 37, 38, 39, 40, 41, 42, 43, 44}


def situation(**kwargs):
    data = dict(event='restaurant', outfit_text='', circumstance='indoor', effect='any',
                weather={'temperature': 18, 'humidity': 55}, manual_time='evening', manual_season='autumn')
    data.update(kwargs)
    return build_situation(**data)


def test_inventory_exact_partition():
    assert {p['id'] for p in PERFUMES if p.get('volume_group') == 'small'} == SMALL_IDS
    assert sum(p.get('volume_label') == '100 мл' for p in PERFUMES) == 24
    assert all(p.get('volume_label') == '5 или 10 мл' for p in PERFUMES if p['id'] in SMALL_IDS)


def test_skipped_outfit_does_not_affect_scores_or_confidence():
    s = situation()
    other = s.model_copy(deep=True)
    other.outfit.style = ['formal']
    other.outfit.formality = 5
    other.outfit.palette = 'dark'
    for p in PERFUMES:
        a, b = score_perfume(p, s), score_perfume(p, other)
        assert a.score == b.score
        assert not a.breakdown.evidence['outfit']
        assert confidence_for(a, build_perfume_profile(p), s) == confidence_for(b, build_perfume_profile(p), other)


def test_skipped_weight_redistribution():
    r = score_perfume(PERFUMES[0], situation())
    b = r.breakdown
    expected = (b.event_score * .30 + b.climate_score * .25 + b.effect_score * .10 +
                b.environment_score * .15 + b.time_score * .10 + b.season_score * .05 + b.personal_score * .05)
    assert b.weighted_score == pytest.approx(expected)


def test_volume_metadata_does_not_affect_ranking():
    p = deepcopy(PERFUMES[0])
    before = score_perfume(p, situation()).score
    p.update(volume_group='large', volume_label='100 мл')
    assert score_perfume(p, situation()).score == before


def test_layering_respects_individual_temperature_limit():
    p, q = deepcopy(PERFUMES[0]), deepcopy(PERFUMES[36])
    p.update(hard_temperature_min=-30, hard_temperature_max=50)
    normal = analyze_pair_situation(p, q, situation())
    p['hard_temperature_max'] = 10
    restricted = analyze_pair_situation(p, q, situation())
    assert restricted.score <= score_perfume(p, situation()).score
    assert restricted.score < normal.score
    assert any('температур' in w for w in restricted.warnings)


@pytest.fixture
def bot_module(monkeypatch):
    import importlib
    from app import config
    monkeypatch.setattr(config, 'load_config', lambda: config.Config(bot_token='123456:test'))
    bot = importlib.import_module('app.bot')
    monkeypatch.setattr(bot, 'config', config.Config(bot_token='123456:test'))
    return bot


@pytest.mark.asyncio
async def test_skip_handler_clears_old_outfit_and_advances(bot_module):
    from unittest.mock import AsyncMock
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.base import StorageKey
    from app.states import PerfumeForm
    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=1, user_id=1))
    await state.update_data(outfit_text='чёрный костюм')
    message = AsyncMock()
    message.text = 'Пропустить'
    await bot_module.get_outfit(message, state)
    assert (await state.get_data())['outfit_text'] == ''
    assert await state.get_state() == PerfumeForm.circumstance.state
    await storage.close()


@pytest.mark.asyncio
async def test_volume_filter_and_labels(bot_module):
    from unittest.mock import AsyncMock
    from app.keyboards import perfume_list_keyboard
    labels = {b.text for row in perfume_list_keyboard().keyboard for b in row}
    assert {'5 или 10 мл', '100 мл'} <= labels
    message, state = AsyncMock(), AsyncMock()
    for label, expected in [('5 или 10 мл', 20), ('100 мл', 24)]:
        message.answer.reset_mock()
        message.text = label
        await bot_module.show_by_volume(message, state)
        text = '\n'.join(c.args[0] for c in message.answer.call_args_list)
        assert sum(line.startswith('— ') for line in text.splitlines()) == expected
        assert all(label in line for line in text.splitlines() if line.startswith('— '))
    rendered = bot_module.format_perfume_results(situation(), [score_perfume(PERFUMES[0], situation())])
    assert '5 или 10 мл' in rendered
    pair = analyze_pair_situation(PERFUMES[0], PERFUMES[5], situation())
    rendered = bot_module.format_layering_results(situation(), [pair])
    assert '5 или 10 мл' in rendered and '100 мл' in rendered


@pytest.mark.parametrize('event,temp,room', [('work', 32, 'small_room'), ('restaurant', 18, 'indoor'), ('walk', -5, 'outdoor')])
def test_context_scores_are_finite_without_outfit(event, temp, room):
    s = situation(event=event, circumstance=room, weather={'temperature': temp, 'humidity': 75})
    results = [score_perfume(p, s) for p in PERFUMES]
    assert all(0 <= r.score <= 100 for r in results)
    assert all(not r.breakdown.evidence['outfit'] for r in results)


def test_new_weights_normalize_and_temperature_outweighs_season():
    from app.services.scoring_config import SCORE_WEIGHTS, NO_OUTFIT_WEIGHTS
    for weights in (SCORE_WEIGHTS, NO_OUTFIT_WEIGHTS):
        assert sum(weights.values()) == pytest.approx(1)
        assert weights['climate'] > weights['season']


def test_preset_page_shows_volume_and_restrictions(bot_module):
    from app.services.layering import get_preset_layering_pairs
    pairs = get_preset_layering_pairs(situation(weather={'temperature': 36, 'humidity': 80}))
    assert any(p.get('warnings') for p in pairs)
    text = "\n".join(bot_module._format_preset_page(pairs, offset) for offset in range(0, len(pairs), 6))
    assert 'мл' in text
    assert 'Риск:' in text

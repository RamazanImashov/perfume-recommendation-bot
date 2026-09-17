import pytest
from app.data.perfumes import PERFUMES
from app.services.recommender import find_perfume
from app.services.layering import PRESET_LAYERING_PAIRS, analyze_pair_situation
from app.services.scoring import score_perfume
from app.services.situation_parser import build_situation

NAMES = ['Stronger With You Powerfully', 'Born in Roma Uomo Extradose', 'Narcotic Delight', 'Bitter Peach', 'Gentle Fluidity Silver']

def situation(temp=16):
    return build_situation(event='restaurant', outfit_text='белая рубашка бежевые брюки лоферы smart casual', circumstance='indoor', effect='expensive', weather={'temperature':temp,'feels_like':temp,'humidity':80}, manual_time='evening', manual_season='autumn', latitude=42)

@pytest.mark.parametrize('name', NAMES)
def test_added_profiles_and_pairs(name):
    p = find_perfume(name)
    assert p is not None
    assert p['id'] >= 40
    assert any(name in (pair['first'], pair['second']) for pair in PRESET_LAYERING_PAIRS)
    for other in PERFUMES:
        if other['id'] == p['id']: continue
        r = analyze_pair_situation(p, other, situation())
        assert 0 <= r.score <= 100
        assert r.base_name != r.top_name
    r = score_perfume(p, situation())
    assert 0 <= r.score <= 100 and r.spray_count >= 1

@pytest.mark.parametrize('name', ['Stronger With You Powerfully','Narcotic Delight','Bitter Peach'])
def test_sweet_new_profiles_penalized_in_heat(name):
    p = find_perfume(name)
    assert p is not None
    assert score_perfume(p, situation(34)).score < score_perfume(p, situation(16)).score

def test_catalogue_count_and_identity():
    assert len(PERFUMES) == 44
    assert len({p['id'] for p in PERFUMES}) == 44
    assert find_perfume('Born in Roma Uomo Extradose')['gender'] == 'men'

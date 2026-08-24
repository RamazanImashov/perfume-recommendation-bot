from __future__ import annotations

from datetime import datetime

import pytest

from app.data.perfumes import PERFUMES
from app.services.layering import PRESET_LAYERING_PAIRS, analyze_pair_situation, recommend_layering_situation
from app.services.outfit_parser import parse_outfit_profile
from app.services.recommender import find_perfume, recommend_situation
from app.services.scoring import score_perfume
from app.services.situation_parser import build_situation, infer_season, infer_time_of_day
from app.services.validator import validate_perfumes
from app.services.weather import _closest_hour_index

FRESH = {"Light Blue pour Homme", "Hawas for Him", "Art Of Universe", "Maahir Legacy", "Turathi Blue", "Pacific Chill", "Imagination", "9AM Dive", "Symphony", "Y Eau de Parfum", "Rare Reef"}
COLD = {"Tobacco Vanille", "Khamrah", "Khamrah Qahwa", "Khamrah Dukhan", "Liquid Brun", "The Most Wanted Parfum", "Stronger With You Absolutely", "Ombré Leather (2018)"}
DATE = {"Lost Cherry", "The Most Wanted Parfum", "Stronger With You Absolutely", "Oud Wood", "Aventus"}
FORMAL = {"Oud Wood", "Aventus", "Ombré Leather (2018)", "Tobacco Vanille", "The Most Wanted Parfum"}
HEAVY = {"Tobacco Vanille", "Khamrah", "Khamrah Qahwa", "Khamrah Dukhan", "Liquid Brun", "9PM Elixir"}


def weather(temp, humidity=55, rain=0, cloud=40, wind=5, is_day=True):
    return {"temperature": temp, "feels_like": temp, "humidity": humidity, "rain": rain, "precipitation": rain, "cloud_cover": cloud, "wind_speed": wind, "is_day": is_day}


def scenario(name, temp, humidity, event, outfit, circumstance, effect, strong, forbidden=None, min_score=45, rain=0, cloud=40, wind=5, time="day"):
    return {"name": name, "weather": weather(temp, humidity, rain, cloud, wind, time in {"morning", "day"}), "event": event, "outfit": outfit, "circumstance": circumstance, "effect": effect, "strong": set(strong), "forbidden": set(forbidden or []), "min_score": min_score, "time": time}


SCENARIOS = []
# 10 core scenarios x 5 variants = 50 regression scenarios.
cores = [
    ("hot-study", 32, 82, "study", "белая футболка джинсы кроссовки clean casual", "indoor", "clean", FRESH, HEAVY, "day"),
    ("hot-active", 33, 76, "active", "футболка шорты кроссовки спорт", "outdoor", "clean", FRESH, HEAVY, "day"),
    ("cold-restaurant", 2, 48, "restaurant", "пальто свитер темные брюки smart casual", "indoor", "expensive", COLD | FORMAL, set(), "evening"),
    ("cool-date", 15, 58, "date", "черная рубашка серые брюки smart casual", "close_distance", "sexy", DATE, {"9PM Elixir"}, "evening"),
    ("rain-meeting", 11, 78, "meeting", "рубашка пальто темные брюки smart casual", "indoor", "expensive", FORMAL | {"Imagination"}, set(), "day"),
    ("morning-study", 18, 50, "study", "светлая рубашка джинсы clean casual", "indoor", "clean", FRESH, {"Tobacco Vanille"}, "morning"),
    ("night-club", 17, 60, "club", "черная кожаная куртка джинсы streetwear", "club", "noticeable", {"9PM Night Out", "9PM Elixir", "The Most Wanted Parfum", "9PM"}, set(), "night"),
    ("small-room", 19, 55, "casual", "серый свитер джинсы casual", "small_room", "calm", {"Oud Wood", "Imagination", "Rare Reef", "Fakhar Black"}, {"9PM Elixir"}, "evening"),
    ("formal-meeting", 16, 52, "meeting", "черный пиджак белая рубашка брюки formal", "indoor", "expensive", FORMAL, set(), "day"),
    ("summer-walk", 27, 48, "walk", "льняная белая рубашка светлые брюки кроссовки", "outdoor", "clean", FRESH, {"Tobacco Vanille", "Khamrah"}, "day"),
]
for base_name, temp, humidity, event, outfit, circ, effect, strong, forbidden, tod in cores:
    for variant in range(5):
        SCENARIOS.append(scenario(
            f"{base_name}-{variant}", temp + (variant - 2) * 0.5, max(20, min(95, humidity + (variant - 2) * 2)), event, outfit,
            circ, effect, strong, forbidden, 42, rain=0.8 if "rain" in base_name else 0, cloud=85 if "rain" in base_name else 40,
            wind=22 if variant == 4 and circ == "outdoor" else 5, time=tod,
        ))


@pytest.mark.parametrize("case", SCENARIOS, ids=[c["name"] for c in SCENARIOS])
def test_regression_scenarios(case):
    situation = build_situation(event=case["event"], outfit_text=case["outfit"], circumstance=case["circumstance"], effect=case["effect"], weather=case["weather"], manual_time=case["time"], manual_season="auto", latitude=42)
    top = recommend_situation(situation, 3)
    assert len(top) == 3
    assert len({x.name for x in top}) == 3
    assert top[0].score >= case["min_score"]
    assert any(x.name in case["strong"] for x in top)
    assert top[0].name not in case["forbidden"]
    assert all(0 <= x.score <= 100 for x in top)
    assert all(0 <= x.confidence <= 100 for x in top)


def test_extreme_humid_heat_hard_constraints():
    s = build_situation(event="active", outfit_text="футболка шорты спорт", circumstance="outdoor", effect="clean", weather=weather(33, 85), manual_time="day", latitude=42)
    for name in ("Tobacco Vanille", "Khamrah"):
        r = score_perfume(find_perfume(name), s)
        assert r.hard_warnings
        assert r.score < 30


def test_fresh_not_penalized_for_missing_old_occasion_tag():
    s = build_situation(event="work", outfit_text="рубашка джинсы clean casual", circumstance="indoor", effect="clean", weather=weather(21, 50), manual_time="day", latitude=42)
    r = score_perfume(find_perfume("Imagination"), s)
    assert r.breakdown.event_score >= 60
    assert r.score >= 55


def test_diversity_roles_and_no_duplicates():
    s = build_situation(event="date", outfit_text="черная рубашка smart casual", circumstance="close_distance", effect="sexy", weather=weather(15, 55, is_day=False), manual_time="evening", latitude=42)
    top = recommend_situation(s, 3)
    assert [x.role for x in top] == ["Лучший выбор", "Безопасный вариант", "Более выразительный вариант"]
    assert len({x.name for x in top}) == 3


def test_auto_time_categories():
    assert infer_time_of_day(datetime(2026, 1, 1, 8)) == "morning"
    assert infer_time_of_day(datetime(2026, 1, 1, 14)) == "day"
    assert infer_time_of_day(datetime(2026, 1, 1, 19)) == "evening"
    assert infer_time_of_day(datetime(2026, 1, 1, 23)) == "night"


def test_auto_season_hemispheres():
    assert infer_season(datetime(2026, 7, 1), 42) == "summer"
    assert infer_season(datetime(2026, 7, 1), -33) == "winter"
    assert infer_season(datetime(2026, 1, 1), 42) == "winter"
    assert infer_season(datetime(2026, 1, 1), -33) == "summer"


def test_forecast_selection_nearest_hour():
    times = ["2026-08-24T18:00", "2026-08-24T19:00", "2026-08-24T20:00"]
    assert _closest_hour_index(times, datetime(2026, 8, 24, 19, 20)) == 1
    assert _closest_hour_index(times, datetime(2026, 8, 24, 19, 50)) == 2


def test_outfit_parser_structured():
    p = parse_outfit_profile("Черная кожаная куртка, белая футболка, серые джинсы и белые кроссовки, streetwear oversize")
    assert "leather" in p.materials
    assert p.top_type == "tshirt"
    assert p.bottom_type == "jeans"
    assert p.shoes_type == "sneakers"
    assert "streetwear" in p.style
    assert p.fit == "oversize"
    assert {"black", "white", "grey"}.issubset(set(p.colors))


def test_curated_pair_bonus_and_direction():
    s = build_situation(event="date", outfit_text="черная рубашка smart casual", circumstance="close_distance", effect="sexy", weather=weather(15, 55, is_day=False), manual_time="evening", latitude=42)
    r = analyze_pair_situation(find_perfume("Oud Wood"), find_perfume("Lost Cherry"), s)
    assert r.curated is True
    assert r.application_order == ["Oud Wood", "Lost Cherry"]
    assert 0 <= r.score <= 100


def test_curated_heavy_pair_loses_in_hot_humid_weather():
    hot = build_situation(event="restaurant", outfit_text="рубашка smart casual", circumstance="indoor", effect="expensive", weather=weather(33, 82), manual_time="day", latitude=42)
    r = analyze_pair_situation(find_perfume("Tobacco Vanille"), find_perfume("Oud Wood"), hot)
    assert r.curated is True
    assert r.warnings
    assert r.score < 70


def test_layering_score_ranges_and_no_duplicate_pairs():
    s = build_situation(event="restaurant", outfit_text="рубашка smart casual", circumstance="indoor", effect="expensive", weather=weather(12, 55, is_day=False), manual_time="evening", latitude=42)
    pairs = recommend_layering_situation(s, 10)
    keys = [{x.base_name, x.top_name} for x in pairs]
    assert all(0 <= x.score <= 100 and 0 <= x.confidence <= 100 for x in pairs)
    assert len({tuple(sorted(k)) for k in keys}) == len(keys)


def test_database_validator():
    assert validate_perfumes(PERFUMES, PRESET_LAYERING_PAIRS) == []


def test_personal_feedback_and_recent_wear_penalty():
    from app.services.personalization import build_personal_snapshot
    now = datetime.now().astimezone()
    history = [{"perfume": "Oud Wood", "timestamp": now.isoformat(), "event": "restaurant", "circumstance": "indoor", "rating": "excellent", "feedback_tags": ["repeat"]}]
    snapshot = build_personal_snapshot(history, "diversity", now)
    assert snapshot["adjustments"]["Oud Wood"] > 0
    assert snapshot["recent_penalties"]["Oud Wood"] > 0


def test_repeat_favorites_has_lower_recent_penalty():
    from app.services.personalization import build_personal_snapshot
    now = datetime.now().astimezone()
    h = [{"perfume": "Aventus", "timestamp": now.isoformat(), "event": "meeting", "circumstance": "indoor", "rating": "excellent", "feedback_tags": []}]
    diversity = build_personal_snapshot(h, "diversity", now)
    favorites = build_personal_snapshot(h, "favorites", now)
    assert diversity["recent_penalties"]["Aventus"] > favorites["recent_penalties"]["Aventus"]


def test_free_text_parser():
    from app.services.situation_parser import parse_free_text
    data = parse_free_text("Сегодня вечером ресторан, около 18°C, черная рубашка, серые брюки, в помещении, хочу пахнуть дорого")
    assert data["event"] == "restaurant"
    assert data["circumstance"] == "indoor"
    assert data["effect"] == "expensive"
    assert data["temperature"] == 18
    assert data["time_of_day"] == "evening"


def test_spray_engine_reduces_load_small_room():
    from app.models.perfume import build_perfume_profile
    from app.services.spray_advisor import recommend_sprays
    s = build_situation(event="casual", outfit_text="casual", circumstance="small_room", effect="any", weather=weather(24, 75), manual_time="evening", latitude=42)
    profile = build_perfume_profile(find_perfume("9PM Elixir"))
    advice = recommend_sprays(profile, s)
    assert 1 <= advice.count <= profile.base_sprays_max


def test_deterministic_same_input_same_output():
    s = build_situation(event="restaurant", outfit_text="рубашка smart casual", circumstance="indoor", effect="expensive", weather=weather(12, 55), manual_time="evening", latitude=42)
    a = [(x.name, x.score) for x in recommend_situation(s, 10, diversity=False)]
    b = [(x.name, x.score) for x in recommend_situation(s, 10, diversity=False)]
    assert a == b

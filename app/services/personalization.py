from __future__ import annotations

import math
from datetime import datetime, timezone

from app.services.scoring_config import FEEDBACK_WEIGHTS, PERSONAL_DECAY_DAYS, PERSONAL_MAX_ADJUSTMENT, RECENT_WEAR_PENALTIES


def _parse_time(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def build_personal_snapshot(history: list[dict] | None, preference_mode: str = "diversity", now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    history = history or []
    per_perfume: dict[str, float] = {}
    last_wear_days: dict[str, int] = {}
    context_strength: dict[str, dict[str, float]] = {}

    for item in history:
        names = []
        if item.get("perfume"):
            names.append(str(item["perfume"]))
        names.extend(str(x) for x in (item.get("layering") or []))
        when = _parse_time(item.get("timestamp"))
        age_days = max(0.0, (now - when).total_seconds() / 86400) if when else PERSONAL_DECAY_DAYS
        decay = math.exp(-age_days / PERSONAL_DECAY_DAYS)
        signal = FEEDBACK_WEIGHTS.get(str(item.get("rating", "normal")), 0.0)
        for tag in item.get("feedback_tags") or []:
            signal += FEEDBACK_WEIGHTS.get(str(tag), 0.0)
        for name in names:
            per_perfume[name] = per_perfume.get(name, 0.0) + signal * decay
            if when:
                days = int(age_days)
                last_wear_days[name] = min(days, last_wear_days.get(name, 10_000))
            key = f"{item.get('circumstance','')}|{item.get('event','')}"
            context_strength.setdefault(name, {})[key] = context_strength.setdefault(name, {}).get(key, 0.0) + signal * decay

    for name in list(per_perfume):
        per_perfume[name] = max(-PERSONAL_MAX_ADJUSTMENT, min(PERSONAL_MAX_ADJUSTMENT, per_perfume[name] * 3.0))

    penalties = RECENT_WEAR_PENALTIES.get(preference_mode, RECENT_WEAR_PENALTIES["diversity"])
    recent = {name: penalties.get(days, 0.0) for name, days in last_wear_days.items()}
    return {"adjustments": per_perfume, "recent_penalties": recent, "context": context_strength, "history_count": len(history), "mode": preference_mode}


def personal_adjustment(perfume_name: str, situation, snapshot: dict | None) -> tuple[float, float, list[str]]:
    if not snapshot:
        return 50.0, 0.0, []
    adjustment = float(snapshot.get("adjustments", {}).get(perfume_name, 0.0))
    context_key = f"{situation.circumstance}|{situation.event}"
    contextual = float(snapshot.get("context", {}).get(perfume_name, {}).get(context_key, 0.0))
    adjustment += max(-4.0, min(4.0, contextual * 1.2))
    recent_penalty = float(snapshot.get("recent_penalties", {}).get(perfume_name, 0.0))
    reasons = []
    if adjustment >= 2.0: reasons.append("личная история поддерживает этот аромат")
    elif adjustment <= -2.0: reasons.append("по прошлому опыту в похожих условиях есть риск")
    if recent_penalty: reasons.append("недавно уже носился")
    return max(0.0, min(100.0, 50.0 + adjustment * 2.0)), recent_penalty, reasons

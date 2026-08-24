from __future__ import annotations

import re

from app.models.outfit import OutfitProfile

COLOR_PATTERNS = {
    "black": r"черн|чёрн|black", "white": r"бел|white", "grey": r"сер|grey|gray", "brown": r"корич|brown",
    "beige": r"беж|beige", "blue": r"голуб|син|navy|blue", "green": r"зелен|зелён|green",
    "burgundy": r"бордов|burgundy", "red": r"красн|red", "cream": r"крем|cream", "khaki": r"хаки|khaki",
}
GARMENT_PATTERNS = {
    "shirt": r"рубашк|shirt", "polo": r"поло|polo", "tshirt": r"футболк|t[- ]?shirt|tee", "hoodie": r"худи|hoodie",
    "sweater": r"свитер|джемпер|sweater", "knit": r"трикотаж|knit", "jeans": r"джинс|jeans",
    "trousers": r"брюк|штаны|trousers|pants", "shorts": r"шорт|shorts", "sneakers": r"кроссов|sneakers",
    "boots": r"ботинк|boots", "loafers": r"лофер|loafers", "shoes": r"туфл|shoes", "jacket": r"куртк|jacket",
    "coat": r"пальто|coat", "blazer": r"пиджак|blazer", "leather_jacket": r"кожан(?:ая|ой)?\s+куртк|кожанк|leather jacket",
}
MATERIAL_PATTERNS = {
    "leather": r"кожан|кожа|leather", "denim": r"деним|джинсов|denim", "wool": r"шерст|wool",
    "cotton": r"хлоп|cotton", "linen": r"л[её]н|linen", "knit": r"трикотаж|вязк|knit", "synthetic": r"полиэстер|нейлон|synthetic",
}
STYLE_PATTERNS = {
    "smart_casual": r"smart\s*casual|смарт\s*кэжуал|смарт", "business_casual": r"business\s*casual|делов.*кэжуал",
    "formal": r"строг|formal|костюм|галстук", "sport": r"спорт|sport|athleisure", "streetwear": r"streetwear|стрит|оверсайз|oversize",
    "clean_casual": r"clean\s*casual|чист.*кэжуал|минимал", "casual": r"casual|кэжуал",
}
FIT_PATTERNS = {"oversize": r"оверсайз|oversize", "slim": r"облега|slim|skinny", "regular": r"regular|обычн.*посад"}


def _matches(text: str, patterns: dict[str, str]) -> list[str]:
    return [name for name, pattern in patterns.items() if re.search(pattern, text, flags=re.I)]


def _nearest_color(text: str, garment_pattern: str) -> str | None:
    # Capture a small context around the garment, then resolve the first color there.
    match = re.search(garment_pattern, text, flags=re.I)
    if not match:
        return None
    start, end = max(0, match.start() - 28), min(len(text), match.end() + 18)
    context = text[start:end]
    colors = _matches(context, COLOR_PATTERNS)
    return colors[0] if colors else None


def parse_outfit_profile(text: str) -> OutfitProfile:
    raw = (text or "").strip()
    normalized = raw.lower()
    colors = _matches(normalized, COLOR_PATTERNS)
    garments = _matches(normalized, GARMENT_PATTERNS)
    materials = _matches(normalized, MATERIAL_PATTERNS)
    styles = _matches(normalized, STYLE_PATTERNS)
    fits = _matches(normalized, FIT_PATTERNS)

    if not styles:
        if any(g in garments for g in ("shirt", "polo", "blazer", "loafers", "shoes")):
            styles = ["smart_casual"]
        elif any(g in garments for g in ("hoodie", "sneakers")) and "oversize" in fits:
            styles = ["streetwear"]
        else:
            styles = ["casual"]
    if "formal" in styles:
        formality = 4.7
    elif "business_casual" in styles:
        formality = 4.0
    elif "smart_casual" in styles:
        formality = 3.4
    elif "clean_casual" in styles:
        formality = 2.8
    elif "streetwear" in styles or "sport" in styles:
        formality = 1.4
    else:
        formality = 2.0

    dark_colors = {"black", "burgundy", "brown"}
    light_colors = {"white", "beige", "cream"}
    if colors and set(colors) <= dark_colors:
        palette = "dark"
    elif colors and set(colors) <= light_colors:
        palette = "light"
    elif len(set(colors)) == 1:
        palette = "monochrome"
    else:
        palette = "neutral"

    if any(g in garments for g in ("coat", "sweater", "boots")) or "wool" in materials:
        weather_weight = "heavy"
    elif any(g in garments for g in ("shorts", "tshirt")) or "linen" in materials:
        weather_weight = "light"
    else:
        weather_weight = "medium"

    top_type = next((g for g in ("shirt", "polo", "tshirt", "hoodie", "sweater", "knit") if g in garments), None)
    bottom_type = next((g for g in ("jeans", "trousers", "shorts") if g in garments), None)
    shoes_type = next((g for g in ("sneakers", "boots", "loafers", "shoes") if g in garments), None)
    outerwear = [g for g in ("leather_jacket", "jacket", "coat", "blazer") if g in garments]

    legacy = set(colors) | set(garments) | set(materials) | set(styles)
    if palette in {"dark", "light", "monochrome"}:
        legacy.add(palette)
    if "leather_jacket" in garments:
        legacy.update({"leather", "jacket", "dark"})
    if "smart_casual" in styles:
        legacy.add("smart_casual")
    if "sport" in styles:
        legacy.add("sport_casual")

    return OutfitProfile(
        top_type=top_type,
        top_color=_nearest_color(normalized, GARMENT_PATTERNS.get(top_type, r"$^")) if top_type else None,
        bottom_type=bottom_type,
        bottom_color=_nearest_color(normalized, GARMENT_PATTERNS.get(bottom_type, r"$^")) if bottom_type else None,
        shoes_type=shoes_type,
        shoes_color=_nearest_color(normalized, GARMENT_PATTERNS.get(shoes_type, r"$^")) if shoes_type else None,
        outerwear=outerwear,
        materials=materials,
        colors=colors,
        palette=palette,
        style=styles,
        formality=formality,
        fit=fits[0] if fits else None,
        weather_weight=weather_weight,
        garments=garments,
        legacy_tags=sorted(legacy),
        raw_text=raw,
    )


def parse_outfit(text: str) -> set[str]:
    """Backward-compatible adapter for old recommender/handlers."""
    return set(parse_outfit_profile(text).legacy_tags)

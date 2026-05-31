import re


KEYWORD_TAGS: dict[str, list[str]] = {
    r"\bчерн|black": ["black", "dark"],
    r"\bтемн|dark": ["dark"],
    r"\bбел|white": ["white", "light"],
    r"\bсветл|light": ["light"],
    r"\bсер|grey|gray": ["grey"],
    r"\bкорич|brown": ["brown"],
    r"\bбеж|beige": ["beige", "light"],
    r"\bголуб|blue": ["blue", "light"],
    r"\bсин|navy": ["blue"],
    r"\bзелен|green": ["green"],
    r"\bбордов|burgundy": ["burgundy", "dark"],

    r"кожан|leather": ["leather"],
    r"куртк|jacket": ["jacket", "light_jacket"],
    r"пальто|coat": ["coat", "formal"],
    r"рубашк|shirt": ["shirt", "smart_casual"],
    r"поло|polo": ["polo", "smart_casual"],
    r"свитер|sweater": ["sweater", "knitwear"],
    r"трикотаж|knit": ["knitwear"],
    r"худи|hoodie": ["hoodie", "streetwear", "casual"],
    r"футболк|t[- ]?shirt|tee": ["tshirt", "casual"],
    r"джинс|jeans": ["jeans", "casual"],
    r"широк|wide": ["wide_jeans", "streetwear"],
    r"кроссов|sneakers": ["sneakers", "casual"],
    r"ботинк|boots": ["boots"],
    r"шорт|shorts": ["shorts", "light"],
    r"часы|watch": ["watch"],
    r"оверсайз|oversize": ["oversize", "streetwear"],

    r"streetwear|стрит": ["streetwear"],
    r"smart casual|смарт": ["smart_casual"],
    r"casual|кэжуал": ["casual"],
    r"спорт|sport": ["sport", "sport_casual"],
    r"строг|formal": ["formal", "smart_casual"],
    r"минимал|minimal": ["minimalism"],
    r"дорог|luxury|premium": ["formal", "minimalism"],
}


def parse_outfit(text: str) -> set[str]:
    normalized = text.lower().strip()
    tags: set[str] = set()

    for pattern, pattern_tags in KEYWORD_TAGS.items():
        if re.search(pattern, normalized):
            tags.update(pattern_tags)

    if not tags:
        tags.add("casual")

    return tags

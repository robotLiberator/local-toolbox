"""Conservative, offline cleanup; never paraphrase or deduplicate whole sentences."""
import re


# A small whitelist avoids changing normal reduplicated words (看看、慢慢、人人).
_WORDS = (
    "我们", "你们", "他们", "她们", "它们", "这个", "那个", "就是",
    "然后", "所以", "因为", "但是", "而且", "我", "你", "他", "她", "它",
)
_REPEATS = tuple(
    re.compile(r"(" + re.escape(word) + r")(?:[\s，,、]*" + re.escape(word) + r")+")
    for word in _WORDS
)


def clean_stutters(text: str) -> str:
    """Collapse adjacent whitelisted repeats, leaving emphasis and other words alone.

    Full stops and other sentence boundaries are deliberately not crossed.
    Standalone fillers are retained: 那个 can refer to something, not just hesitation.
    """
    for pattern in _REPEATS:
        text = pattern.sub(r"\1", text)
    return text

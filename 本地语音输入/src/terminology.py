"""Deterministic, context-aware terminology repair; no network or guessing."""
import json
import re
import shutil
from pathlib import Path

from paths import APP_ROOT, user_file


def dictionary_file():
    path = user_file('terminology.json')
    if not path.exists():
        shutil.copyfile(APP_ROOT / 'terminology.json', path)
    return path


def load_enabled():
    try:
        return json.loads(user_file('terminology_settings.json').read_text(encoding='utf-8')).get('enabled', True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def save_enabled(enabled):
    user_file('terminology_settings.json').write_text(json.dumps({'enabled': bool(enabled)}), encoding='utf-8')


def correct_terms(text, dictionary=None):
    """Literal aliases only; ambiguous English needs nearby Chinese tech context.

    A corrupt custom dictionary fails open to the unchanged transcript.
    Reload per utterance so saved edits apply without restarting the app.
    """
    if not text:
        return text
    try:
        data = dictionary if dictionary is not None else json.loads(dictionary_file().read_text(encoding='utf-8-sig'))
        contexts = data['technical_context']
        entries = data['terms']
        if not isinstance(contexts, list) or not all(isinstance(x, str) and x for x in contexts):
            return text
        if not isinstance(entries, list):
            return text
        rules = []
        for entry in entries:
            canonical = entry['canonical']
            if not isinstance(canonical, str) or not canonical or len(canonical) > 80:
                return text
            for field, conditional in [('aliases', False), ('context_aliases', True)]:
                aliases = entry.get(field, [])
                if not isinstance(aliases, list) or not all(isinstance(x, str) and x and len(x) <= 80 for x in aliases):
                    return text
                for alias in aliases:
                    # Chinese may touch the term; embedded English words must not match.
                    pattern = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(alias) + r'(?![A-Za-z0-9_])', re.IGNORECASE)
                    rules.append((len(alias), pattern, canonical, conditional))
        # Match once on the original text: replacements cannot cascade into other rules.
        matches = []
        for length, pattern, canonical, conditional in sorted(rules, key=lambda r: -r[0]):
            for match in pattern.finditer(text):
                if conditional:
                    before = re.split(r'[。！？.!?\n]', text[:match.start()])[-1][-24:]
                    after = re.split(r'[。！？.!?\n]', text[match.end():])[0][:24]
                    nearby = before + after
                    english_prefix = re.search(r'\b(?:I|you|we|they|he|she|to|should|must|will|can)\s+(?:usually\s+|always\s+|not\s+)?$', before, re.IGNORECASE)
                    if english_prefix or not re.search(r'[\u4e00-\u9fff]', nearby) or not any(hint.casefold() in nearby.casefold() for hint in contexts):
                        continue
                if any(match.start() < end and match.end() > start for start, end, _ in matches):
                    continue
                matches.append((match.start(), match.end(), canonical))
        for start, end, canonical in sorted(matches, reverse=True):
            text = text[:start] + canonical + text[end:]
        return text
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return text

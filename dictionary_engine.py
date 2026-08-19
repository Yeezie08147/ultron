"""
dictionary_engine.py — ULTRON Lexical & Word Definition Matrix.

Capabilities:
- Real-time English word definitions, part of speech, and usage examples via free dictionary API + Wikipedia fallback
"""

import httpx
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.dictionary")


def define_word(word: str) -> Dict[str, Any]:
    """Fetch definition and part of speech for a word."""
    clean_word = word.lower().strip().replace("define ", "").replace("what does ", "").replace(" mean", "").strip()
    if not clean_word:
        return {"success": False, "message": "Specify a word to define, sir."}

    # 1. Primary Dictionary API
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{clean_word}"
    try:
        with httpx.Client(verify=False, timeout=4.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()[0]
                meanings = data.get("meanings", [])
                if meanings:
                    first_meaning = meanings[0]
                    part_of_speech = first_meaning.get("partOfSpeech", "term")
                    definition = first_meaning["definitions"][0].get("definition", "")
                    return {
                        "success": True,
                        "word": clean_word,
                        "definition": definition,
                        "message": f"{clean_word.capitalize()} ({part_of_speech}): {definition}"
                    }
    except Exception:
        pass

    # 2. Wikipedia Summary Fallback
    try:
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_word}"
        with httpx.Client(verify=False, timeout=4.0) as client:
            w_resp = client.get(wiki_url)
            if w_resp.status_code == 200:
                extract = w_resp.json().get("extract", "")
                if extract:
                    first_sentence = extract.split(". ")[0] + "."
                    return {
                        "success": True,
                        "word": clean_word,
                        "definition": first_sentence,
                        "message": f"{clean_word.capitalize()}: {first_sentence}"
                    }
    except Exception:
        pass

    return {
        "success": False,
        "message": f"Unable to retrieve definition for {clean_word}, sir."
    }

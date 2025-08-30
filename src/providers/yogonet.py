from __future__ import annotations

from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

from .base import Provider, parse_first_five_numbers_0_36_from_text


class YogonetProvider(Provider):
    name = "Yogonet"
    URL = (
        "https://www.yogonet.com/latinoamerica/play/resultados/loterias/"
        "buenos-aires/loto-5-plus/"
    )

    def fetch(self) -> Tuple[List[int], str]:
        headers = {
            "User-Agent": "Loto5PlusChecker/1.0 (+https://example.local)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(self.URL, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try structured cues first (common number list patterns)
        candidates: List[int] = []
        for selector in [
            "li",
            "span",
            "div",
        ]:
            elems = soup.select(selector)
            text = " ".join(e.get_text(" ", strip=True) for e in elems)
            try:
                candidates = parse_first_five_numbers_0_36_from_text(text)
                break
            except Exception:
                continue

        if not candidates:
            # Fallback: whole page text
            text = soup.get_text(" ", strip=True)
            candidates = parse_first_five_numbers_0_36_from_text(text)

        return candidates, self.name


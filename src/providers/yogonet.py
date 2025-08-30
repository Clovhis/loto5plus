from __future__ import annotations

from typing import List

import requests
from bs4 import BeautifulSoup

from .base import (
    Provider,
    ProviderResult,
    parse_first_five_numbers_0_36_from_text,
    try_parse_draw_metadata,
)


class YogonetProvider(Provider):
    name = "Yogonet"
    URL = (
        "https://www.yogonet.com/latinoamerica/play/resultados/loterias/"
        "buenos-aires/loto-5-plus/"
    )

    def fetch(self) -> ProviderResult:
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

        # Metadata
        page_text = soup.get_text(" ", strip=True)
        draw_num, last_dt, next_dt = try_parse_draw_metadata(page_text)

        return ProviderResult(
            numbers=candidates,
            label=self.name,
            last_draw_number=draw_num,
            last_draw_datetime=last_dt,
            next_draw_datetime=next_dt,
        )

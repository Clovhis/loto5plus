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


class SaltaProvider(Provider):
    name = "Lotería de Salta"
    URL = "https://www.loteriadesalta.com/extractos-oficiales/loto-5/"

    def fetch(self) -> ProviderResult:
        headers = {
            "User-Agent": "Loto5PlusChecker/1.0 (+https://example.local)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(self.URL, headers=headers, timeout=6)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Many official sites embed results in tables or blocks; use robust text scan
        text = soup.get_text(" ", strip=True)
        numbers = parse_first_five_numbers_0_36_from_text(text)
        draw_num, last_dt, next_dt = try_parse_draw_metadata(text)
        return ProviderResult(
            numbers=numbers,
            label=self.name,
            last_draw_number=draw_num,
            last_draw_datetime=last_dt,
            next_draw_datetime=next_dt,
        )

from __future__ import annotations

from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

from .base import Provider, parse_first_five_numbers_0_36_from_text


class SaltaProvider(Provider):
    name = "Lotería de Salta"
    URL = "https://www.loteriadesalta.com/extractos-oficiales/loto-5/"

    def fetch(self) -> Tuple[List[int], str]:
        headers = {
            "User-Agent": "Loto5PlusChecker/1.0 (+https://example.local)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(self.URL, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Many official sites embed results in tables or blocks; use robust text scan
        text = soup.get_text(" ", strip=True)
        numbers = parse_first_five_numbers_0_36_from_text(text)
        return numbers, self.name


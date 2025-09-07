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


class TujugadaProvider(Provider):
    name = "TuJugada"
    # Try multiple plausible endpoints used by TuJugada for Loto 5 Plus
    CANDIDATE_URLS = [
        "https://www.tujugada.com/loterias/loto-5-plus",
        "https://www.tujugada.com/loterias/loto-5",
        "https://www.tujugada.com.ar/loterias/loto-5-plus",
        "https://www.tujugada.com.ar/loterias/loto-5",
    ]

    def fetch(self) -> ProviderResult:
        headers = {
            "User-Agent": "Loto5PlusChecker/1.0 (+https://example.local)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        last_exc: Exception | None = None
        for url in self.CANDIDATE_URLS:
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Robust text-first parsing due to varied markup
                page_text = soup.get_text(" ", strip=True)
                numbers = parse_first_five_numbers_0_36_from_text(page_text)
                draw_num, last_dt, next_dt = try_parse_draw_metadata(page_text)

                return ProviderResult(
                    numbers=numbers,
                    label=f"{self.name} ({url})",
                    last_draw_number=draw_num,
                    last_draw_datetime=last_dt,
                    next_draw_datetime=next_dt,
                )
            except Exception as e:  # noqa: BLE001
                last_exc = e
                continue

        # If none of the candidates worked, raise last error
        raise (last_exc or RuntimeError("No se pudo obtener TuJugada"))


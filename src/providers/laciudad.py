from __future__ import annotations

from typing import List, Optional

import re
import requests
from bs4 import BeautifulSoup

from .base import Provider, ProviderResult


class LaciudadProvider(Provider):
    name = "Lotería de la Ciudad"
    URL = "https://loto5.loteriadelaciudad.gob.ar/"

    def fetch(self) -> ProviderResult:
        headers = {
            "User-Agent": "Loto5PlusChecker/1.0 (+https://example.local)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(self.URL, headers=headers, timeout=6)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) Try to extract the five drawn numbers by DOM scanning
        candidates: list[tuple[int, int]] = []  # (idx, number)
        idx = 0
        for el in soup.find_all(["span", "div", "li", "p", "strong"]):
            text = el.get_text("", strip=True)
            if not text or len(text) > 2:
                idx += 1
                continue
            if re.fullmatch(r"\d{1,2}", text):
                n = int(text)
                if 0 <= n <= 36:
                    candidates.append((idx, n))
            idx += 1

        numbers: List[int] = []
        if candidates:
            # Find the first compact cluster of 5 unique numbers
            for i in range(len(candidates)):
                seen: list[int] = []
                left_idx = candidates[i][0]
                for j in range(i, len(candidates)):
                    _, n = candidates[j]
                    if n not in seen:
                        seen.append(n)
                    if len(seen) == 5:
                        right_idx = candidates[j][0]
                        # Require compactness in DOM order to avoid picking date pieces
                        if right_idx - left_idx <= 30:
                            numbers = seen
                        break
                if numbers:
                    break

        if not numbers:
            # Fallback: attempt inline pattern like "n1 - n2 - n3 - n4 - n5"
            page_text = soup.get_text("\n", strip=True)
            m = re.search(r"\b(\d{1,2})\s*[-,]\s*(\d{1,2})\s*[-,]\s*(\d{1,2})\s*[-,]\s*(\d{1,2})\s*[-,]\s*(\d{1,2})\b", page_text)
            if m:
                nums = [int(m.group(k)) for k in range(1, 6)]
                if all(0 <= x <= 36 for x in nums) and len(set(nums)) == 5:
                    numbers = nums

        if not numbers:
            raise ValueError("No se pudieron obtener los 5 números del sitio oficial.")

        # 2) Draw number and date from explicit label "Fecha: dd/mm/yyyy - Sorteo: nnnn"
        page_text = soup.get_text("\n", strip=True)
        draw_num: Optional[int] = None
        last_date_text: Optional[str] = None
        m = re.search(r"Fecha:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*Sorteo:\s*(\d{2,6})", page_text, re.IGNORECASE)
        if m:
            last_date_text = m.group(1)
            try:
                draw_num = int(m.group(2))
            except Exception:
                draw_num = None
        else:
            # Fallbacks: try to find "Sorteo: nnnn" and a nearby date
            m2 = re.search(r"Sorteo:\s*(\d{2,6})", page_text, re.IGNORECASE)
            if m2:
                try:
                    draw_num = int(m2.group(1))
                except Exception:
                    draw_num = None
            d2 = re.search(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", page_text)
            if d2:
                last_date_text = d2.group(1)

        from datetime import datetime
        last_dt = None
        if last_date_text:
            for fmt in ("%d/%m/%Y", "%d/%m/%y"):
                try:
                    last_dt = datetime.strptime(last_date_text, fmt)
                    break
                except Exception:
                    continue

        # 3) Próximo sorteo jackpot: capture amount after the header
        jackpot_text: Optional[str] = None
        # Look for the header line then the first currency-like amount nearby
        header_match = re.search(r"POZO\s+ESTIMADO\s+PR[ÓO]XIMO\s+SORTEO", page_text, re.IGNORECASE)
        if header_match:
            tail = page_text[header_match.end():]
            mval = re.search(r"\$\s*[0-9.]+,\d{2}\.-", tail)
            if not mval:
                mval = re.search(r"\$\s*[0-9.]+(?:,\d{2})?", tail)
            if mval:
                jackpot_text = mval.group(0).strip()

        return ProviderResult(
            numbers=sorted(numbers),
            label=self.name,
            last_draw_number=draw_num,
            last_draw_datetime=last_dt,
            next_draw_datetime=None,
            next_jackpot_text=jackpot_text,
        )


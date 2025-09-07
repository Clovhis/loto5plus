from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ProviderResult:
    numbers: List[int]
    label: str
    last_draw_number: Optional[int] = None
    last_draw_datetime: Optional[datetime] = None
    next_draw_datetime: Optional[datetime] = None


class Provider(ABC):
    """Abstract provider for fetching latest Loto 5 Plus results.

    Implementations must return a tuple ([n1..n5], label) where the list
    contains exactly five unique integers in range 0-36 and label is a
    short string identifying the source.
    """

    name: str = ""

    @abstractmethod
    def fetch(self) -> ProviderResult:
        """Fetch latest results and metadata or raise an exception on failure."""
        raise NotImplementedError


def parse_first_five_numbers_0_36_from_text(text: str) -> List[int]:
    """Extract the first five unique numbers in [0, 36] from free text.

    This is a resilient fallback for heterogeneous pages. It iterates
    tokens in order and picks the first five unique ints in range.
    Raises ValueError if fewer than five numbers found.
    """
    import re

    tokens = re.findall(r"\b\d{1,2}\b", text)
    seen = set()
    result: List[int] = []
    for t in tokens:
        n = int(t)
        if 0 <= n <= 36 and n not in seen:
            result.append(n)
            seen.add(n)
            if len(result) == 5:
                break
    if len(result) != 5:
        raise ValueError("No se pudieron extraer 5 números válidos (0–36)")
    return result


def try_parse_draw_metadata(text: str) -> tuple[Optional[int], Optional[datetime], Optional[datetime]]:
    """Best-effort parse of draw number, last draw datetime and next draw datetime from text.

    Returns (last_draw_number, last_draw_datetime, next_draw_datetime). Any value can be None.
    """
    import re
    from datetime import datetime

    # Draw number e.g. "Sorteo N° 1234", "Sorteo Nro 1234", "Sorteo No 1234", "Sorteo #1234"
    num: Optional[int] = None
    m = re.search(r"Sorteo\s*(?:N[°ºo]?|Nro\.?|No\.?|#)?\s*(\d{2,6})", text, re.IGNORECASE)
    if m:
        try:
            num = int(m.group(1))
        except Exception:
            num = None

    # Helper to parse near markers (Último/Próximo sorteo, etc.)
    def find_dt_terms(around_terms: list[str]) -> Optional[datetime]:
        # Locate the first occurrence of any term and scan nearby text
        pattern = "|".join(rf"{t}" for t in around_terms)
        m0 = re.search(pattern, text, re.IGNORECASE)
        idx = m0.start() if m0 else -1
        span = text if idx == -1 else text[max(0, idx - 120) : idx + 280]

        # 1) Numeric date + time
        d = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", span)
        t = re.search(r"(\d{1,2}[:.]\d{2})\s*(?:hs|hs\.|h|hrs|hrs\.)?", span, re.IGNORECASE)
        if d and t:
            ds = d.group(1)
            ts = t.group(1).replace(".", ":")
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d-%m-%Y %H:%M", "%d-%m-%y %H:%M"):
                try:
                    return datetime.strptime(f"{ds} {ts}", fmt)
                except Exception:
                    continue

        # 2) Date only (numeric) — assume 00:00
        if d and not t:
            ds = d.group(1)
            for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
                try:
                    base = datetime.strptime(ds, fmt)
                    return base.replace(hour=0, minute=0)
                except Exception:
                    continue

        # 3) Spanish textual date (e.g., 6 de septiembre de 2025) + optional time
        month_map = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
            "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
            "noviembre": 11, "diciembre": 12,
        }
        mtxt = re.search(r"(\d{1,2})\s+de\s+([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})", span, re.IGNORECASE)
        if mtxt:
            day = int(mtxt.group(1))
            month_name = mtxt.group(2).lower()
            month = month_map.get(month_name)
            year = int(mtxt.group(3))
            if month:
                hhmm = re.search(r"(\d{1,2}[:.]\d{2})\s*(?:hs|hs\.|h|hrs|hrs\.)?", span, re.IGNORECASE)
                if hhmm:
                    hh, mm = hhmm.group(1).replace(".", ":").split(":")
                    return datetime(year, month, day, int(hh), int(mm))
                return datetime(year, month, day, 0, 0)

        # 4) Time only — attach today
        if t and not d:
            try:
                ts = t.group(1).replace(".", ":")
                today = datetime.today().strftime("%d/%m/%Y")
                return datetime.strptime(f"{today} {ts}", "%d/%m/%Y %H:%M")
            except Exception:
                pass
        return None

    last_dt = find_dt_terms(["último sorteo", "ultimo sorteo", "resultado", "resultado del sorteo"]) or None
    next_dt = find_dt_terms(["próximo sorteo", "proximo sorteo", "siguiente sorteo"]) or None

    return num, last_dt, next_dt


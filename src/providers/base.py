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
    # Additional metadata for official site
    next_jackpot_text: Optional[str] = None


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
    import unicodedata
    from datetime import datetime

    # Normalize text for matching terms (remove accents, lowercase)
    def normalize(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()

    text_norm = normalize(text)

    # Draw number: support multiple phrasings
    num: Optional[int] = None
    try:
        num_patterns = [
            r"\bsorteo\b\s*(?:n[°ºo]?\s*|nro\.?\s*|no\.?\s*|#\s*)?(\d{2,6})",
            r"(?:n[°º]?\s*de\s*sorteo|nro\.?\s*de\s*sorteo|numero\s*de\s*sorteo)\s*[:#-]?\s*(\d{2,6})",
            r"\bn[°º]?\s*[:#-]?\s*(\d{2,6})",
            r"\bsorteo\s*[:#-]?\s*(\d{2,6})",
        ]
        for pat in num_patterns:
            m = re.search(pat, text_norm, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                break
    except Exception:
        num = None

    # Helper: find datetime near any of the include terms, avoiding exclude terms when possible
    def find_dt_terms(terms_include: list[str], terms_exclude: list[str] | None = None) -> Optional[datetime]:
        terms_exclude = terms_exclude or []
        inc_pat = "|".join(re.escape(normalize(t)) for t in terms_include)
        exc_pat = "|".join(re.escape(normalize(t)) for t in terms_exclude) if terms_exclude else None

        candidates: list[tuple[int, datetime]] = []
        for m in re.finditer(inc_pat, text_norm):
            idx = m.start()
            span_norm = text_norm[max(0, idx - 160) : idx + 360]
            if exc_pat and re.search(exc_pat, span_norm):
                continue

            # 1) Numeric date + time
            d = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", span_norm)
            t = re.search(r"(\d{1,2})(?::|\.)(\d{2})\s*(?:hs|h|hrs|horas)?", span_norm)
            if d and t:
                ds = d.group(1)
                ts = f"{t.group(1)}:{t.group(2)}"
                for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d-%m-%Y %H:%M", "%d-%m-%y %H:%M"):
                    try:
                        candidates.append((idx, datetime.strptime(f"{ds} {ts}", fmt)))
                        break
                    except Exception:
                        continue
                if candidates:
                    continue

            # 2) Date only (numeric) — assume 00:00
            if d and not t:
                ds = d.group(1)
                for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
                    try:
                        base = datetime.strptime(ds, fmt)
                        candidates.append((idx, base.replace(hour=0, minute=0)))
                        break
                    except Exception:
                        continue
                if candidates:
                    continue

            # 3) Textual month (e.g., 6 de septiembre de 2025) + optional time
            month_map = {
                "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
                "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
                "noviembre": 11, "diciembre": 12,
            }
            mtxt = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", span_norm)
            if mtxt:
                day = int(mtxt.group(1))
                month = month_map.get(mtxt.group(2).lower())
                year = int(mtxt.group(3))
                if month:
                    hhmm = re.search(r"(\d{1,2})(?::|\.)(\d{2})\s*(?:hs|h|hrs|horas)?", span_norm)
                    if hhmm:
                        hh, mm = int(hhmm.group(1)), int(hhmm.group(2))
                        candidates.append((idx, datetime(year, month, day, hh, mm)))
                    else:
                        candidates.append((idx, datetime(year, month, day, 0, 0)))

        if not candidates:
            return None

        # Prefer the earliest index (closest to the include term)
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # Simple fallback: mimic earlier behavior (scan around single anchor term)
    def find_dt_simple(anchor: str) -> Optional[datetime]:
        idx = text_norm.find(normalize(anchor))
        if idx == -1:
            return None
        span_norm = text_norm[max(0, idx - 80) : idx + 180]
        d = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", span_norm)
        t = re.search(r"(\d{1,2}):(\d{2})", span_norm)
        if d and t:
            ds = d.group(1)
            ts = f"{t.group(1)}:{t.group(2)}"
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d-%m-%Y %H:%M", "%d-%m-%y %H:%M"):
                try:
                    return datetime.strptime(f"{ds} {ts}", fmt)
                except Exception:
                    continue
        if t and not d:
            try:
                today = datetime.today().strftime("%d/%m/%Y")
                ts = f"{t.group(1)}:{t.group(2)}"
                return datetime.strptime(f"{today} {ts}", "%d/%m/%Y %H:%M")
            except Exception:
                return None
        return None

    last_dt = (
        find_dt_terms(["último sorteo", "ultimo sorteo"])  # prefer explicit marker
        or find_dt_terms(["resultado", "resultado del sorteo"], terms_exclude=["próximo", "proximo", "siguiente"])  # avoid next markers
    ) or find_dt_simple("último sorteo") or find_dt_simple("resultado")

    next_dt = (
        find_dt_terms(["próximo sorteo", "proximo sorteo", "siguiente sorteo"])  # next markers
        or find_dt_terms(["próximo", "proximo", "siguiente", "cierra"])  # generic next/cutoff
    ) or find_dt_simple("próximo sorteo") or find_dt_simple("proximo sorteo")

    return num, last_dt, next_dt

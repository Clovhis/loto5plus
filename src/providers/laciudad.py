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

        # 1) Extract the five drawn numbers (robust clustering within same container)
        from collections import defaultdict
        Node = dict
        candidates: list[Node] = []  # {idx, n, el, root, score}
        for idx, el in enumerate(soup.find_all(["span", "div", "li", "p", "strong"])):
            txt = el.get_text("", strip=True)
            if not txt or not re.fullmatch(r"\d{1,2}", txt):
                continue
            n = int(txt)
            if not (0 <= n <= 36):
                continue
            # ascend to a stable small container
            root = el
            steps = 0
            while getattr(root, "parent", None) is not None and steps < 3:
                root = root.parent
                steps += 1
            cls_el = " ".join(el.get("class", []))
            cls_root = " ".join(getattr(root, "get", lambda *_: [])("class", []))
            cls = f"{cls_el} {cls_root}".strip()
            score = 0
            if re.search(r"bol|bola|ball|num|n[uú]mero|sorteo|result", cls, re.IGNORECASE):
                score += 2
            if len(txt) == 2 and txt.startswith("0"):
                score += 1
            candidates.append({"idx": idx, "n": n, "el": el, "root": root, "score": score})

        numbers: List[int] = []
        best_key = None
        if candidates:
            by_root: dict[int, list[Node]] = defaultdict(list)
            for node in candidates:
                by_root[id(node["root"])].append(node)

            def consider(arr: list[Node], extra_bonus: int = 0) -> None:
                nonlocal numbers, best_key
                arr = sorted(arr, key=lambda x: x["idx"])
                for i in range(len(arr)):
                    uniq: list[Node] = []
                    seen = set()
                    for j in range(i, len(arr)):
                        n = arr[j]["n"]
                        if n not in seen:
                            seen.add(n)
                            uniq.append(arr[j])
                        if len(uniq) == 5:
                            span_w = uniq[-1]["idx"] - uniq[0]["idx"]
                            score = sum(x["score"] for x in uniq) + extra_bonus
                            if span_w <= 100:
                                score += 2
                            key = (score, -span_w, -sum(x["idx"] for x in uniq))
                            if best_key is None or key > best_key:
                                best_key = key
                                numbers = [x["n"] for x in uniq]
                            break

            # Prefer clusters within the same container
            for _, arr in by_root.items():
                consider(arr, extra_bonus=5)
            if not numbers:
                consider(candidates, extra_bonus=0)

        if not numbers:
            # Fallback: look near the legend "Fecha: .. - Sorteo: .."
            page_text = soup.get_text("\n", strip=True)
            anchor = re.search(r"Fecha:\s*\d{1,2}/\d{1,2}/\d{2,4}\s*-\s*Sorteo:\s*\d{2,6}", page_text, re.IGNORECASE)
            tail = page_text[anchor.end(): anchor.end() + 800] if anchor else page_text
            m = re.search(r"\b(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\b", tail)
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
        header_match = re.search(r"POZO\s+ESTIMADO\s+PR[ÓO]XIMO\s+SORTEO", page_text, re.IGNORECASE)
        if header_match:
            tail2 = page_text[header_match.end():]
            mval = re.search(r"\$\s*[0-9.]+,\d{2}\.-", tail2)
            if not mval:
                mval = re.search(r"\$\s*[0-9.]+(?:,\d{2})?", tail2)
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


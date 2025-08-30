from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple


class Provider(ABC):
    """Abstract provider for fetching latest Loto 5 Plus results.

    Implementations must return a tuple ([n1..n5], label) where the list
    contains exactly five unique integers in range 0-36 and label is a
    short string identifying the source.
    """

    name: str = ""

    @abstractmethod
    def fetch(self) -> Tuple[List[int], str]:
        """Fetch latest results or raise an exception on failure."""
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


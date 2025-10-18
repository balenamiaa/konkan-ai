from typing import List

class Meld:
    mask_hi: int
    mask_lo: int
    points: int
    jokers_used: int
    kind: int

class CoverResult:
    melds: List[Meld]
    covered_cards: int
    total_points: int
    used_jokers: int

def enumerate_melds(mask_hi: int, mask_lo: int) -> List[Meld]: ...
def best_cover(mask_hi: int, mask_lo: int, objective: int, threshold: int) -> CoverResult: ...

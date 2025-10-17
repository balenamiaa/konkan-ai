"""Core game state data structures for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from ._compat import np


@dataclass(slots=True)
class MeldOnTable:
    """Representation of a meld that is visible on the table."""

    mask_hi: np.uint64
    mask_lo: np.uint64
    owner: int
    has_joker: bool
    points: int
    is_four_set: bool


@dataclass(slots=True)
class PlayerPublic:
    """Public information tracked for each player."""

    came_down: bool
    table_points: int


@dataclass(slots=True)
class KonkanState:
    """Mutable game state used throughout determinization and search."""

    player_to_act: int
    turn_index: int
    deck: object
    deck_top: int
    trash: List[int]
    hands: List[object]
    table: List[MeldOnTable]
    public: List[PlayerPublic]
    highest_table_points: int
    first_player_has_discarded: bool

    def clone_shallow(self) -> "KonkanState":
        """Create a shallow copy of the state suitable for branching search."""

        return KonkanState(
            player_to_act=self.player_to_act,
            turn_index=self.turn_index,
            deck=self.deck.copy(),
            deck_top=self.deck_top,
            trash=list(self.trash),
            hands=[hand.copy() for hand in self.hands],
            table=list(self.table),
            public=[PlayerPublic(p.came_down, p.table_points) for p in self.public],
            highest_table_points=self.highest_table_points,
            first_player_has_discarded=self.first_player_has_discarded,
        )


def hand_mask(hand: Sequence[int]) -> tuple[np.uint64, np.uint64]:
    """Compute the (hi, lo) bitset mask for a player's hand."""

    mask_hi = np.uint64(0)
    mask_lo = np.uint64(0)
    for card_identifier in hand:
        if card_identifier < 64:
            mask_lo |= np.uint64(1) << np.uint64(card_identifier)
        else:
            mask_hi |= np.uint64(1) << np.uint64(card_identifier - 64)
    return mask_hi, mask_lo


def new_game_state(num_players: int) -> KonkanState:
    """Return an empty shell game state with the requested player count."""

    hands = [np.zeros(0, dtype=np.uint16) for _ in range(num_players)]
    public = [PlayerPublic(False, 0) for _ in range(num_players)]
    return KonkanState(
        player_to_act=0,
        turn_index=0,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[],
        hands=hands,
        table=[],
        public=public,
        highest_table_points=0,
        first_player_has_discarded=False,
    )

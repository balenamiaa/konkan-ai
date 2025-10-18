"""Core game state data structures for Konkan."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Iterable, List, Sequence

from . import encoding
from ._compat import np

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from numpy.typing import NDArray

    from .rules import TurnPhase as RulesTurnPhase

    UInt16Array = NDArray[np.uint16]
else:  # pragma: no cover - runtime fallback when numpy is absent
    UInt16Array = object
    RulesTurnPhase = object


class TurnPhase(str, Enum):
    """Phases that track high-level player actions."""

    AWAITING_DRAW = "awaiting_draw"
    AWAITING_TRASH = "awaiting_trash"
    COMPLETE = "complete"


@dataclass(slots=True)
class KonkanConfig:
    """Runtime configuration for a single Konkan round."""

    num_players: int
    hand_size: int = 14
    come_down_points: int = 81
    allow_trash_first_turn: bool = False
    dealer_index: int = 0
    first_player_hand_size: int | None = None

@dataclass(slots=True)
class PlayerState:
    """State tracked for each player at the table."""

    hand_mask: int = 0
    laid_mask: int = 0
    laid_points: int = 0
    has_come_down: bool = False
    phase: TurnPhase = TurnPhase.AWAITING_DRAW
    last_action_was_trash: bool = False

    def copy(self) -> "PlayerState":
        """Return a shallow copy of the player state."""

        return PlayerState(
            hand_mask=self.hand_mask,
            laid_mask=self.laid_mask,
            laid_points=self.laid_points,
            has_come_down=self.has_come_down,
            phase=self.phase,
            last_action_was_trash=self.last_action_was_trash,
        )

@dataclass(slots=True)
class PublicState:
    """Shared table state that is visible to all players."""

    draw_pile: List[int]
    trash_pile: List[int]
    turn_index: int
    dealer_index: int
    current_player_index: int = 0
    winner_index: int | None = None
    highest_table_points: int = 0
    last_trash_by: int | None = None

    def copy(self) -> "PublicState":
        """Return a shallow copy of the public table state."""

        return PublicState(
            draw_pile=list(self.draw_pile),
            trash_pile=list(self.trash_pile),
            turn_index=self.turn_index,
            dealer_index=self.dealer_index,
            current_player_index=self.current_player_index,
            winner_index=self.winner_index,
            highest_table_points=self.highest_table_points,
            last_trash_by=self.last_trash_by,
        )


def _default_phase() -> "RulesTurnPhase":
    """Return the default turn phase for a fresh game state."""

    from .rules import TurnPhase as _TurnPhase  # Local import to avoid cycles

    return _TurnPhase.DRAW


@dataclass(slots=True)
class MeldOnTable:
    """Representation of a meld that is visible on the table."""

    mask_hi: int
    mask_lo: int
    cards: List[int]
    owner: int
    kind: int
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

    player_to_act: int = 0
    turn_index: int = 0
    deck: UInt16Array = field(default_factory=lambda: np.zeros(0, dtype=np.uint16))
    deck_top: int = 0
    trash: List[int] = field(default_factory=list)
    hands: List[UInt16Array] = field(default_factory=list)
    table: List[MeldOnTable] = field(default_factory=list)
    public: PublicState = field(default_factory=lambda: PublicState([], [], 0, 0))
    highest_table_points: int = 0
    first_player_has_discarded: bool = False
    phase: "RulesTurnPhase" = field(default_factory=_default_phase)
    config: KonkanConfig | None = None
    players: List[PlayerState] = field(default_factory=list)

    def clone_shallow(self) -> "KonkanState":
        """Create a shallow copy of the state suitable for branching search."""

        public_copy = self.public.copy()
        return KonkanState(
            player_to_act=self.player_to_act,
            turn_index=self.turn_index,
            deck=self.deck.copy(),
            deck_top=self.deck_top,
            trash=list(self.trash),
            hands=[hand.copy() for hand in self.hands],
            table=[
                MeldOnTable(
                    mask_hi=meld.mask_hi,
                    mask_lo=meld.mask_lo,
                    cards=list(meld.cards),
                    owner=meld.owner,
                    kind=meld.kind,
                    has_joker=meld.has_joker,
                    points=meld.points,
                    is_four_set=meld.is_four_set,
                )
                for meld in self.table
            ],
            public=public_copy,
            highest_table_points=self.highest_table_points,
            first_player_has_discarded=self.first_player_has_discarded,
            phase=self.phase,
            config=self.config,
            players=[player.copy() for player in self.players],
        )

    def register_discard(self, player_index: int) -> None:
        """Update bookkeeping after a player discards a card."""

        if player_index == 0 and not self.first_player_has_discarded:
            self.first_player_has_discarded = True
        self.phase = _default_phase()


def hand_mask(hand: Iterable[int]) -> tuple[int, int]:
    """Compute the (hi, lo) bitset mask for a player's hand."""

    mask_hi = 0
    mask_lo = 0
    for card_identifier in hand:
        if card_identifier < 64:
            mask_lo |= 1 << card_identifier
        else:
            mask_hi |= 1 << (card_identifier - 64)
    return mask_hi, mask_lo


def new_game_state(num_players: int) -> KonkanState:
    """Return an empty shell game state with the requested player count."""

    hands = [np.zeros(0, dtype=np.uint16) for _ in range(num_players)]
    public = PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=0,
        dealer_index=0,
        current_player_index=0,
    )
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
        phase=_default_phase(),
    )


def deal_new_game(config: KonkanConfig, deck_cards: Sequence[int]) -> KonkanState:
    """Deal a fresh round returning an initialized ``KonkanState``."""

    draw_pile = list(deck_cards)
    players = [PlayerState() for _ in range(config.num_players)]
    first_player_index = 0
    if config.num_players:
        first_player_index = (config.dealer_index + 1) % config.num_players

    for idx, player in enumerate(players):
        desired_cards = config.hand_size
        if idx == first_player_index and config.first_player_hand_size is not None:
            desired_cards = config.first_player_hand_size
        elif idx == first_player_index and config.first_player_hand_size is None:
            desired_cards = config.hand_size
        for _ in range(desired_cards):
            if not draw_pile:
                raise ValueError("insufficient cards in deck for requested hand size")
            card_identifier = draw_pile.pop()
            player.hand_mask = encoding.add_card(player.hand_mask, card_identifier)

    current_player = first_player_index if config.num_players else 0
    public = PublicState(
        draw_pile=draw_pile,
        trash_pile=[],
        turn_index=0,
        dealer_index=config.dealer_index,
        current_player_index=current_player,
    )

    return KonkanState(
        player_to_act=current_player,
        turn_index=0,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[],
        hands=[],
        table=[],
        public=public,
        highest_table_points=0,
        first_player_has_discarded=False,
        phase=_default_phase(),
        config=config,
        players=players,
    )

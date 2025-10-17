"""State containers for the Konkan rules engine."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Sequence

from . import cards, encoding


class TurnPhase(Enum):
    AWAITING_DRAW = "awaiting_draw"
    AWAITING_TRASH = "awaiting_trash"
    COMPLETE = "complete"


@dataclass
class KonkanConfig:
    """High level configuration knobs for a Konkan deal."""

    num_players: int = 2
    hand_size: int = 13
    come_down_points: int = 51
    allow_trash_first_turn: bool = False
    recycle_shuffle_seed: int | None = None
    dealer_index: int = 0


@dataclass
class PlayerState:
    """Mutable view of a single player's private information."""

    hand_mask: encoding.Mask = field(default_factory=encoding.empty_mask)
    laid_mask: encoding.Mask = field(default_factory=encoding.empty_mask)
    melds: List[Sequence[int]] = field(default_factory=list)
    has_come_down: bool = False
    last_trash: encoding.CardId | None = None
    phase: TurnPhase = TurnPhase.AWAITING_DRAW
    pending_sarf: bool = False  # armed when a player draws a printed joker this turn

    def card_count(self) -> int:
        return encoding.popcount(self.hand_mask)


@dataclass
class PublicState:
    """Shared table state visible to every participant."""

    draw_pile: List[int] = field(default_factory=list)
    trash_pile: List[int] = field(default_factory=list)
    turn_index: int = 0
    dealer_index: int = 0
    pending_recycle: bool = False
    winner_index: int | None = None

    def top_trash(self) -> int | None:
        if not self.trash_pile:
            return None
        return self.trash_pile[-1]


@dataclass
class KonkanState:
    config: KonkanConfig
    players: List[PlayerState]
    public: PublicState

    def active_player(self) -> PlayerState:
        return self.players[self.public.turn_index]

    def player_view(self, index: int) -> PlayerState:
        return self.players[index]


# Factory helpers -----------------------------------------------------------

def deal_new_game(config: KonkanConfig, deck: List[int]) -> KonkanState:
    if len(deck) < config.num_players * config.hand_size:
        raise ValueError("deck too small for requested configuration")
    players = [PlayerState() for _ in range(config.num_players)]
    draw_pile = deck.copy()

    for round_index in range(config.hand_size):
        for player_index in range(config.num_players):
            card_id = draw_pile.pop()
            player = players[player_index]
            player.hand_mask = encoding.add_card(player.hand_mask, card_id)

    trash_pile: List[int] = [draw_pile.pop()]
    dealer = config.dealer_index % config.num_players
    public = PublicState(
        draw_pile=draw_pile,
        trash_pile=trash_pile,
        turn_index=(dealer + 1) % config.num_players,
        dealer_index=dealer,
    )
    for index, player in enumerate(players):
        player.phase = TurnPhase.AWAITING_DRAW if index == public.turn_index else TurnPhase.COMPLETE
    return KonkanState(config=config, players=players, public=public)


def serialize_state(state: KonkanState) -> Dict[str, object]:
    return {
        "config": asdict(state.config),
        "players": [
            {
                "hand_mask": player.hand_mask,
                "laid_mask": player.laid_mask,
                "melds": [list(meld) for meld in player.melds],
                "has_come_down": player.has_come_down,
                "last_trash": player.last_trash,
                "phase": player.phase.value,
                "pending_sarf": player.pending_sarf,
            }
            for player in state.players
        ],
        "public": {
            "draw_pile": list(state.public.draw_pile),
            "trash_pile": list(state.public.trash_pile),
            "turn_index": state.public.turn_index,
            "dealer_index": state.public.dealer_index,
            "pending_recycle": state.public.pending_recycle,
            "winner_index": state.public.winner_index,
        },
    }


def deserialize_state(payload: Dict[str, object]) -> KonkanState:
    config_payload = payload["config"]
    config = KonkanConfig(**config_payload)  # type: ignore[arg-type]
    players_payload = payload["players"]
    players: List[PlayerState] = []
    for entry in players_payload:
        player = PlayerState()
        player.hand_mask = entry["hand_mask"]
        player.laid_mask = entry["laid_mask"]
        player.melds = [tuple(meld) for meld in entry["melds"]]
        player.has_come_down = entry["has_come_down"]
        player.last_trash = entry["last_trash"]
        player.phase = TurnPhase(entry["phase"])
        player.pending_sarf = entry["pending_sarf"]
        players.append(player)

    public_payload = payload["public"]
    public = PublicState(
        draw_pile=list(public_payload["draw_pile"]),
        trash_pile=list(public_payload["trash_pile"]),
        turn_index=public_payload["turn_index"],
        dealer_index=public_payload["dealer_index"],
        pending_recycle=public_payload["pending_recycle"],
        winner_index=public_payload["winner_index"],
    )
    return KonkanState(config=config, players=players, public=public)


def ensure_player_has_cards(player: PlayerState, cards_to_remove: Iterable[int]) -> None:
    for card_id in cards_to_remove:
        if not encoding.has_card(player.hand_mask, card_id):
            raise ValueError(f"player missing card {cards.Card(card_id).code}")


def ensure_phase(player: PlayerState, expected: TurnPhase) -> None:
    if player.phase is not expected:
        raise RuntimeError(f"player is in phase {player.phase.value}, expected {expected.value}")

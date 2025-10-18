from __future__ import annotations

import random
from typing import List

from konkan import encoding, state
from konkan.determinize import sample_world
from konkan.state import PublicState


class ReverseShuffle:
    def shuffle(self, seq: List[int]) -> None:
        seq.reverse()


def test_sample_world_preserves_actor_hand_and_reassigns_opponents() -> None:
    config = state.KonkanConfig(
        num_players=3,
        hand_size=3,
        first_player_hand_size=3,
        dealer_index=0,
    )
    deck = list(range(30))
    game_state = state.deal_new_game(config, deck)

    public = game_state.public
    assert isinstance(public, PublicState)

    original_draw = list(public.draw_pile)
    actor = public.current_player_index
    original_actor_hand = encoding.cards_from_mask(game_state.players[actor].hand_mask)

    determinized = sample_world(game_state, ReverseShuffle())

    determinized_actor_hand = encoding.cards_from_mask(determinized.players[actor].hand_mask)
    assert determinized_actor_hand == original_actor_hand

    determinized_public = determinized.public
    assert isinstance(determinized_public, PublicState)

    assert determinized_public.draw_pile == list(reversed(original_draw))

    seen_cards = set()
    for idx, player in enumerate(determinized.players):
        hand_cards = encoding.cards_from_mask(player.hand_mask)
        if idx == actor:
            continue
        assert len(hand_cards) == 3
        for cid in hand_cards:
            assert cid not in original_actor_hand
            assert cid not in seen_cards
            seen_cards.add(cid)


def test_sample_world_uses_rng_shuffle() -> None:
    class ShuffleRecorder:
        def __init__(self) -> None:
            self.calls = 0

        def shuffle(self, seq: List[int]) -> None:
            self.calls += 1
            random.shuffle(seq)

    config = state.KonkanConfig(num_players=2, hand_size=2, first_player_hand_size=2)
    deck = list(range(20))
    game_state = state.deal_new_game(config, deck)

    recorder = ShuffleRecorder()
    sample_world(game_state, recorder)
    assert recorder.calls >= 1

# Konkan AI

Konkan AI is a modern playground for experimenting with information-set Monte Carlo tree search (IS-MCTS) strategies for the three-player Konkan card game. The project blends Python orchestration, a Rust meld solver, and an expressive Typer/Rich CLI to deliver a competitive and stylish tabletop experience.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
# Optional: build the Rust meld solver once it is implemented
# (requires the Rust toolchain via https://rustup.rs)
# maturin develop --release
```

The repository targets Python 3.10+, NumPy for fast array work, Numba for hot loops, and maturin+pyo3 for Rust interoperability. Ruff and pytest are preconfigured for linting and testing.

## Konkan rules (human-friendly summary)

### Deck and objective
- Konkan uses two standard 52-card decks plus two Jokers for a total of 106 physical cards. Duplicate copies of a card are tracked explicitly so every physical card is distinguishable.
- The rank order is A, 2–10, J, Q, K. Aces may appear only at the ends of runs (A-2-3 or Q-K-A) and never wrap around.
- Points follow the traditional Konkan scale: Ace and 10–King are worth 10 points, pip cards are worth their face value, and Jokers adopt the value of the card they represent inside a meld.

### Dealing and turn flow
- **Opening deal:** the starting player receives 15 cards and must immediately discard one to close the opening turn. Every other player receives 14 cards.
- **Normal turns:** each subsequent turn has three ordered phases: draw exactly one card, optionally perform table actions (coming down and/or sarf), then discard exactly one card.
- **Draw sources:** drawing from the face-down deck is always legal; drawing from the trash pile (face-up discard pile) is subject to the rules described below.

### Coming down (initial melds)
- A player who has not yet come down may only do so by laying melds whose combined points meet or exceed the current threshold.
- The starting threshold is 81 points. Once any player has come down, the required threshold for everyone else becomes one point higher than the current highest total of melds on the table (strictly increasing each time someone raises the bar).
- Valid melds are either runs of three or more suited cards (Aces only at the ends) or sets of three or four distinct-suited cards. Jokers may substitute for any single missing card but inherit its point value.
- When evaluating whether a player may take the top trash card before they have come down, temporarily include that card in their hand and verify via the meld solver that the threshold can be met. If not, they must draw from the deck instead.

### Sarf and Joker swaps
- After coming down, a player may **sarf** by extending any meld on the table, regardless of the original owner, as long as the resulting meld remains valid.
- If a meld on the table contains a Joker, a player holding the represented card may swap it in: the real card is placed on the meld, and the Joker returns to the player’s hand for later use. The meld’s point total updates to reflect the new card arrangement.
- Sets of four cards are immediately slid under the trash pile when first played. Once sealed, they cannot be extended by future sarfs.

### Drawing from the trash pile
- Players who are already down may always draw the top trash card instead of drawing from the deck.
- Players who are not down may draw the top trash card only if adding that specific card allows them to come down right now (per the threshold check above).
- After a trash pickup the player continues their turn normally and must still finish with a discard.

### Ending a round
- **Standard go-out:** arrange all 14 cards in hand into melds and then discard the 15th card you drew that turn. The discard must leave no deadwood.
- **Sarf endgame:** if a player is already down and, through sarf actions, empties their hand to two or fewer cards, they may legally finish the round by sarfing those final cards without needing an additional discard, provided every resulting meld remains valid.
- The round ends immediately when a player goes out. Traditional Konkan scoring awards opponents the total points of the cards remaining in their hands if they have not come down, or the points of their remaining hand cards after subtracting cards already laid on the table if they have come down. The AI currently stops the simulation when someone goes out, so post-round scoring is informative but not yet automated.

---

Further milestones will layer in the Rust meld solver, determinization, IS-MCTS search, and a sumptuous Rich-powered CLI to visualise every play.

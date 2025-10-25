# Konkan AI

Konkan AI is a modern playground for experimenting with information-set Monte Carlo tree search (IS-MCTS) strategies for the three-player Konkan card game. The project blends Python orchestration, a Rust meld solver, and a Textual-powered terminal experience to deliver a competitive and stylish tabletop session.

## Development setup

This project is developed and tested against **CPython 3.14**. The quickest way to get going is with [uv](https://github.com/astral-sh/uv):

```bash
# Install Python 3.14 if needed and create a virtual environment
uv python pin 3.14
uv venv
source .venv/bin/activate

# Install the project in editable mode with development extras
uv pip install -e .[dev]

# Optional: build the Rust meld solver once it lands in-tree
# (requires the Rust toolchain via https://rustup.rs)
# PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv run maturin develop --release
```

Ruff and pytest ship preconfigured, and the default dependency stack (NumPy, Numba, Typer, Rich, Pydantic) is verified on Python 3.14.

### Developer utilities

Common maintenance commands are available once the environment is active:

```bash
# Format the repository with Ruff
uv run konkan-format

# Lint sources
uv run konkan-lint

# Type-check with mypy
uv run konkan-typecheck

# Lint, type-check, and run pytest
uv run konkan-test
```

## Command line play

Fire up the Textual UI for a quick match against AI opponents:

```bash
uv run konkan-play play --players 3 --humans 1 --simulations 256 \
  --dirichlet-alpha 0.3 --dirichlet-weight 0.25 --debug
```

The UI supports two or three seats, with any number of humans from zero to the player count. Each turn renders the full table, a rolling event log, highlighted meld suggestions, and an action palette that accepts arrow keys or number shortcuts. Key bindings:

- `D` — toggle the debug overlay (search stats, deck/trash counts).
- `H` — reveal or hide every hand (handy for post-game analysis).
- `N` — advance to the next round after a winner is declared.
- `Q` — exit the session at any time.

Points, laid melds, and deadwood totals accumulate automatically across rounds via a live scoreboard. Optional knobs such as `--dirichlet-alpha` / `--dirichlet-weight` inject AlphaZero-style exploration, `--no-opponent-priors` disables the heuristic opponent model, and `--debug` enables the richer overlays right from the first frame.

### Head-to-head benchmarks

Automated head-to-head runs help compare different IS-MCTS settings. Launch them straight from the CLI:

```bash
uv run konkan-play benchmark --rounds 20 --baseline-sims 128 --challenger-sims 256 \
  --dirichlet-alpha 0.3 --dirichlet-weight 0.2
```

Prefer Python? The underlying harness remains available:

```python
from konkan.benchmark import run_head_to_head
from konkan.ismcts.search import SearchConfig

report = run_head_to_head(
    rounds=10,
    baseline=SearchConfig(simulations=64),
    challenger=SearchConfig(simulations=256),
    seed=42,
)

print(report.baseline, report.challenger)
```

Each report bundles the per-round history alongside aggregated wins, laid points, deadwood, and net totals for the two agents.

## The Rules of Konkan

### Game Objective

Konkan is a Rummy-style card game where players **race to get rid of all their cards before their enemies do.** The goal is to, on your turn, form valid combinations (**"pairs"**) with 14 of your cards and **"throw"** the final 15th card to win.

### Setup

- **Players:** 2 or 3 players (each player competes individually).
- **Deck:** The game uses two standard 52-card decks plus two Jokers, for a total of 106 cards. This means there are two of every card (e.g., two Aces of Hearts).
- **Dealing:**
  1. The player designated to go first is dealt a **"hand"** of 15 cards.
  2. All other players are dealt a hand of 14 cards.
  3. The remaining cards are placed face-down to form the **"deck"**.
  4. The **"trash"** pile starts empty and is created by the first player's discard.

### Card Ranks and Point Values

- **Ranks:** The card ranks are circular but cannot be used in "wrap-around" combinations. The order is: **A-2-3-4-5-6-7-8-9-10-J-Q-K-A**.
- **Point Values:**
  - **Ace:** 10 points
  - **K, Q, J, 10:** 10 points each
  - **2 through 9:** Face value (e.g., a 7 is worth 7 points)
  - **Joker:** Takes the point value of the card it represents in a pair.

### Gameplay

#### Starting the Game

The player dealt 15 cards takes the first turn. This turn is unique: they **do not pull a card**. They simply examine their hand and **throw** one card face-up to start the trash pile. Play then proceeds to the next player.

#### A Player's Standard Turn

Every turn after the first consists of three steps, in order:

1. **Pull:** You must start your turn by pulling one card (bringing your hand to 15 cards). You have two options:
   - Pull the top card from the face-down **deck**.
   - Pull the top card from the face-up **trash** pile (see specific rules below).
2. **Action (Optional):** After pulling, you may perform game actions if you are able:
   - **"Come Down"**: Place your initial pairs onto the table.
   - **"Sarf"**: Add cards from your hand to existing pairs on the table.
   - Form new pairs after you have already come down.
3. **Throw:** You must end your turn by discarding one card from your hand and placing it face-up on top of the **trash** pile.

### Forming Pairs (Melds)

To come down or win, you must form valid "pairs". A pair must contain 3 or more cards. There are two types:

1. **Run (Consecutive cards of the same suit)**
   - **Definition:** Three or more cards of the same suit in sequential rank.
   - **Ace Rule:** The Ace can be at the beginning of a run (`A_heart, 2_heart, 3_heart`) or at the end (`Q_diamond, K_diamond, A_diamond`). A "wrap-around" run (`K_spade, A_spade, 2_spade`) is **not valid**.
   - **Example Value:** The pair `(A_heart, 2_heart, 3_heart)` is worth 10 + 2 + 3 = 15 points.
2. **Set (Cards of the same rank)**
   - **Definition:** Three or four cards of the same rank, where each card in the pair has a different suit.
   - **Example:** `(7_spades, 7_diamonds, 7_clubs)` is a valid set. It can be extended with the `7_hearts`. A set cannot contain two cards of the same suit.

### The Joker (Wildcard)

- There are **two Jokers** in the deck.
- A Joker is a wildcard and can substitute for any card needed to complete a Run or a Set.
- **Swapping a Joker:** If an enemy has a pair on the table containing a Joker, a player who has already "come down" may swap it. If you hold the actual card the Joker represents, you can place your card into the pair and take the Joker into your hand. This action is performed during your turn.

### "Coming Down" (Making Your First Melds)

"Coming down" is the act of placing your first set of pairs from your hand onto the table. It is governed by strict point-value rules.

- **First Player to Come Down:** If no enemy has come down yet, the total point value of the cards in the pairs you put down must be **81 or more**.
- **Subsequent Players:** If an enemy has already come down, the total point value of your pairs must be **at least 1 point higher than the highest score currently on the table**.

### Pulling from the Trash Pile

You may pull the top card from the trash pile only if you meet **one** of these conditions:

1. You have **already "come down"** in a previous turn.
2. You are **able to "come down" in this exact turn** by using the card you pull from the trash pile.

### "Sarf" (Laying Off Cards)

"Sarf" is adding a card from your hand to a valid pair already on the table (yours or an enemy's).

- **Condition:** You can only perform a "sarf" **after** you have successfully "come down".

### Special Rules

- **Complete Set of Four:** When you come down with a complete set of four identical ranks (e.g., `K_heart, K_diamond, K_spade, K_club`), that pair is immediately moved **underneath the trash pile**. It is immune to "sarf," and its cards cannot be pulled.
- **Running out of Cards:** If the deck runs out, the entire trash pile is shuffled thoroughly to become the new deck.

### Winning the Game

There are two primary ways to win, but both must end with the same action: **throwing your final card**. You can never end your turn with zero cards.

1. **Winning from a Full Hand (Going Out)**  
   This is the main way to win. On your turn, after you **pull** a card (bringing your hand to 15 cards), you can win immediately if you can:
   - Arrange 14 of those 15 cards into one or more valid pairs.
   - Meet the point requirements for "coming down" if you haven't already.
   - You then place all 14 cards down and **throw** the 15th card to win.
2. **Winning from a Small Hand (The "Sarf" Endgame)**  
   If you have already come down and are left with only a few cards, you cannot form new pairs. Your only path to victory is through "sarf".
   - **From 2 Cards:** You start your turn with 2 cards. You pull a card (now you have 3). To win, you must be able to "sarf" the two cards you started with. This leaves the single card you pulled, which you throw to win.
   - **From 1 Card:** You start your turn with 1 card. You pull a card (now you have 2). To win, you must "sarf" one of those cards. This leaves the other card in your hand, which you throw to win.

---

Further milestones will layer in the Rust meld solver, determinization, IS-MCTS search, and a Rich-powered CLI to visualise every play.

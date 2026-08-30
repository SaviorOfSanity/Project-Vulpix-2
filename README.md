# Project Vulpix 2.0 - Pokémon TCG Simulator & MCTS AI Engine

A complete, high-performance turn-based Pokémon Trading Card Game (TCG) simulator in Python, equipped with an advanced Monte Carlo Tree Search (MCTS) reinforcement learning controller, baseline heuristic AI, official tournament rules, unit test suite, and interactive visual interfaces.

---

## 🌟 Features

- **Core Engine & Official Rulebook Compliance**:
  - **Full Turn Lifecycle**: Mandatory draw phase (skipped for P1 Turn 1 in modern rules), multi-action development turns (`play_pokemon`, `evolve`, `play_supporter`, `attach_energy`, `retreat`), concluding only when `attack` or `pass` is executed.
  - **Tournament Evolution Rules**: No evolution on a player's first turn of the game, no evolution on the turn a Pokémon is put into play, and no multiple evolutions on the same turn. Damage counters and attached energy are preserved.
  - **Player 1 Turn 1 Restrictions**: Player going first on Turn 1 cannot attack and cannot play Supporter cards.
  - **Type Effectiveness**: Exact Weakness ($2\times$) and Resistance ($-30$) damage calculations.
  - **Action Limits**: Max 1 energy attachment/turn, max 1 supporter/turn, max 1 retreat/turn, bench limit 5.
  - **Card Resolution Order**: Strict resolution order for hand-modifying cards (e.g. *Professor's Research* pops from hand first, discards remainder of hand, draws 7, moves to discard, sets supporter flag).
  - **Knockouts & Win Conditions**: Evaluates active discard, prize card distribution, and win conditions in strict priority (1. Take all 6 Prize cards, 2. Bench Wipe, 3. Deck Out).
  - **Mulligan Rules**: Automatic mulligan procedure if opening hand contains 0 Basic Pokémon, granting the opponent extra bonus card draws.

- **AI Controllers**:
  - **`MCTSController`**: Advanced Monte Carlo Tree Search with UCB1 selection, rigorous two-player zero-sum perspective inversion, bounded greedy rollout policy, unvisited fallback, and normalized $[-1.0, 1.0]$ composite heuristic evaluation (Prize differential, Board presence, Active damage, Energy/Attack potential, Deck preservation).
  - **`TurnBasedGreedyAI`**: Baseline heuristic priority AI (Bench/Evolve $\rightarrow$ Attach Energy Active then Bench $\rightarrow$ Supporter $\rightarrow$ Highest Damage Attack $\rightarrow$ Pass).

- **Visual Interfaces & Tooling**:
  - **Interactive Web Visualizer (`pokemon_tcg_visualizer.html`)**: Rich animated GUI with HP bars, attached energy tokens, step-by-step turn execution, auto-play speed controls, live MCTS advantage gauge, and Human vs AI mode.
  - **Native Desktop GUI (`gui_app.py`)**: Zero-dependency Python Tkinter application directly linked to the live Python engine.
  - **Automated Test Suite (`test_game_engine.py`)**: 13 comprehensive unit test cases covering engine mechanics and AI logic.
  - **Simulation Runner (`Game Engine.py` / `generate_logs.py`)**: Batch simulation harness with concise per-move telemetry and post-match win statistics.

---

## 📁 Repository Structure

```
.
├── Game Engine.py              # Main Game Engine, Cards, Player, GameState, AI Controllers & Harness
├── cards.json                  # JSON card database (Pikachu, Charmander, Charmeleon, Energy, Trainers)
├── gui_app.py                  # Native Python Tkinter Desktop Visualizer
├── pokemon_tcg_visualizer.html # Standalone interactive HTML5/Tailwind Visualizer
├── test_game_engine.py         # Complete automated test suite
├── generate_logs.py            # Sample match and simulation telemetry generator
├── README.md                   # Project documentation
└── .gitignore                  # Git ignore rules
```

---

## 🚀 Quickstart & Usage

### 1. Run the Automated Test Suite
```bash
python test_game_engine.py
```

### 2. Run Batch AI Simulations
```bash
python "Game Engine.py"
```

### 3. Launch the Native Desktop GUI
```bash
python gui_app.py
```

### 4. Launch the Web Visualizer
Open `pokemon_tcg_visualizer.html` in any web browser.

---

## 📜 License
MIT License.

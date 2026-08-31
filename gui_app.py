"""
Pokémon TCG Visual GUI & ISMCTS Tournament Suite (Standard Format - Phase 4)
Uses Python's standard tkinter GUI framework (no external dependencies needed).
Connects directly to the live Game Engine, Special Conditions, ACE SPECs, 8-Deck Archetype Pool, and Tournament Matrix Runner.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

# Import live game engine
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
Player = game_engine.Player
GameState = game_engine.GameState
TurnBasedGreedyAI = game_engine.TurnBasedGreedyAI
MCTSController = game_engine.MCTSController
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES
TournamentMatrixRunner = game_engine.TournamentMatrixRunner

ARCHETYPES = STANDARD_ARCHETYPES


class PokemonTCGGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Pokémon TCG Simulator & Tournament Matrix Suite (Standard Format - Phase 4)")
        self.root.geometry("1340x940")
        self.root.minsize(1140, 820)
        self.root.configure(bg="#0f172a")

        # Game State
        self.factory = CardFactory('cards.json')
        self.p1_archetype_name = "Gardevoir ex"
        self.p2_archetype_name = "Terapagos ex"

        self.game = None
        self.mcts = MCTSController(iteration_limit=300, simulation_depth=16)
        self.greedy = TurnBasedGreedyAI()
        
        self.is_auto_playing = False
        self.auto_speed_ms = 600
        self.mode = "ai_vs_ai"

        self.setup_styles()
        self.build_ui()
        self.start_new_match()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", thickness=8, troughcolor="#1e293b", background="#10b981")
        style.configure("TCombobox", fieldbackground="#1e293b", background="#334155", foreground="#f8fafc")
        style.configure("Treeview", background="#0f172a", foreground="#f8fafc", fieldbackground="#0f172a", font=("Segoe UI", 8))
        style.configure("Treeview.Heading", background="#1e293b", foreground="#38bdf8", font=("Segoe UI", 9, "bold"))

    def build_ui(self):
        # 1. Top Navigation & Controls Bar
        top_bar = tk.Frame(self.root, bg="#1e293b", padx=12, pady=10, relief="groove", bd=1)
        top_bar.pack(side="top", fill="x")

        title_label = tk.Label(
            top_bar,
            text="⚡ Pokémon TCG & Tournament Suite",
            font=("Segoe UI", 13, "bold"),
            fg="#f8fafc",
            bg="#1e293b"
        )
        title_label.pack(side="left", padx=6)

        # Mode Selector
        self.mode_var = tk.StringVar(value="ai_vs_ai")
        mode_btn1 = tk.Radiobutton(
            top_bar, text="ISMCTS vs AI", variable=self.mode_var, value="ai_vs_ai",
            command=self.on_mode_change, bg="#1e293b", fg="#94a3b8", selectcolor="#0f172a",
            activebackground="#1e293b", activeforeground="#f8fafc", font=("Segoe UI", 8, "bold")
        )
        mode_btn1.pack(side="left", padx=2)

        mode_btn2 = tk.Radiobutton(
            top_bar, text="Human vs ISMCTS", variable=self.mode_var, value="human_vs_mcts",
            command=self.on_mode_change, bg="#1e293b", fg="#94a3b8", selectcolor="#0f172a",
            activebackground="#1e293b", activeforeground="#f8fafc", font=("Segoe UI", 8, "bold")
        )
        mode_btn2.pack(side="left", padx=2)

        # Deck Archetype Pickers
        tk.Label(top_bar, text="P1:", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(8, 2))
        self.p1_combo = ttk.Combobox(top_bar, values=list(ARCHETYPES.keys()), state="readonly", width=16, font=("Segoe UI", 8))
        self.p1_combo.set(self.p1_archetype_name)
        self.p1_combo.pack(side="left", padx=2)
        self.p1_combo.bind("<<ComboboxSelected>>", self.on_archetype_change)

        tk.Label(top_bar, text="P2:", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(6, 2))
        self.p2_combo = ttk.Combobox(top_bar, values=list(ARCHETYPES.keys()), state="readonly", width=16, font=("Segoe UI", 8))
        self.p2_combo.set(self.p2_archetype_name)
        self.p2_combo.pack(side="left", padx=2)
        self.p2_combo.bind("<<ComboboxSelected>>", self.on_archetype_change)

        # Action Buttons
        btn_new = tk.Button(
            top_bar, text="🔄 Reset", font=("Segoe UI", 8, "bold"),
            bg="#059669", fg="#ffffff", activebackground="#10b981", activeforeground="#ffffff",
            relief="flat", padx=8, pady=3, cursor="hand2", command=self.start_new_match
        )
        btn_new.pack(side="left", padx=3)

        self.btn_step = tk.Button(
            top_bar, text="▶️ Step", font=("Segoe UI", 8, "bold"),
            bg="#4f46e5", fg="#ffffff", activebackground="#6366f1", activeforeground="#ffffff",
            relief="flat", padx=8, pady=3, cursor="hand2", command=self.step_action
        )
        self.btn_step.pack(side="left", padx=3)

        self.btn_auto = tk.Button(
            top_bar, text="⏩ Auto", font=("Segoe UI", 8, "bold"),
            bg="#334155", fg="#ffffff", activebackground="#475569", activeforeground="#ffffff",
            relief="flat", padx=8, pady=3, cursor="hand2", command=self.toggle_auto_play
        )
        self.btn_auto.pack(side="left", padx=3)

        btn_matrix = tk.Button(
            top_bar, text="🏆 Tournament Matrix", font=("Segoe UI", 8, "bold"),
            bg="#d97706", fg="#ffffff", activebackground="#f59e0b", activeforeground="#ffffff",
            relief="flat", padx=8, pady=3, cursor="hand2", command=self.open_tournament_window
        )
        btn_matrix.pack(side="left", padx=4)

        # Speed Slider
        lbl_speed = tk.Label(top_bar, text="Speed:", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b")
        lbl_speed.pack(side="left", padx=(8, 2))
        self.slider_speed = tk.Scale(
            top_bar, from_=100, to=1500, orient="horizontal", bg="#1e293b", fg="#94a3b8",
            highlightthickness=0, length=65, showvalue=0, command=self.on_speed_change
        )
        self.slider_speed.set(600)
        self.slider_speed.pack(side="left", padx=2)

        # 2. Main Content Split
        content_frame = tk.Frame(self.root, bg="#0f172a", padx=10, pady=6)
        content_frame.pack(fill="both", expand=True)

        left_playmat = tk.Frame(content_frame, bg="#0f172a")
        left_playmat.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right_panel = tk.Frame(content_frame, bg="#0f172a", width=350)
        right_panel.pack(side="right", fill="both", expand=False)

        # --- PLAYMAT: OPPONENT (P2) ---
        self.p2_card_frame = tk.LabelFrame(
            left_playmat, text=" Opponent: Player 2 (Greedy AI) ", font=("Segoe UI", 10, "bold"),
            bg="#1e293b", fg="#f43f5e", relief="groove", bd=1, padx=8, pady=4
        )
        self.p2_card_frame.pack(fill="x", pady=(0, 3))

        self.p2_stats_label = tk.Label(self.p2_card_frame, text="", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b")
        self.p2_stats_label.pack(anchor="w")

        p2_board_row = tk.Frame(self.p2_card_frame, bg="#1e293b")
        p2_board_row.pack(fill="x", pady=2)

        self.p2_active_label = tk.Label(
            p2_board_row, text="Active: (None)", font=("Segoe UI", 9, "bold"),
            bg="#0f172a", fg="#f8fafc", relief="ridge", bd=2, width=34, height=5, justify="center"
        )
        self.p2_active_label.pack(side="left", padx=4)

        self.p2_bench_label = tk.Label(
            p2_board_row, text="Bench: (Empty)", font=("Segoe UI", 8),
            bg="#0f172a", fg="#cbd5e1", relief="ridge", bd=1, height=5, justify="left", anchor="nw", padx=6, pady=3
        )
        self.p2_bench_label.pack(side="left", fill="both", expand=True, padx=4)

        # --- CENTER STATUS BANNER ---
        self.center_banner = tk.Frame(left_playmat, bg="#1e1b4b", padx=10, pady=5, relief="groove", bd=1)
        self.center_banner.pack(fill="x", pady=3)

        self.turn_status_label = tk.Label(
            self.center_banner, text="Turn 1 | Active Player: P1",
            font=("Segoe UI", 9, "bold"), fg="#a5b4fc", bg="#1e1b4b"
        )
        self.turn_status_label.pack(side="left")

        self.stadium_label = tk.Label(
            self.center_banner, text="Stadium: (None)",
            font=("Segoe UI", 8, "bold"), fg="#34d399", bg="#1e1b4b"
        )
        self.stadium_label.pack(side="left", padx=14)

        self.last_move_label = tk.Label(
            self.center_banner, text="Game Initialized.",
            font=("Segoe UI", 8, "italic"), fg="#f8fafc", bg="#1e1b4b"
        )
        self.last_move_label.pack(side="right")

        # --- PLAYMAT: PLAYER 1 (ISMCTS / Human) ---
        self.p1_card_frame = tk.LabelFrame(
            left_playmat, text=" Player 1: (ISMCTS AI / You) ", font=("Segoe UI", 10, "bold"),
            bg="#1e293b", fg="#6366f1", relief="groove", bd=1, padx=8, pady=4
        )
        self.p1_card_frame.pack(fill="x", pady=(3, 0))

        p1_board_row = tk.Frame(self.p1_card_frame, bg="#1e293b")
        p1_board_row.pack(fill="x", pady=2)

        self.p1_active_label = tk.Label(
            p1_board_row, text="Active: (None)", font=("Segoe UI", 9, "bold"),
            bg="#0f172a", fg="#f8fafc", relief="ridge", bd=2, width=34, height=5, justify="center"
        )
        self.p1_active_label.pack(side="left", padx=4)

        self.p1_bench_label = tk.Label(
            p1_board_row, text="Bench: (Empty)", font=("Segoe UI", 8),
            bg="#0f172a", fg="#cbd5e1", relief="ridge", bd=1, height=5, justify="left", anchor="nw", padx=6, pady=3
        )
        self.p1_bench_label.pack(side="left", fill="both", expand=True, padx=4)

        self.p1_stats_label = tk.Label(self.p1_card_frame, text="", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b")
        self.p1_stats_label.pack(anchor="w", pady=(2, 0))

        # P1 Hand View
        self.p1_hand_frame = tk.Frame(self.p1_card_frame, bg="#0f172a", padx=6, pady=3, relief="sunken", bd=1)
        self.p1_hand_frame.pack(fill="x", pady=3)
        self.p1_hand_label = tk.Label(
            self.p1_hand_frame, text="Hand: (Empty)", font=("Segoe UI", 8),
            fg="#e2e8f0", bg="#0f172a", anchor="w", justify="left"
        )
        self.p1_hand_label.pack(fill="x")

        # Interactive Human Controls Panel
        self.human_panel = tk.Frame(left_playmat, bg="#0f172a", pady=2)
        self.human_panel.pack(fill="x")
        self.human_actions_frame = tk.Frame(self.human_panel, bg="#0f172a")
        self.human_actions_frame.pack(fill="x")

        # --- RIGHT SIDE: TELEMETRY & LOGS ---
        mcts_box = tk.LabelFrame(
            right_panel, text=" ISMCTS Heuristic Advantage ", font=("Segoe UI", 9, "bold"),
            bg="#1e293b", fg="#38bdf8", relief="groove", bd=1, padx=8, pady=6
        )
        mcts_box.pack(fill="x", pady=(0, 4))

        self.score_display_label = tk.Label(
            mcts_box, text="Evaluation Score: +0.000", font=("Segoe UI", 10, "bold"),
            fg="#10b981", bg="#1e293b"
        )
        self.score_display_label.pack(anchor="w")

        self.progress_advantage = ttk.Progressbar(mcts_box, orient="horizontal", mode="determinate", maximum=2.0)
        self.progress_advantage.pack(fill="x", pady=3)
        self.progress_advantage['value'] = 1.0

        self.breakdown_label = tk.Label(
            mcts_box, text="Prizes: 0 | Board: 0 | Damage: 0 | Conditions: None",
            font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b", justify="left"
        )
        self.breakdown_label.pack(anchor="w")

        log_box = tk.LabelFrame(
            right_panel, text=" Move-by-Move Telemetry Log ", font=("Segoe UI", 9, "bold"),
            bg="#1e293b", fg="#f8fafc", relief="groove", bd=1, padx=6, pady=4
        )
        log_box.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_box, bg="#0f172a", fg="#f1f5f9", font=("Consolas", 8),
            wrap="word", relief="flat", padx=4, pady=4
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scrollbar = tk.Scrollbar(log_box, command=self.log_text.yview)
        log_scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scrollbar.set)

    def log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def on_mode_change(self):
        self.mode = self.mode_var.get()
        if self.is_auto_playing:
            self.toggle_auto_play()
        self.start_new_match()

    def on_archetype_change(self, event=None):
        self.p1_archetype_name = self.p1_combo.get()
        self.p2_archetype_name = self.p2_combo.get()
        self.start_new_match()

    def on_speed_change(self, val):
        self.auto_speed_ms = int(val)

    def start_new_match(self):
        if self.is_auto_playing:
            self.toggle_auto_play()

        self.log_text.delete("1.0", "end")

        c1 = self.mcts if self.mode == "ai_vs_ai" else None
        c2 = self.greedy

        d1_list = ARCHETYPES[self.p1_archetype_name]
        d2_list = ARCHETYPES[self.p2_archetype_name]

        p1_name = f"P1 [{self.p1_archetype_name}]"
        p2_name = f"P2 [{self.p2_archetype_name}]"

        p1 = Player(p1_name, d1_list, self.factory, controller=c1)
        p2 = Player(p2_name, d2_list, self.factory, controller=c2)

        self.game = GameState(p1, p2)
        self.game.setup_game(verbose=False)

        self.log(f"=== New Match Started: {p1.name} vs {p2.name} ===")
        self.update_view()

    def format_card_info(self, p_card):
        if not p_card:
            return "(None)"
        eff_max = p_card.get_effective_max_hp()
        cur_hp = eff_max - p_card.damage_counters
        energy_count = sum(getattr(e, 'energy_units', 1) for e in p_card.attached_energy)
        ex_str = f" [EX {p_card.prize_yield}P]" if p_card.is_rule_box else ""
        tera_str = " [Tera]" if p_card.is_tera else ""
        tool_str = f" [Tool: {p_card.attached_tool.name}]" if p_card.attached_tool else ""
        cond_str = f" [Cond: {', '.join(k.value for k in p_card.special_conditions)}]" if p_card.special_conditions else ""
        ab_str = f" [Ability: {p_card.ability['name']}]" if p_card.ability else ""
        atks = ", ".join([f"{a['name']} ({a['damage']}dmg)" for a in p_card.attacks])
        return f"{p_card.name}{ex_str}{tera_str}{tool_str}{cond_str}{ab_str}\nHP: {cur_hp}/{eff_max} | Energy: {energy_count}⚡\nAttacks: {atks}"

    def update_view(self):
        if not self.game:
            return

        p1 = self.game.players[0]
        p2 = self.game.players[1]
        active_p = self.game.get_active_player()

        self.turn_status_label.config(
            text=f"Turn {self.game.turn_number + 1} | Active: {active_p.name}"
        )
        stadium_name = self.game.active_stadium.name if self.game.active_stadium else "None"
        self.stadium_label.config(text=f"Stadium: {stadium_name}")

        # Opponent (P2)
        p2_max_b = p2.get_max_bench_size(self.game)
        self.p2_stats_label.config(
            text=f"Deck: {len(p2.deck)} | Hand: {len(p2.hand)} | Prizes Remaining: {len(p2.prize_cards)}"
        )
        if p2.active_pokemon:
            self.p2_active_label.config(text=f"ACTIVE: {self.format_card_info(p2.active_pokemon)}", fg="#fb7185")
        else:
            self.p2_active_label.config(text="ACTIVE: (None)", fg="#94a3b8")

        p2_bench_str = "\n".join([f"• {self.format_card_info(p)}" for p in p2.bench]) or "(Bench Empty)"
        self.p2_bench_label.config(text=f"BENCH ({len(p2.bench)}/{p2_max_b}):\n{p2_bench_str}")

        # Player 1 (P1)
        p1_max_b = p1.get_max_bench_size(self.game)
        self.p1_stats_label.config(
            text=f"Deck: {len(p1.deck)} | Hand: {len(p1.hand)} | Prizes Remaining: {len(p1.prize_cards)}"
        )
        if p1.active_pokemon:
            self.p1_active_label.config(text=f"ACTIVE: {self.format_card_info(p1.active_pokemon)}", fg="#818cf8")
        else:
            self.p1_active_label.config(text="ACTIVE: (None)", fg="#94a3b8")

        p1_bench_str = "\n".join([f"• {self.format_card_info(p)}" for p in p1.bench]) or "(Bench Empty)"
        self.p1_bench_label.config(text=f"BENCH ({len(p1.bench)}/{p1_max_b}):\n{p1_bench_str}")

        p1_hand_str = " | ".join([c.name + (" [ACE]" if c.is_ace_spec else "") for c in p1.hand]) or "(Hand Empty)"
        self.p1_hand_label.config(text=f"HAND ({len(p1.hand)}): {p1_hand_str}")

        # ISMCTS Heuristic Telemetry
        eval_score = self.mcts._evaluate_state(self.game, p1)
        self.score_display_label.config(
            text=f"Evaluation Score: {eval_score:+.3f}",
            fg="#10b981" if eval_score >= 0 else "#f43f5e"
        )
        self.progress_advantage['value'] = eval_score + 1.0

        prize_diff = len(p2.prize_cards) - len(p1.prize_cards)
        p1_board = (1 if p1.active_pokemon else 0) + len(p1.bench)
        p2_board = (1 if p2.active_pokemon else 0) + len(p2.bench)
        board_diff = p1_board - p2_board
        p2_dmg = p2.active_pokemon.damage_counters if p2.active_pokemon else 0
        p2_max = p2.active_pokemon.get_effective_max_hp() if p2.active_pokemon else 1
        p2_conds = ", ".join([k.value for k in p2.active_pokemon.special_conditions]) if (p2.active_pokemon and p2.active_pokemon.special_conditions) else "None"

        self.breakdown_label.config(
            text=f"Prize Diff: {prize_diff:+d} | Board Diff: {board_diff:+d} | Damage: {p2_dmg}/{p2_max} | Opp Conds: {p2_conds}"
        )

        for widget in self.human_actions_frame.winfo_children():
            widget.destroy()

        if self.mode == "human_vs_mcts" and self.game.active_player_index == 0 and not self.game.game_over:
            moves = self.game.get_legal_moves()
            lbl_pick = tk.Label(self.human_actions_frame, text="Your Move:", font=("Segoe UI", 9, "bold"), fg="#38bdf8", bg="#0f172a")
            lbl_pick.pack(side="left", padx=4)
            for m in moves[:6]:
                btn_m = tk.Button(
                    self.human_actions_frame, text=self.format_move_text(m), font=("Segoe UI", 8),
                    bg="#1e293b", fg="#f8fafc", activebackground="#334155", activeforeground="#ffffff",
                    relief="groove", padx=6, pady=2, cursor="hand2", command=lambda move=m: self.handle_human_move(move)
                )
                btn_m.pack(side="left", padx=2)

        if self.game.game_over:
            self.last_move_label.config(text=f"GAME OVER: {self.game.win_reason}", fg="#fbbf24")
            self.log(f"🏆 [GAME OVER] {self.game.win_reason}")
            if self.is_auto_playing:
                self.toggle_auto_play()

    def format_move_text(self, move):
        action_type = move[0]
        player = self.game.get_active_player()
        if action_type == 'play_pokemon':
            card = player.hand[move[1]]
            return f"Bench {card.name}"
        elif action_type == 'evolve':
            card = player.hand[move[1]]
            return f"Evolve {card.name}"
        elif action_type == 'use_pokemon_ability':
            return f"Ability: {move[2]}"
        elif action_type == 'play_item':
            card = player.hand[move[1]]
            ace_str = " [ACE]" if card.is_ace_spec else ""
            return f"Item {card.name}{ace_str}"
        elif action_type == 'attach_tool':
            card = player.hand[move[1]]
            tgt = "Active" if move[2] == 0 else f"Bench {move[2]}"
            return f"Tool {card.name} -> {tgt}"
        elif action_type == 'play_stadium':
            card = player.hand[move[1]]
            return f"Stadium {card.name}"
        elif action_type == 'use_stadium_ability':
            return "Use Stadium"
        elif action_type == 'attach_energy':
            card = player.hand[move[1]]
            tgt = "Active" if move[2] == 0 else f"Bench {move[2]}"
            return f"Attach {card.name} -> {tgt}"
        elif action_type == 'play_supporter':
            card = player.hand[move[1]]
            return f"Use {card.name}"
        elif action_type == 'attack':
            atk = player.active_pokemon.attacks[move[1]]
            return f"Attack: {atk['name']} ({atk['damage']}dmg)"
        elif action_type == 'retreat':
            return f"Retreat -> Bench {move[1]}"
        elif action_type == 'pass':
            return "Pass Turn"
        return str(move)

    def handle_human_move(self, move):
        turn_ended = self.game.handle_action(move, verbose=False)
        self.last_move_label.config(text=f"You chose: {self.format_move_text(move)}")
        self.log(f"(P1 - Human) chose: {self.format_move_text(move)}")

        if turn_ended and not self.game.game_over:
            self.game.switch_turns(verbose=False)

        self.update_view()

    def step_action(self):
        if not self.game or self.game.game_over:
            return

        legal_moves = self.game.get_legal_moves()
        if not legal_moves:
            return

        if self.mode == "human_vs_mcts" and self.game.active_player_index == 0:
            return

        if self.game.active_player_index == 0:
            chosen_move = self.mcts.choose_action(self.game, legal_moves)
            ai_name = "ISMCTS"
        else:
            chosen_move = self.greedy.choose_action(self.game, legal_moves)
            ai_name = "GreedyAI"

        formatted_txt = self.format_move_text(chosen_move)
        turn_ended = self.game.handle_action(chosen_move, verbose=False)
        p_id = "P1" if self.game.active_player_index == 0 else "P2"
        self.last_move_label.config(text=f"{p_id} ({ai_name}) chose: {formatted_txt}")
        self.log(f"({p_id} - {ai_name}) chose: {formatted_txt}")

        if turn_ended and not self.game.game_over:
            self.game.switch_turns(verbose=False)

        self.update_view()

    def toggle_auto_play(self):
        self.is_auto_playing = not self.is_auto_playing
        if self.is_auto_playing:
            self.btn_auto.config(text="⏸️ Pause", bg="#d97706")
            self.run_auto_loop()
        else:
            self.btn_auto.config(text="⏩ Auto", bg="#334155")

    def run_auto_loop(self):
        if not self.is_auto_playing or not self.game or self.game.game_over:
            if self.is_auto_playing:
                self.toggle_auto_play()
            return

        self.step_action()
        self.root.after(self.auto_speed_ms, self.run_auto_loop)

    def open_tournament_window(self):
        tourney_win = tk.Toplevel(self.root)
        tourney_win.title("Standard Format Tournament Matrix Simulator")
        tourney_win.geometry("900x600")
        tourney_win.configure(bg="#0f172a")

        header = tk.Label(
            tourney_win,
            text="🏆 Standard Meta Round-Robin Tournament Matrix",
            font=("Segoe UI", 12, "bold"),
            fg="#f8fafc", bg="#0f172a"
        )
        header.pack(pady=10)

        tree = ttk.Treeview(tourney_win, columns=("Rank", "Archetype", "Tier", "Record", "WinRate", "PrizeDiff"), show="headings", height=10)
        tree.heading("Rank", text="Rank")
        tree.heading("Archetype", text="Archetype")
        tree.heading("Tier", text="Tier")
        tree.heading("Record", text="Record (W-L-D)")
        tree.heading("WinRate", text="Win Rate")
        tree.heading("PrizeDiff", text="Prize Diff")

        tree.column("Rank", width=50, anchor="center")
        tree.column("Archetype", width=180, anchor="w")
        tree.column("Tier", width=80, anchor="center")
        tree.column("Record", width=120, anchor="center")
        tree.column("WinRate", width=90, anchor="center")
        tree.column("PrizeDiff", width=90, anchor="center")
        tree.pack(fill="both", expand=True, padx=12, pady=6)

        status_lbl = tk.Label(tourney_win, text="Click 'Start Tournament' to run multi-deck simulation.", font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a")
        status_lbl.pack(pady=4)

        def run_sim_thread():
            status_lbl.config(text="Simulating Round-Robin Tournament... Please wait.", fg="#f59e0b")
            runner = TournamentMatrixRunner(
                card_factory=self.factory,
                games_per_matchup=2,
                c1_kwargs={"iteration_limit": 60, "simulation_depth": 6}
            )
            res = runner.run_round_robin(verbose=False)
            
            for item in tree.get_children():
                tree.delete(item)

            for rank, d in enumerate(res["ranked_decks"], 1):
                s = res["overall_stats"][d]
                total = max(1, s["total"])
                wr = (s["wins"] / total) * 100
                diff = s["prizes_taken"] - s["prizes_lost"]
                tier = "Tier S" if wr >= 60.0 else ("Tier 1" if wr >= 50.0 else "Tier 2")
                record_str = f"{s['wins']}-{s['losses']}-{s['draws']}"
                tree.insert("", "end", values=(rank, d, tier, record_str, f"{wr:.1f}%", f"{diff:+d}"))

            status_lbl.config(text=f"Tournament Complete! {len(res['ranked_decks'])} archetypes evaluated in {res['elapsed_seconds']:.2f}s.", fg="#10b981")

        btn_run = tk.Button(
            tourney_win, text="🚀 Start Tournament Simulation", font=("Segoe UI", 10, "bold"),
            bg="#059669", fg="#ffffff", activebackground="#10b981", activeforeground="#ffffff",
            relief="flat", padx=12, pady=6, cursor="hand2", command=lambda: threading.Thread(target=run_sim_thread, daemon=True).start()
        )
        btn_run.pack(pady=10)


def main():
    root = tk.Tk()
    app = PokemonTCGGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

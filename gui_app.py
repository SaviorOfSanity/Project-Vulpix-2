"""
Pokémon TCG Simulator, Deck Builder, AI Coach & Tournament Suite (Standard Format)
GUI framework: Standard tkinter.
Integrates:
1. Multi-Tier AI Opponents (Casual, Competitor, Championship Master).
2. Live AI Coach & Blunder Analysis Engine.
3. Deck Builder from Scratch & PTCGL Import/Export.
4. Anti-Meta Tournament EV Optimizer.
5. Strategic Matchup Guide & Prize-Map Generator.
6. Full Meta Gauntlet & Tournament Matrix.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import threading
import time

# Import live game modules
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
Player = game_engine.Player
GameState = game_engine.GameState
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES
TournamentMatrixRunner = game_engine.TournamentMatrixRunner

from deck_builder import DeckBuilder, DeckValidator, AntiMetaOptimizer
from meta_gauntlet import MetaGauntlet
from ai_opponents import CasualAI, CompetitorAI, ChampionshipMasterAI, AIOpponentFactory
from ai_coach import AICoach
from strategy_planner import StrategyPlanner

ARCHETYPES = STANDARD_ARCHETYPES


class PokemonTCGGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vulpix AI: Pokémon TCG Simulator, Deck Builder & Championship Coach Suite")
        self.root.geometry("1400x950")
        self.root.minsize(1160, 840)
        self.root.configure(bg="#0f172a")

        # Core Engines
        self.factory = CardFactory('cards.json')
        self.builder = DeckBuilder(self.factory)
        self.gauntlet = MetaGauntlet(self.factory)
        self.coach = AICoach(self.factory, coach_iterations=120, coach_depth=8)
        self.planner = StrategyPlanner(self.factory)
        self.optimizer = AntiMetaOptimizer(self.factory)

        self.p1_archetype_name = "Gardevoir ex"
        self.p2_archetype_name = "Terapagos ex"
        self.ai_tier = "Competitor"

        self.game = None
        self.is_auto_playing = False
        self.auto_speed_ms = 600
        self.mode = "human_vs_mcts"

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
        # 1. Top Navigation & Global Controls Bar
        top_bar = tk.Frame(self.root, bg="#1e293b", padx=10, pady=8, relief="groove", bd=1)
        top_bar.pack(side="top", fill="x")

        title_label = tk.Label(
            top_bar,
            text="⚡ Vulpix TCG Championship Suite",
            font=("Segoe UI", 12, "bold"),
            fg="#f8fafc",
            bg="#1e293b"
        )
        title_label.pack(side="left", padx=4)

        # Mode Selector
        self.mode_var = tk.StringVar(value="human_vs_mcts")
        mode_btn1 = tk.Radiobutton(
            top_bar, text="Human vs AI", variable=self.mode_var, value="human_vs_mcts",
            command=self.on_mode_change, bg="#1e293b", fg="#94a3b8", selectcolor="#0f172a",
            activebackground="#1e293b", activeforeground="#f8fafc", font=("Segoe UI", 8, "bold")
        )
        mode_btn1.pack(side="left", padx=2)

        mode_btn2 = tk.Radiobutton(
            top_bar, text="AI vs AI", variable=self.mode_var, value="ai_vs_ai",
            command=self.on_mode_change, bg="#1e293b", fg="#94a3b8", selectcolor="#0f172a",
            activebackground="#1e293b", activeforeground="#f8fafc", font=("Segoe UI", 8, "bold")
        )
        mode_btn2.pack(side="left", padx=2)

        # AI Tier Selector
        tk.Label(top_bar, text="AI Tier:", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(6, 2))
        self.ai_tier_combo = ttk.Combobox(top_bar, values=["Casual", "Competitor", "Championship Master"], state="readonly", width=16, font=("Segoe UI", 8))
        self.ai_tier_combo.set(self.ai_tier)
        self.ai_tier_combo.pack(side="left", padx=2)
        self.ai_tier_combo.bind("<<ComboboxSelected>>", self.on_ai_tier_change)

        # Deck Pickers
        tk.Label(top_bar, text="P1:", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(6, 2))
        self.p1_combo = ttk.Combobox(top_bar, values=list(ARCHETYPES.keys()), state="readonly", width=14, font=("Segoe UI", 8))
        self.p1_combo.set(self.p1_archetype_name)
        self.p1_combo.pack(side="left", padx=2)
        self.p1_combo.bind("<<ComboboxSelected>>", self.on_archetype_change)

        tk.Label(top_bar, text="P2:", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(4, 2))
        self.p2_combo = ttk.Combobox(top_bar, values=list(ARCHETYPES.keys()), state="readonly", width=14, font=("Segoe UI", 8))
        self.p2_combo.set(self.p2_archetype_name)
        self.p2_combo.pack(side="left", padx=2)
        self.p2_combo.bind("<<ComboboxSelected>>", self.on_archetype_change)

        # Action Buttons
        btn_new = tk.Button(
            top_bar, text="🔄 Reset", font=("Segoe UI", 8, "bold"),
            bg="#059669", fg="#ffffff", relief="flat", padx=6, pady=2, cursor="hand2", command=self.start_new_match
        )
        btn_new.pack(side="left", padx=2)

        self.btn_step = tk.Button(
            top_bar, text="▶️ Step", font=("Segoe UI", 8, "bold"),
            bg="#4f46e5", fg="#ffffff", relief="flat", padx=6, pady=2, cursor="hand2", command=self.step_action
        )
        self.btn_step.pack(side="left", padx=2)

        self.btn_auto = tk.Button(
            top_bar, text="⏩ Auto", font=("Segoe UI", 8, "bold"),
            bg="#334155", fg="#ffffff", relief="flat", padx=6, pady=2, cursor="hand2", command=self.toggle_auto_play
        )
        self.btn_auto.pack(side="left", padx=2)

        # Feature Tools Buttons
        btn_builder = tk.Button(
            top_bar, text="🛠️ Deck Builder", font=("Segoe UI", 8, "bold"),
            bg="#0284c7", fg="#ffffff", relief="flat", padx=6, pady=2, cursor="hand2", command=self.open_deck_builder_window
        )
        btn_builder.pack(side="left", padx=2)

        btn_plan = tk.Button(
            top_bar, text="📋 Gameplan", font=("Segoe UI", 8, "bold"),
            bg="#7c3aed", fg="#ffffff", relief="flat", padx=6, pady=2, cursor="hand2", command=self.open_gameplan_window
        )
        btn_plan.pack(side="left", padx=2)

        btn_gauntlet = tk.Button(
            top_bar, text="🛡️ Gauntlet", font=("Segoe UI", 8, "bold"),
            bg="#d97706", fg="#ffffff", relief="flat", padx=6, pady=2, cursor="hand2", command=self.open_gauntlet_window
        )
        btn_gauntlet.pack(side="left", padx=2)

        # Speed Slider
        self.slider_speed = tk.Scale(
            top_bar, from_=100, to=1500, orient="horizontal", bg="#1e293b", fg="#94a3b8",
            highlightthickness=0, length=50, showvalue=0, command=self.on_speed_change
        )
        self.slider_speed.set(600)
        self.slider_speed.pack(side="left", padx=2)

        # 2. Main Content Split
        content_frame = tk.Frame(self.root, bg="#0f172a", padx=8, pady=4)
        content_frame.pack(fill="both", expand=True)

        left_playmat = tk.Frame(content_frame, bg="#0f172a")
        left_playmat.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right_panel = tk.Frame(content_frame, bg="#0f172a", width=380)
        right_panel.pack(side="right", fill="both", expand=False)

        # --- PLAYMAT: OPPONENT (P2) ---
        self.p2_card_frame = tk.LabelFrame(
            left_playmat, text=" Opponent: Player 2 ", font=("Segoe UI", 9, "bold"),
            bg="#1e293b", fg="#f43f5e", relief="groove", bd=1, padx=6, pady=4
        )
        self.p2_card_frame.pack(fill="x", pady=(0, 2))

        self.p2_stats_label = tk.Label(self.p2_card_frame, text="", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b")
        self.p2_stats_label.pack(anchor="w")

        p2_board_row = tk.Frame(self.p2_card_frame, bg="#1e293b")
        p2_board_row.pack(fill="x", pady=2)

        self.p2_active_label = tk.Label(
            p2_board_row, text="Active: (None)", font=("Segoe UI", 8, "bold"),
            bg="#0f172a", fg="#f8fafc", relief="ridge", bd=2, width=32, height=4, justify="center"
        )
        self.p2_active_label.pack(side="left", padx=4)

        self.p2_bench_label = tk.Label(
            p2_board_row, text="Bench: (Empty)", font=("Segoe UI", 8),
            bg="#0f172a", fg="#cbd5e1", relief="ridge", bd=1, height=4, justify="left", anchor="nw", padx=6, pady=2
        )
        self.p2_bench_label.pack(side="left", fill="both", expand=True, padx=4)

        # --- CENTER STATUS BANNER ---
        self.center_banner = tk.Frame(left_playmat, bg="#1e1b4b", padx=8, pady=4, relief="groove", bd=1)
        self.center_banner.pack(fill="x", pady=2)

        self.turn_status_label = tk.Label(
            self.center_banner, text="Turn 1 | Active Player: P1",
            font=("Segoe UI", 8, "bold"), fg="#a5b4fc", bg="#1e1b4b"
        )
        self.turn_status_label.pack(side="left")

        self.stadium_label = tk.Label(
            self.center_banner, text="Stadium: (None)",
            font=("Segoe UI", 8, "bold"), fg="#34d399", bg="#1e1b4b"
        )
        self.stadium_label.pack(side="left", padx=10)

        self.last_move_label = tk.Label(
            self.center_banner, text="Game Initialized.",
            font=("Segoe UI", 8, "italic"), fg="#f8fafc", bg="#1e1b4b"
        )
        self.last_move_label.pack(side="right")

        # --- PLAYMAT: PLAYER 1 (Human / Coach) ---
        self.p1_card_frame = tk.LabelFrame(
            left_playmat, text=" Player 1 (You) ", font=("Segoe UI", 9, "bold"),
            bg="#1e293b", fg="#6366f1", relief="groove", bd=1, padx=6, pady=4
        )
        self.p1_card_frame.pack(fill="x", pady=(2, 0))

        p1_board_row = tk.Frame(self.p1_card_frame, bg="#1e293b")
        p1_board_row.pack(fill="x", pady=2)

        self.p1_active_label = tk.Label(
            p1_board_row, text="Active: (None)", font=("Segoe UI", 8, "bold"),
            bg="#0f172a", fg="#f8fafc", relief="ridge", bd=2, width=32, height=4, justify="center"
        )
        self.p1_active_label.pack(side="left", padx=4)

        self.p1_bench_label = tk.Label(
            p1_board_row, text="Bench: (Empty)", font=("Segoe UI", 8),
            bg="#0f172a", fg="#cbd5e1", relief="ridge", bd=1, height=4, justify="left", anchor="nw", padx=6, pady=2
        )
        self.p1_bench_label.pack(side="left", fill="both", expand=True, padx=4)

        self.p1_stats_label = tk.Label(self.p1_card_frame, text="", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b")
        self.p1_stats_label.pack(anchor="w", pady=(1, 0))

        self.p1_hand_frame = tk.Frame(self.p1_card_frame, bg="#0f172a", padx=6, pady=2, relief="sunken", bd=1)
        self.p1_hand_frame.pack(fill="x", pady=2)
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

        # --- RIGHT SIDE: AI COACH & TELEMETRY ---
        coach_box = tk.LabelFrame(
            right_panel, text=" 🧠 AI Coach & Tactical Recommendations ", font=("Segoe UI", 9, "bold"),
            bg="#1e293b", fg="#38bdf8", relief="groove", bd=1, padx=8, pady=6
        )
        coach_box.pack(fill="x", pady=(0, 4))

        self.coach_rec_label = tk.Label(
            coach_box, text="Calculating top lines...", font=("Segoe UI", 8),
            fg="#f8fafc", bg="#1e293b", justify="left", wraplength=350
        )
        self.coach_rec_label.pack(anchor="w", pady=2)

        self.blunder_alert_label = tk.Label(
            coach_box, text="Grade: Ready", font=("Segoe UI", 8, "bold"),
            fg="#10b981", bg="#1e293b"
        )
        self.blunder_alert_label.pack(anchor="w")

        mcts_box = tk.LabelFrame(
            right_panel, text=" Advantage Evaluation ", font=("Segoe UI", 8, "bold"),
            bg="#1e293b", fg="#a5b4fc", relief="groove", bd=1, padx=6, pady=4
        )
        mcts_box.pack(fill="x", pady=(0, 4))

        self.score_display_label = tk.Label(
            mcts_box, text="Advantage: +0.000", font=("Segoe UI", 9, "bold"),
            fg="#10b981", bg="#1e293b"
        )
        self.score_display_label.pack(anchor="w")

        self.progress_advantage = ttk.Progressbar(mcts_box, orient="horizontal", mode="determinate", maximum=2.0)
        self.progress_advantage.pack(fill="x", pady=2)
        self.progress_advantage['value'] = 1.0

        log_box = tk.LabelFrame(
            right_panel, text=" Move-by-Move Telemetry Log ", font=("Segoe UI", 8, "bold"),
            bg="#1e293b", fg="#f8fafc", relief="groove", bd=1, padx=4, pady=4
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

    def on_ai_tier_change(self, event=None):
        self.ai_tier = self.ai_tier_combo.get()
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

        c1 = AIOpponentFactory.create_opponent(self.ai_tier) if self.mode == "ai_vs_ai" else None
        c2 = AIOpponentFactory.create_opponent(self.ai_tier)

        d1_list = ARCHETYPES[self.p1_archetype_name]
        d2_list = ARCHETYPES[self.p2_archetype_name]

        p1_name = f"P1 [{self.p1_archetype_name}]"
        p2_name = f"P2 [{self.p2_archetype_name}] ({self.ai_tier} AI)"

        p1 = Player(p1_name, d1_list, self.factory, controller=c1)
        p2 = Player(p2_name, d2_list, self.factory, controller=c2)

        self.game = GameState(p1, p2)
        self.game.setup_game(verbose=False)

        self.log(f"=== New Match: {p1.name} vs {p2.name} ===")
        self.update_view()

    def format_card_info(self, p_card):
        if not p_card:
            return "(None)"
        eff_max = p_card.get_effective_max_hp()
        cur_hp = eff_max - p_card.damage_counters
        energy_count = sum(getattr(e, 'energy_units', 1) for e in p_card.attached_energy)
        ex_str = f" [EX {p_card.prize_yield}P]" if p_card.is_rule_box else ""
        cond_str = f" [Cond: {', '.join(k.value for k in p_card.special_conditions)}]" if p_card.special_conditions else ""
        ab_str = f" [Ability: {p_card.ability['name']}]" if p_card.ability else ""
        atks = ", ".join([f"{a['name']} ({a['damage']}dmg)" for a in p_card.attacks])
        return f"{p_card.name}{ex_str}{cond_str}{ab_str}\nHP: {cur_hp}/{eff_max} | Energy: {energy_count}⚡\nAttacks: {atks}"

    def update_view(self):
        if not self.game:
            return

        p1 = self.game.players[0]
        p2 = self.game.players[1]
        active_p = self.game.get_active_player()

        self.turn_status_label.config(text=f"Turn {self.game.turn_number + 1} | Active: {active_p.name}")
        stadium_name = self.game.active_stadium.name if self.game.active_stadium else "None"
        self.stadium_label.config(text=f"Stadium: {stadium_name}")

        # Opponent (P2)
        self.p2_stats_label.config(text=f"Deck: {len(p2.deck)} | Hand: {len(p2.hand)} | Prizes: {len(p2.prize_cards)}")
        self.p2_active_label.config(text=f"ACTIVE: {self.format_card_info(p2.active_pokemon)}")
        p2_bench_str = "\n".join([f"• {self.format_card_info(p)}" for p in p2.bench]) or "(Bench Empty)"
        self.p2_bench_label.config(text=f"BENCH ({len(p2.bench)}/{p2.get_max_bench_size(self.game)}):\n{p2_bench_str}")

        # Player 1 (P1)
        self.p1_stats_label.config(text=f"Deck: {len(p1.deck)} | Hand: {len(p1.hand)} | Prizes: {len(p1.prize_cards)}")
        self.p1_active_label.config(text=f"ACTIVE: {self.format_card_info(p1.active_pokemon)}")
        p1_bench_str = "\n".join([f"• {self.format_card_info(p)}" for p in p1.bench]) or "(Bench Empty)"
        self.p1_bench_label.config(text=f"BENCH ({len(p1.bench)}/{p1.get_max_bench_size(self.game)}):\n{p1_bench_str}")
        p1_hand_str = " | ".join([c.name + (" [ACE]" if c.is_ace_spec else "") for c in p1.hand]) or "(Hand Empty)"
        self.p1_hand_label.config(text=f"HAND ({len(p1.hand)}): {p1_hand_str}")

        # Live Coach Recommendations on Player's Turn
        if self.game.active_player_index == 0 and not self.game.game_over:
            coach_eval = self.coach.evaluate_turn(self.game, top_n=3)
            recs = coach_eval["recommended_moves"]
            rec_text = "🎯 TOP RECOMMENDED MOVES:\n"
            for i, r in enumerate(recs, 1):
                rec_text += f"{i}. {r['description']} (EV: {r['score']:+.2f})\n"
            self.coach_rec_label.config(text=rec_text)
            self.score_display_label.config(text=f"Advantage: {coach_eval['current_eval']:+.3f}")
            self.progress_advantage['value'] = coach_eval['current_eval'] + 1.0

        for widget in self.human_actions_frame.winfo_children():
            widget.destroy()

        if self.mode == "human_vs_mcts" and self.game.active_player_index == 0 and not self.game.game_over:
            moves = self.game.get_legal_moves()
            lbl_pick = tk.Label(self.human_actions_frame, text="Your Move:", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#0f172a")
            lbl_pick.pack(side="left", padx=2)
            for m in moves[:6]:
                btn_m = tk.Button(
                    self.human_actions_frame, text=self.coach.get_action_description(self.game, m)[:35], font=("Segoe UI", 8),
                    bg="#1e293b", fg="#f8fafc", relief="groove", padx=4, pady=2, cursor="hand2", command=lambda move=m: self.handle_human_move(move)
                )
                btn_m.pack(side="left", padx=1)

        if self.game.game_over:
            self.last_move_label.config(text=f"GAME OVER: {self.game.win_reason}", fg="#fbbf24")
            self.log(f"🏆 [GAME OVER] {self.game.win_reason}")
            if self.is_auto_playing:
                self.toggle_auto_play()

    def handle_human_move(self, move):
        # Run Blunder Analysis before applying
        analysis = self.coach.analyze_player_move(self.game, move)
        self.blunder_alert_label.config(
            text=f"Grade: {analysis['grade']} | {analysis['comment']}",
            fg="#10b981" if analysis['grade'] in ("Best Move", "Good Move") else "#f43f5e"
        )

        turn_ended = self.game.handle_action(move, verbose=False)
        desc = self.coach.get_action_description(self.game, move)
        self.last_move_label.config(text=f"You chose: {desc}")
        self.log(f"(P1 - You) [{analysis['grade']}]: {desc}")

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

        p = self.game.get_active_player()
        chosen_move = p.controller.choose_action(self.game, legal_moves)

        desc = self.coach.get_action_description(self.game, chosen_move)
        turn_ended = self.game.handle_action(chosen_move, verbose=False)
        p_id = "P1" if self.game.active_player_index == 0 else "P2"
        self.last_move_label.config(text=f"{p_id} chose: {desc}")
        self.log(f"({p_id}) chose: {desc}")

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

    def open_deck_builder_window(self):
        win = tk.Toplevel(self.root)
        win.title("Vulpix Deck Builder & Anti-Meta EV Optimizer")
        win.geometry("850x650")
        win.configure(bg="#0f172a")

        header = tk.Label(win, text="🛠️ Deck Generator, Scratch Builder & Anti-Meta Optimizer", font=("Segoe UI", 12, "bold"), fg="#f8fafc", bg="#0f172a")
        header.pack(pady=8)

        f_inputs = tk.Frame(win, bg="#1e293b", padx=10, pady=8, relief="groove", bd=1)
        f_inputs.pack(fill="x", padx=12, pady=4)

        tk.Label(f_inputs, text="Primary Attacker / Concept:", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b").grid(row=0, column=0, sticky="w")
        attacker_entry = tk.Entry(f_inputs, width=24, font=("Segoe UI", 9), bg="#0f172a", fg="#f8fafc")
        attacker_entry.insert(0, "Ceruledge ex")
        attacker_entry.grid(row=0, column=1, padx=6, pady=2)

        tk.Label(f_inputs, text="Preferred ACE SPEC:", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b").grid(row=0, column=2, sticky="w", padx=(10, 0))
        ace_entry = tk.Entry(f_inputs, width=20, font=("Segoe UI", 9), bg="#0f172a", fg="#f8fafc")
        ace_entry.insert(0, "Grand Tree")
        ace_entry.grid(row=0, column=3, padx=6, pady=2)

        deck_display = scrolledtext.ScrolledText(win, width=85, height=18, font=("Consolas", 9), bg="#0f172a", fg="#f1f5f9")
        deck_display.pack(fill="both", expand=True, padx=12, pady=6)

        def generate_scratch():
            atk = attacker_entry.get().strip()
            ace = ace_entry.get().strip() or None
            try:
                deck = self.builder.generate_deck_from_scratch(atk, preferred_ace_spec=ace)
                ptcgl_txt = self.builder.export_to_ptcgl(deck)
                deck_display.delete("1.0", "end")
                deck_display.insert("end", f"// Generated Legal 60-Card Deck for {atk}\n\n" + ptcgl_txt)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def run_anti_meta():
            deck_display.delete("1.0", "end")
            deck_display.insert("end", "Analyzing Tournament Meta Distribution & Optimizing EV Counter-Deck... Please wait.\n")
            win.update()
            
            target_meta = {"Charizard ex": 0.40, "Gardevoir ex": 0.30, "Ceruledge ex": 0.30}
            res = self.optimizer.optimize_anti_meta_deck(target_meta, sample_games_per_eval=2, mcts_iterations=30)
            ptcgl_txt = self.builder.export_to_ptcgl(res["best_decklist"])
            deck_display.delete("1.0", "end")
            deck_display.insert("end", f"// [TOP EV ANTI-META DECK] {res['best_deck_name']}\n// Expected Win Rate: {res['expected_winrate']*100:.1f}%\n\n" + ptcgl_txt)

        btn_row = tk.Frame(win, bg="#0f172a")
        btn_row.pack(pady=8)

        tk.Button(btn_row, text="⚡ Generate Deck from Scratch", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="#ffffff", padx=10, pady=4, command=generate_scratch).pack(side="left", padx=4)
        tk.Button(btn_row, text="🎯 Optimize Anti-Meta Counter Deck", font=("Segoe UI", 9, "bold"), bg="#059669", fg="#ffffff", padx=10, pady=4, command=run_anti_meta).pack(side="left", padx=4)

    def open_gameplan_window(self):
        win = tk.Toplevel(self.root)
        win.title("Strategic Matchup Guide & Prize-Mapping Engine")
        win.geometry("850x650")
        win.configure(bg="#0f172a")

        header = tk.Label(win, text=f"📋 Matchup Strategy Guide: {self.p1_archetype_name} vs {self.p2_archetype_name}", font=("Segoe UI", 12, "bold"), fg="#f8fafc", bg="#0f172a")
        header.pack(pady=8)

        display = scrolledtext.ScrolledText(win, width=85, height=24, font=("Consolas", 9), bg="#0f172a", fg="#f1f5f9")
        display.pack(fill="both", expand=True, padx=12, pady=6)

        plan = self.planner.generate_gameplan(
            my_deck=ARCHETYPES[self.p1_archetype_name],
            my_deck_name=self.p1_archetype_name,
            opp_deck=ARCHETYPES[self.p2_archetype_name],
            opp_deck_name=self.p2_archetype_name
        )

        txt = (
            f"=== STRATEGIC MATCHUP GUIDE: {plan['matchup_title']} ===\n\n"
            f"[PRIZE MAP ROADMAP]\n{plan['prize_map_plan']}\n\n"
            f"[TURN 1-2 SETUP PRIORITIES]\n- {plan['turn_1_2_setup']}\n\n"
            f"[THREAT WARNINGS & COUNTERS]\n" + "\n".join([f"- {w}" for w in plan['threat_warnings']]) + "\n\n"
            f"[DOS]\n" + "\n".join([f"- {d}" for d in plan['dos']]) + "\n\n"
            f"[DONTS]\n" + "\n".join([f"- {d}" for d in plan['donts']])
        )
        display.insert("end", txt)

    def open_gauntlet_window(self):
        win = tk.Toplevel(self.root)
        win.title("Standard Format Meta Gauntlet Simulator")
        win.geometry("900x600")
        win.configure(bg="#0f172a")

        header = tk.Label(win, text=f"🛡️ Testing '{self.p1_archetype_name}' against Full Standard Meta Gauntlet", font=("Segoe UI", 12, "bold"), fg="#f8fafc", bg="#0f172a")
        header.pack(pady=8)

        tree = ttk.Treeview(win, columns=("Opponent", "Class", "Record", "WinRate", "PrizeDiff"), show="headings", height=10)
        tree.heading("Opponent", text="Opponent Archetype")
        tree.heading("Class", text="Classification")
        tree.heading("Record", text="Record (W-L-D)")
        tree.heading("WinRate", text="Win Rate")
        tree.heading("PrizeDiff", text="Prize Diff")

        tree.column("Opponent", width=180, anchor="w")
        tree.column("Class", width=110, anchor="center")
        tree.column("Record", width=110, anchor="center")
        tree.column("WinRate", width=90, anchor="center")
        tree.column("PrizeDiff", width=90, anchor="center")
        tree.pack(fill="both", expand=True, padx=12, pady=6)

        status_lbl = tk.Label(win, text="Click 'Run Gauntlet' to simulate candidate deck against all archetypes.", font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a")
        status_lbl.pack(pady=4)

        def run_gauntlet_thread():
            status_lbl.config(text="Running Gauntlet simulations... Please wait.", fg="#f59e0b")
            deck = ARCHETYPES[self.p1_archetype_name]
            res = self.gauntlet.run_gauntlet(deck, custom_deck_name=self.p1_archetype_name, games_per_matchup=2, mcts_iterations=50)

            for item in tree.get_children():
                tree.delete(item)

            for opp_name, data in res["matchup_breakdown"].items():
                tree.insert("", "end", values=(opp_name, data["classification"], data["record"], f"{data['win_rate']:.1f}%", f"{data['prize_diff']:+d}"))

            status_lbl.config(text=f"Gauntlet Complete! Overall Record: {res['overall_record']} ({res['overall_win_rate']:.1f}%) | {res['meta_tier']}", fg="#10b981")

        tk.Button(win, text="🚀 Run Meta Gauntlet", font=("Segoe UI", 9, "bold"), bg="#d97706", fg="#ffffff", padx=12, pady=4, command=lambda: threading.Thread(target=run_gauntlet_thread, daemon=True).start()).pack(pady=8)


def main():
    root = tk.Tk()
    app = PokemonTCGGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

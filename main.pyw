import tkinter as tk
from time import time
from dataclasses import dataclass
from typing import Callable
import json
from pathlib import Path
from datetime import datetime


class Theme:
    BG = "#050505"
    FG = "#34d399"
    ACCENT = "#10b981"
    WARN = "#f59e0b"
    CRITICAL = "#ef4444"
    FONT_H = ("Segoe UI", 24, "bold")
    FONT_P = ("Segoe UI", 11)
    FONT_MONO = ("Consolas", 10)


@dataclass
class Session:
    intent: str = ""
    total_sec: float = 0
    start_at: float = 0
    paused_at: float | None = None
    total_paused: float = 0

    # New: cap is based on ORIGINAL planned duration only
    planned_sec: float = 0
    extended_sec: float = 0

    @property
    def current_pause_sec(self) -> float:
        return (time() - self.paused_at) if self.paused_at else 0.0

    @property
    def effective_elapsed_sec(self) -> float:
        return (time() - self.start_at) - self.total_paused - self.current_pause_sec

    @property
    def remaining_sec(self) -> float:
        return self.total_sec - self.effective_elapsed_sec

    @property
    def progress(self) -> float:
        if self.total_sec <= 0:
            return 0.0
        return max(0.0, min(1.0, self.effective_elapsed_sec / self.total_sec))

    @property
    def extend_cap_sec(self) -> float:
        # New rule: max(15, set/2) minutes, based on ORIGINAL planned duration only
        return max(15 * 60, self.planned_sec / 2)

    @property
    def extend_remaining_sec(self) -> float:
        return max(0.0, self.extend_cap_sec - self.extended_sec)

    def can_extend_min(self, mins: int) -> bool:
        return mins * 60 <= self.extend_remaining_sec


class VibeGate(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GateKeeper")
        self.configure(bg=Theme.BG)
        self.attributes("-topmost", True)  # type: ignore
        self.overrideredirect(True)

        self.session = Session()
        self.status = "VOID"

        self.history_path = Path("gate_keeper_history.json")
        self.history: list[dict] = self._load_history()

        # Progress bar runtime refs
        self.progress_canvas: tk.Canvas | None = None
        self.progress_fill_id: int | None = None

        self._active_bindings: list[str] = []

        # Drag mechanics
        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.do_drag)

        self.stage = tk.Frame(self, bg=Theme.BG)
        self.stage.pack(expand=True, fill="both")

        self.to_void()
        self.tick()

    # --- Window Logic ---
    def start_drag(self, event: tk.Event):
        self.x = event.x
        self.y = event.y

    def do_drag(self, event: tk.Event):
        if self.status == "VOID":
            return
        dx = event.x - self.x
        dy = event.y - self.y
        x = self.winfo_x() + dx
        y = self.winfo_y() + dy
        self.geometry(f"+{x}+{y}")

    def _clear_bindings(self):
        """Unbind all tracked event handlers"""
        for seq in self._active_bindings:
            self.unbind(seq)
        self._active_bindings.clear()

    def _bind_tracked(self, sequence: str, func: Callable):
        """Bind and track for cleanup"""
        self.bind(sequence, func)
        self._active_bindings.append(sequence)

    def transition(self, target: str, size: tuple[int, int] | None = None):
        self.status = target
        self._clear_bindings()

        for w in self.stage.winfo_children():
            w.destroy()

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = size if size else (sw, sh)
        self.geometry(f"{w}x{h}+{int((sw - w) / 2)}+0")

    @staticmethod
    def _validate_float(value: str) -> bool:
        """Validate numeric input"""
        if not value:
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    # --- States ---
    def to_void(self):
        self.transition("VOID")

        tk.Label(
            self.stage, text="GOAL", font=Theme.FONT_MONO, fg=Theme.ACCENT, bg=Theme.BG
        ).pack(pady=(50, 5))

        ent_intent = tk.Entry(
            self.stage,
            font=Theme.FONT_H,
            fg=Theme.FG,
            bg=Theme.BG,
            bd=0,
            insertbackground=Theme.FG,
            justify="center",
        )
        ent_intent.pack(pady=8)
        ent_intent.focus_set()

        tk.Label(
            self.stage,
            text="MINUTES",
            font=Theme.FONT_MONO,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        ).pack(pady=(16, 5))

        def validation_core(p: str) -> bool:
            if p == "":
                return True
            try:
                float(p)
                return True
            except ValueError:
                return False

        vcmd = (self.register(validation_core), "%P")
        ent_time = tk.Entry(
            self.stage,
            font=Theme.FONT_H,
            fg=Theme.FG,
            bg=Theme.BG,
            bd=0,
            insertbackground=Theme.FG,
            justify="center",
            width=7,
            validate="key",
            validatecommand=vcmd,
        )
        ent_time.insert(0, "20")
        ent_time.pack(pady=8)

        # New: expanded preset buttons
        presets = [0.5, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180]
        preset_frame = tk.Frame(self.stage, bg=Theme.BG)
        preset_frame.pack(pady=(6, 12))

        for idx, mins in enumerate(presets):
            txt = f"{mins:g}"
            tk.Button(
                preset_frame,
                text=txt,
                command=lambda m=txt: (
                    ent_time.delete(0, "end"),
                    ent_time.insert(0, m),
                ),
                bg=Theme.BG,
                fg=Theme.FG,
                relief="flat",
                padx=6,
                pady=2,
            ).grid(row=idx // 6, column=idx % 6, padx=3, pady=3)

        def launch(_e: tk.Event | None = None):
            try:
                mins = float(ent_time.get() or 25)
                total = mins * 60
                self.session = Session(
                    intent=ent_intent.get() or "FOCUS",
                    total_sec=total,
                    planned_sec=total,  # cap baseline: original planned duration only
                    start_at=time(),
                )
                self.to_silent()
            except Exception as e:
                print(f"Launch error: {e}")

        self.bind("<Return>", launch)
        tk.Button(
            self.stage,
            text="ENGAGE",
            font=Theme.FONT_P,
            command=launch,
            bg=Theme.ACCENT,
            fg=Theme.BG,
            relief="flat",
            padx=30,
        ).pack(pady=16)

        # New: history list
        self._render_history_list()

    def to_silent(self):
        self.transition("SILENT", (240, 96))

        self.lbl_time = tk.Label(
            self.stage, text="--:--", font=Theme.FONT_H, fg=Theme.FG, bg=Theme.BG
        )
        self.lbl_time.pack(pady=(8, 2), expand=False)

        # New: simple progress bar
        self.progress_canvas = tk.Canvas(
            self.stage, width=200, height=8, bg=Theme.BG, highlightthickness=0, bd=0
        )
        self.progress_canvas.pack(pady=(0, 10))
        self.progress_canvas.create_rectangle(
            0, 0, 200, 8, outline=Theme.ACCENT, width=1
        )
        self.progress_fill_id = self.progress_canvas.create_rectangle(
            0, 0, 0, 8, fill=Theme.ACCENT, width=0
        )

        self.lbl_time.bind("<Button-1>", lambda e: self.toggle_pause())
        self.bind("<space>", lambda e: self.toggle_pause())
        self.bind("<Escape>", lambda e: self.to_void())

    def toggle_pause(self):
        if self.session.paused_at is None:
            self.session.paused_at = time()
            self.lbl_time.config(fg=Theme.WARN)
        else:
            self.session.total_paused += time() - self.session.paused_at
            self.session.paused_at = None
            self.lbl_time.config(fg=Theme.FG)

    def to_overtime(self):
        self.transition("OVERTIME", (420, 170))

        tk.Label(
            self.stage,
            text="LIMIT REACHED",
            font=Theme.FONT_MONO,
            fg=Theme.CRITICAL,
            bg=Theme.BG,
        ).pack(pady=(16, 6))

        remain_min = round(self.session.extend_remaining_sec / 60, 1)
        tk.Label(
            self.stage,
            text=f"EXTEND BUDGET LEFT: {remain_min:g} MIN",
            font=Theme.FONT_MONO,
            fg=Theme.WARN,
            bg=Theme.BG,
        ).pack(pady=(0, 10))

        btn_frame = tk.Frame(self.stage, bg=Theme.BG)
        btn_frame.pack(pady=6)

        def add_time(mins: int):
            if not self.session.can_extend_min(mins):
                return
            add_sec = mins * 60
            self.session.total_sec += add_sec
            self.session.extended_sec += add_sec
            self.to_silent()

        # Keep only RELEASE when budget exhausted
        options = [2, 5, 15]
        any_extend = False
        for mins in options:
            if self.session.can_extend_min(mins):
                any_extend = True
                tk.Button(
                    btn_frame,
                    text=f"+{mins} MIN",
                    command=lambda m=mins: add_time(m),
                    bg=Theme.BG,
                    fg=Theme.FG,
                    relief="flat",
                    padx=8,
                ).pack(side="left", padx=4)

        if not any_extend:
            tk.Label(
                self.stage,
                text="EXTEND CAP REACHED",
                font=Theme.FONT_MONO,
                fg=Theme.CRITICAL,
                bg=Theme.BG,
            ).pack(pady=(0, 8))

        def release():
            self._append_release_history()
            self.to_void()

        tk.Button(
            btn_frame,
            text="RELEASE",
            command=release,
            bg=Theme.CRITICAL,
            fg=Theme.BG,
            relief="flat",
            padx=20,
        ).pack(side="left", padx=4)

    def _start_tick(self):
        """Start the timer tick loop"""
        if self.tick_id is None:
            self.tick()

    def _stop_tick(self):
        """Stop the timer tick loop"""
        if self.tick_id:
            self.after_cancel(self.tick_id)
            self.tick_id = None

    def tick(self):
        if self.status == "SILENT":
            remaining = self.session.remaining_sec

            if remaining <= 0:
                self.to_overtime()
            else:
                m, s = divmod(abs(int(remaining)), 60)
                pause_icon = " ⏸" if self.session.paused_at else ""
                self.lbl_time.config(text=f"{m:02d}:{s:02d}{pause_icon}")

                # New: progress bar update
                if (
                    self.progress_canvas is not None
                    and self.progress_fill_id is not None
                ):
                    width = 200
                    fill_w = int(width * self.session.progress)
                    color = Theme.WARN if self.session.paused_at else Theme.ACCENT
                    self.progress_canvas.coords(self.progress_fill_id, 0, 0, fill_w, 8)
                    self.progress_canvas.itemconfig(self.progress_fill_id, fill=color)

        self.after(500, self.tick)

    def _load_history(self) -> list[dict]:
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_history(self) -> None:
        self.history_path.write_text(
            json.dumps(self.history[-200:], ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _append_release_history(self) -> None:
        # Log only on RELEASE (as requested)
        if self.session.start_at <= 0:
            return

        actual_focus_min = round(max(0.0, self.session.effective_elapsed_sec) / 60, 2)
        planned_min = round(self.session.planned_sec / 60, 2)
        overtime_min = round(max(0.0, actual_focus_min - planned_min), 2)

        self.history.append(
            {
                "released_at": datetime.now().isoformat(timespec="seconds"),
                "intent": self.session.intent or "FOCUS",
                "planned_min": planned_min,
                "actual_focus_min": actual_focus_min,
                "overtime_min": overtime_min,
                "status": "released",
            }
        )
        self._save_history()

    def _render_history_list(self) -> None:
        if not self.history:
            return

        tk.Label(
            self.stage,
            text="RECENT RELEASES",
            font=Theme.FONT_MONO,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        ).pack(pady=(20, 6))

        box = tk.Frame(self.stage, bg=Theme.BG)
        box.pack(pady=(0, 12))

        for row in reversed(self.history[-8:]):
            line = (
                f"{row.get('released_at', '')[-8:]}  "
                f"{row.get('intent', 'FOCUS')}  "
                f"{row.get('actual_focus_min', 0)}m"
            )
            tk.Label(
                box,
                text=line,
                font=Theme.FONT_MONO,
                fg=Theme.FG,
                bg=Theme.BG,
                anchor="w",
                justify="left",
            ).pack(fill="x")


if __name__ == "__main__":
    VibeGate().mainloop()

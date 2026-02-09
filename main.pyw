from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import time
from typing import Callable, Literal, TypedDict


AppState = Literal["VOID", "SILENT", "OVERTIME"]


class Theme:
    BG = "#050505"
    FG = "#34d399"
    ACCENT = "#10b981"
    WARN = "#f59e0b"
    CRITICAL = "#ef4444"
    FONT_H = ("Segoe UI", 24, "bold")
    FONT_P = ("Segoe UI", 11)
    FONT_MONO = ("Consolas", 10)


class HistoryEntry(TypedDict):
    released_at: str
    intent: str
    planned_min: float
    actual_focus_min: float
    overtime_min: float
    status: Literal["released"]


@dataclass
class Session:
    intent: str = ""
    total_sec: float = 0.0
    start_at: float = 0.0
    paused_at: float | None = None
    total_paused: float = 0.0
    planned_sec: float = 0.0
    extended_sec: float = 0.0

    @property
    def current_pause_sec(self) -> float:
        return (time() - self.paused_at) if self.paused_at is not None else 0.0

    @property
    def effective_elapsed_sec(self) -> float:
        return max(0.0, (time() - self.start_at) - self.total_paused - self.current_pause_sec)

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
        return max(10 * 60, self.planned_sec / 2)

    @property
    def extend_remaining_sec(self) -> float:
        return max(0.0, self.extend_cap_sec - self.extended_sec)

    def can_extend_min(self, mins: int) -> bool:
        return mins * 60 <= self.extend_remaining_sec


class HistoryStore:
    def __init__(self, path: Path, limit: int) -> None:
        self.path = path
        self.limit = limit

    def load(self) -> list[HistoryEntry]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, list):
            return []

        parsed: list[HistoryEntry] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                entry: HistoryEntry = {
                    "released_at": str(item["released_at"]),
                    "intent": str(item["intent"]),
                    "planned_min": float(item["planned_min"]),
                    "actual_focus_min": float(item["actual_focus_min"]),
                    "overtime_min": float(item["overtime_min"]),
                    "status": "released",
                }
                parsed.append(entry)
            except (KeyError, TypeError, ValueError):
                continue
        return parsed[-self.limit :]

    def save(self, history: list[HistoryEntry]) -> None:
        self.path.write_text(
            json.dumps(history[-self.limit :], ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def append_release(self, history: list[HistoryEntry], session: Session) -> list[HistoryEntry]:
        if session.start_at <= 0:
            return history

        actual_focus_min = round(session.effective_elapsed_sec / 60, 2)
        planned_min = round(session.planned_sec / 60, 2)
        overtime_min = round(max(0.0, actual_focus_min - planned_min), 2)

        history.append(
            {
                "released_at": datetime.now().isoformat(timespec="seconds"),
                "intent": session.intent or "FOCUS",
                "planned_min": planned_min,
                "actual_focus_min": actual_focus_min,
                "overtime_min": overtime_min,
                "status": "released",
            }
        )
        self.save(history)
        return history


class GateKeeper(tk.Tk):
    PROGRESS_WIDTH = 200
    PROGRESS_HEIGHT = 8
    HISTORY_LIMIT = 200
    HISTORY_VISIBLE = 8

    PRESETS: list[float] = [0.5, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180]
    EXTEND_OPTIONS = [2, 5, 15]

    OVERTIME_BASE_W = 420
    OVERTIME_BASE_H = 170
    OVERTIME_GROWTH_SEC = 2
    OVERTIME_GROWTH_W = 16
    OVERTIME_GROWTH_H = 9

    def __init__(self) -> None:
        super().__init__()
        self.title("GateKeeper")
        self.configure(bg=Theme.BG)
        self.attributes("-topmost", True)  # type: ignore[arg-type]
        self.overrideredirect(True)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self.session = Session()
        self.status: AppState = "VOID"

        self.history_store = HistoryStore(Path("gate_keeper_history.json"), self.HISTORY_LIMIT)
        self.history: list[HistoryEntry] = self.history_store.load()

        self.progress_canvas: tk.Canvas | None = None
        self.progress_fill_id: int | None = None
        self.lbl_time: tk.Label | None = None

        self._active_bindings: list[str] = []
        self._drag_x = 0
        self._drag_y = 0

        self._overtime_started_at: float | None = None
        self._overtime_steps_applied = -1

        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.do_drag)

        self.stage = tk.Frame(self, bg=Theme.BG)
        self.stage.pack(expand=True, fill="both")

        self.to_void()
        self.tick()

    # --- Common plumbing ---
    def start_drag(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def do_drag(self, event: tk.Event) -> None:
        if self.status == "VOID":
            return
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        self.geometry(f"+{self.winfo_x() + dx}+{self.winfo_y() + dy}")

    def _clear_bindings(self) -> None:
        for seq in self._active_bindings:
            self.unbind(seq)
        self._active_bindings.clear()

    def _bind_tracked(self, sequence: str, func: Callable[[tk.Event], object]) -> None:
        self.bind(sequence, func)
        self._active_bindings.append(sequence)

    def transition(self, target: AppState, size: tuple[int, int] | None = None) -> None:
        self.status = target
        self._clear_bindings()

        if target != "OVERTIME":
            self._overtime_started_at = None
            self._overtime_steps_applied = -1

        for widget in self.stage.winfo_children():
            widget.destroy()

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = size if size else (sw, sh)
        self.geometry(f"{w}x{h}+{int((sw - w) / 2)}+0")

    @staticmethod
    def _validate_float(value: str) -> bool:
        if not value:
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    # --- UI states ---
    def to_void(self) -> None:
        self.transition("VOID")

        tk.Label(self.stage, text="GOAL", font=Theme.FONT_MONO, fg=Theme.ACCENT, bg=Theme.BG).pack(
            pady=(50, 5)
        )

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
            self.stage, text="MINUTES", font=Theme.FONT_MONO, fg=Theme.ACCENT, bg=Theme.BG
        ).pack(pady=(16, 5))

        vcmd = (self.register(self._validate_float), "%P")
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

        preset_frame = tk.Frame(self.stage, bg=Theme.BG)
        preset_frame.pack(pady=(6, 12))
        for idx, mins in enumerate(self.PRESETS):
            text = f"{mins:g}"
            tk.Button(
                preset_frame,
                text=text,
                command=lambda m=text: (ent_time.delete(0, "end"), ent_time.insert(0, m)),
                bg=Theme.BG,
                fg=Theme.FG,
                relief="flat",
                padx=6,
                pady=2,
            ).grid(row=idx // 6, column=idx % 6, padx=3, pady=3)

        def launch(_event: tk.Event | None = None) -> None:
            try:
                mins = float(ent_time.get() or 25.0)
            except ValueError:
                return
            total = mins * 60.0
            self.session = Session(
                intent=ent_intent.get() or "FOCUS",
                total_sec=total,
                planned_sec=total,
                start_at=time(),
            )
            self.to_silent()

        self._bind_tracked("<Return>", launch)
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

        self._render_history_list()

    def to_silent(self) -> None:
        self.transition("SILENT", (240, 96))

        self.lbl_time = tk.Label(self.stage, text="--:--", font=Theme.FONT_H, fg=Theme.FG, bg=Theme.BG)
        self.lbl_time.pack(pady=(8, 2))

        self.progress_canvas = tk.Canvas(
            self.stage,
            width=self.PROGRESS_WIDTH,
            height=self.PROGRESS_HEIGHT,
            bg=Theme.BG,
            highlightthickness=0,
            bd=0,
        )
        self.progress_canvas.pack(pady=(0, 10))
        self.progress_canvas.create_rectangle(
            0, 0, self.PROGRESS_WIDTH, self.PROGRESS_HEIGHT, outline=Theme.ACCENT, width=1
        )
        self.progress_fill_id = self.progress_canvas.create_rectangle(
            0, 0, 0, self.PROGRESS_HEIGHT, fill=Theme.ACCENT, width=0
        )

        self.lbl_time.bind("<Button-1>", lambda _e: self.toggle_pause())
        self._bind_tracked("<space>", lambda _e: self.toggle_pause())
        self._bind_tracked("<Escape>", lambda _e: self.to_void())

    def to_overtime(self) -> None:
        self.transition("OVERTIME", (self.OVERTIME_BASE_W, self.OVERTIME_BASE_H))
        self._overtime_started_at = time()
        self._overtime_steps_applied = -1
        self._update_overtime_growth()

        tk.Label(
            self.stage, text="LIMIT REACHED", font=Theme.FONT_MONO, fg=Theme.CRITICAL, bg=Theme.BG
        ).pack(pady=(16, 6))

        remain_min = round(self.session.extend_remaining_sec / 60.0, 1)
        tk.Label(
            self.stage,
            text=f"EXTEND BUDGET LEFT: {remain_min:g} MIN",
            font=Theme.FONT_MONO,
            fg=Theme.WARN,
            bg=Theme.BG,
        ).pack(pady=(0, 10))

        btn_frame = tk.Frame(self.stage, bg=Theme.BG)
        btn_frame.pack(pady=6)

        def add_time(mins: int) -> None:
            if not self.session.can_extend_min(mins):
                return
            add_sec = mins * 60.0
            self.session.total_sec += add_sec
            self.session.extended_sec += add_sec
            self.to_silent()

        can_extend_any = False
        for mins in self.EXTEND_OPTIONS:
            if self.session.can_extend_min(mins):
                can_extend_any = True
                tk.Button(
                    btn_frame,
                    text=f"+{mins} MIN",
                    command=lambda m=mins: add_time(m),
                    bg=Theme.BG,
                    fg=Theme.FG,
                    relief="flat",
                    padx=8,
                ).pack(side="left", padx=4)

        if not can_extend_any:
            tk.Label(
                self.stage,
                text="EXTEND CAP REACHED",
                font=Theme.FONT_MONO,
                fg=Theme.CRITICAL,
                bg=Theme.BG,
            ).pack(pady=(0, 8))

        def release() -> None:
            self.history = self.history_store.append_release(self.history, self.session)
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

    # --- Behavior ---
    def toggle_pause(self) -> None:
        if self.lbl_time is None:
            return
        if self.session.paused_at is None:
            self.session.paused_at = time()
            self.lbl_time.config(fg=Theme.WARN)
        else:
            self.session.total_paused += time() - self.session.paused_at
            self.session.paused_at = None
            self.lbl_time.config(fg=Theme.FG)

    def _update_overtime_growth(self) -> None:
        if self.status != "OVERTIME" or self._overtime_started_at is None:
            return

        elapsed = time() - self._overtime_started_at
        steps = int(elapsed // self.OVERTIME_GROWTH_SEC)
        if steps == self._overtime_steps_applied:
            return

        self._overtime_steps_applied = steps
        w = self.OVERTIME_BASE_W + (steps * self.OVERTIME_GROWTH_W)
        h = self.OVERTIME_BASE_H + (steps * self.OVERTIME_GROWTH_H)
        self.geometry(f"{w}x{h}+{(self.winfo_x() - self.OVERTIME_BASE_W) // 2}+{self.winfo_y()}")

    def tick(self) -> None:
        if self.status == "SILENT":
            remaining = self.session.remaining_sec
            if remaining <= 0:
                self.to_overtime()
            elif self.lbl_time is not None:
                m, s = divmod(abs(int(remaining)), 60)
                pause_icon = " ⏸" if self.session.paused_at else ""
                self.lbl_time.config(text=f"{m:02d}:{s:02d}{pause_icon}")

                if self.progress_canvas is not None and self.progress_fill_id is not None:
                    fill_w = int(self.PROGRESS_WIDTH * self.session.progress)
                    fill_color = Theme.WARN if self.session.paused_at else Theme.ACCENT
                    self.progress_canvas.coords(self.progress_fill_id, 0, 0, fill_w, self.PROGRESS_HEIGHT)
                    self.progress_canvas.itemconfig(self.progress_fill_id, fill=fill_color)

        elif self.status == "OVERTIME":
            self._update_overtime_growth()

        self.after(500, self.tick)

    # --- History UI ---
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

        for row in reversed(self.history[-self.HISTORY_VISIBLE :]):
            line = f"{row['released_at'][-8:]}  {row['intent']}  {row['actual_focus_min']}m"
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
    GateKeeper().mainloop()

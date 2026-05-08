from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox
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
        return max(
            0.0, (time() - self.start_at) - self.total_paused - self.current_pause_sec
        )

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
        return max(2 * 60, self.planned_sec / 5)

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
            bak = self.path.with_suffix(self.path.suffix + ".bak")
            if not bak.exists():
                try:
                    import shutil

                    shutil.copy2(self.path, bak)
                except OSError:
                    pass
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

    def append_release(
        self, history: list[HistoryEntry], session: Session
    ) -> list[HistoryEntry]:
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

    def delete_entry(
        self, history: list[HistoryEntry], index: int
    ) -> list[HistoryEntry]:
        if 0 <= index < len(history):
            history.pop(index)
            self.save(history)
        return history


class GateKeeper(tk.Tk):
    PROGRESS_WIDTH = 180
    PROGRESS_HEIGHT = 8
    HISTORY_LIMIT = 1000
    HISTORY_VISIBLE = 12

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
        self.attributes("-topmost", True)
        self.overrideredirect(True)
        self.attributes("-toolwindow", True)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self.session = Session()
        self.status: AppState = "VOID"

        self.history_store = HistoryStore(
            Path("gate_keeper_history.json"), self.HISTORY_LIMIT
        )
        self.history: list[HistoryEntry] = self.history_store.load()
        self.history_page = 0
        self.history_filter = ""
        self.history_frame: tk.Frame | None = None
        self.history_content: tk.Frame | None = None

        self.progress_canvas: tk.Canvas | None = None
        self.progress_fill_id: int | None = None
        self.lbl_time: tk.Label | None = None
        self.lbl_budget: tk.Label | None = None
        self.btn_pause: tk.Button | None = None

        self._active_bindings: list[str] = []
        self._drag_x = 0
        self._drag_y = 0

        self._overtime_started_at: float | None = None
        self._overtime_steps_applied = -1
        self._animating = False

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
        new_x = self.winfo_x() + dx
        new_y = self.winfo_y() + dy

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = self.winfo_width()
        win_h = self.winfo_height()

        new_x = max(0, min(new_x, screen_w - win_w))
        new_y = max(0, min(new_y, screen_h - win_h))

        self.geometry(f"+{new_x}+{new_y}")

    def _clear_bindings(self) -> None:
        for seq in self._active_bindings:
            self.unbind(seq)
        self._active_bindings.clear()

    def _bind_tracked(self, sequence: str, func: Callable[[tk.Event], object]) -> None:
        self.bind(sequence, func)
        self._active_bindings.append(sequence)

    def _transition(
        self, target: AppState, size: tuple[int, int] | None = None
    ) -> None:
        self.status = target
        self._clear_bindings()

        if target != "OVERTIME":
            self._overtime_started_at = None
            self._overtime_steps_applied = -1

        for widget in self.stage.winfo_children():
            widget.destroy()

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = size if size else (sw, sh)

        x = int((sw - w) / 2)
        y = 0
        x = max(0, min(x, sw - w))
        y = max(0, min(y, sh - h))

        self.geometry(f"{w}x{h}+{x}+{y}")

    @staticmethod
    def _validate_float(value: str) -> bool:
        if not value:
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    # --- Animation ---
    def _fade_out(self, on_done: Callable[[], None]) -> None:
        def step(alpha: float = 1.0) -> None:
            if alpha > 0.0:
                self.attributes("-alpha", alpha)
                self.after(16, step, max(0.0, alpha - 0.1))
            else:
                self.attributes("-alpha", 0.0)
                on_done()

        step()

    def _fade_in(self) -> None:
        self.attributes("-alpha", 0.0)

        def step(alpha: float = 0.0) -> None:
            if alpha < 1.0:
                self.attributes("-alpha", alpha)
                self.after(16, step, min(1.0, alpha + 0.08))
            else:
                self.attributes("-alpha", 1.0)
                self._animating = False

        step()

    def _do_transition(
        self,
        target: AppState,
        size: tuple[int, int] | None,
        build_fn: Callable[[], None],
    ) -> None:
        self._transition(target, size)
        build_fn()
        self._fade_in()

    def _fade_transition(
        self,
        target: AppState,
        size: tuple[int, int] | None,
        build_fn: Callable[[], None],
    ) -> None:
        if self._animating:
            return
        self._animating = True
        self._fade_out(lambda: self._do_transition(target, size, build_fn))

    # --- UI states ---
    def to_void(self) -> None:
        self._fade_transition("VOID", None, self._build_void)

    def _build_void(self) -> None:
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
                command=lambda m=text: (
                    ent_time.delete(0, "end"),
                    ent_time.insert(0, m),
                ),
                bg=Theme.BG,
                fg=Theme.FG,
                relief="flat",
                padx=6,
                pady=2,
            ).grid(row=idx // 6, column=idx % 6, padx=3, pady=3)

        def launch(_event: tk.Event | None = None) -> None:
            if self._animating:
                return
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

        history_wrapper = tk.Frame(self.stage, bg=Theme.BG)
        history_wrapper.pack(fill="x")
        tk.Frame(history_wrapper, bg=Theme.BG).pack(side="left", expand=True, fill="x")
        self.history_frame = tk.Frame(history_wrapper, bg=Theme.BG)
        self.history_frame.pack(side="left")
        tk.Frame(history_wrapper, bg=Theme.BG).pack(side="left", expand=True, fill="x")

        top_bar = tk.Frame(self.history_frame, bg=Theme.BG)
        top_bar.pack(fill="x", pady=(14, 4))
        tk.Label(
            top_bar, text="FILTER", font=Theme.FONT_MONO, fg=Theme.ACCENT, bg=Theme.BG
        ).pack(side="left")
        self.filter_ent = tk.Entry(
            top_bar,
            font=Theme.FONT_MONO,
            fg=Theme.FG,
            bg=Theme.BG,
            bd=0,
            insertbackground=Theme.FG,
            width=14,
        )
        self.filter_ent.pack(side="left", padx=(4, 0))
        self.filter_ent.bind("<KeyRelease>", self._on_filter_keyrelease)
        tk.Button(
            top_bar,
            text="CLEAR",
            command=self._clear_filter,
            bg=Theme.BG,
            fg=Theme.WARN,
            relief="flat",
            padx=6,
        ).pack(side="left", padx=4)

        self.history_content = tk.Frame(self.history_frame, bg=Theme.BG)
        self.history_content.pack(fill="x")
        self._rebuild_history_ui()

    def to_silent(self) -> None:
        self._fade_transition("SILENT", (220, 160), self._build_silent)

    def _build_silent(self) -> None:
        tk.Label(
            self.stage,
            text=self.session.intent,
            font=Theme.FONT_P,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        ).pack(pady=(6, 0))

        self.lbl_time = tk.Label(
            self.stage, text="--:--", font=Theme.FONT_H, fg=Theme.FG, bg=Theme.BG
        )
        self.lbl_time.pack(pady=(0, 4))

        self.lbl_budget = tk.Label(
            self.stage,
            text="",
            font=Theme.FONT_MONO,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        )
        self.lbl_budget.pack(pady=(0, 2))

        self.progress_canvas = tk.Canvas(
            self.stage,
            width=self.PROGRESS_WIDTH,
            height=self.PROGRESS_HEIGHT,
            bg=Theme.BG,
            highlightthickness=0,
            bd=0,
        )
        self.progress_canvas.pack(pady=(0, 6))
        self.progress_canvas.create_rectangle(
            0,
            0,
            self.PROGRESS_WIDTH,
            self.PROGRESS_HEIGHT,
            outline=Theme.ACCENT,
            width=1,
        )
        self.progress_fill_id = self.progress_canvas.create_rectangle(
            0, 0, 0, self.PROGRESS_HEIGHT, fill=Theme.ACCENT, width=0
        )

        btn_frame = tk.Frame(self.stage, bg=Theme.BG)
        btn_frame.pack(pady=(0, 6))

        self.btn_pause = tk.Button(
            btn_frame,
            text="PAUSE",
            command=self.toggle_pause,
            bg=Theme.BG,
            fg=Theme.FG,
            relief="flat",
            padx=8,
            pady=2,
        )
        self.btn_pause.pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text="BACK",
            command=self._release,
            bg=Theme.BG,
            fg=Theme.WARN,
            relief="flat",
            padx=8,
            pady=2,
        ).pack(side="left", padx=4)

        self._bind_tracked("<space>", lambda _e: self.toggle_pause())
        self._bind_tracked("<Escape>", lambda _e: self._release())

    def to_overtime(self) -> None:
        self._fade_transition(
            "OVERTIME",
            (self.OVERTIME_BASE_W, self.OVERTIME_BASE_H),
            self._build_overtime,
        )

    def _build_overtime(self) -> None:
        self._overtime_started_at = time()
        self._overtime_steps_applied = -1
        self._update_overtime_growth()

        tk.Label(
            self.stage,
            text="LIMIT REACHED",
            font=Theme.FONT_MONO,
            fg=Theme.CRITICAL,
            bg=Theme.BG,
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
            if self._animating or not self.session.can_extend_min(mins):
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

        tk.Button(
            btn_frame,
            text="RELEASE",
            command=self._release,
            bg=Theme.CRITICAL,
            fg=Theme.BG,
            relief="flat",
            padx=20,
        ).pack(side="left", padx=4)

    # --- Behavior ---
    def toggle_pause(self) -> None:
        if self._animating or self.lbl_time is None:
            return

        if self.session.paused_at is None:
            self.session.paused_at = time()
            self.lbl_time.config(fg=Theme.WARN)
            if self.btn_pause:
                self.btn_pause.config(text="RESUME", fg=Theme.ACCENT)
        else:
            self.session.total_paused += time() - self.session.paused_at
            self.session.paused_at = None
            self.lbl_time.config(fg=Theme.FG)
            if self.btn_pause:
                self.btn_pause.config(text="PAUSE", fg=Theme.FG)

    def _release(self) -> None:
        self.history = self.history_store.append_release(self.history, self.session)
        self.to_void()

    def _update_overtime_growth(self) -> None:
        if self.status != "OVERTIME" or self._overtime_started_at is None:
            return

        elapsed = time() - self._overtime_started_at
        steps = int(elapsed // self.OVERTIME_GROWTH_SEC)
        if steps == self._overtime_steps_applied:
            return

        self._overtime_steps_applied = steps

        new_w = min(
            self.OVERTIME_BASE_W + (steps * self.OVERTIME_GROWTH_W),
            self.winfo_screenwidth(),
        )
        new_h = min(
            self.OVERTIME_BASE_H + (steps * self.OVERTIME_GROWTH_H),
            self.winfo_screenheight(),
        )

        new_x = self.winfo_x() - self.OVERTIME_GROWTH_W // 2
        new_y = self.winfo_y()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        new_x = max(0, min(new_x, screen_w - new_w))
        new_y = max(0, min(new_y, screen_h - new_h))

        self.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")

    def tick(self) -> None:
        if self.status == "SILENT":
            remaining = self.session.remaining_sec
            if remaining <= 0:
                self.to_overtime()
            else:
                if self.lbl_time is not None:
                    m, s = divmod(abs(int(remaining)), 60)
                    self.lbl_time.config(text=f"{m:02d}:{s:02d}")

                if self.lbl_budget is not None:
                    planned = self.session.planned_sec / 60
                    extended = self.session.extended_sec / 60
                    parts = [f"PLAN {planned:g}m"]
                    if extended > 0:
                        parts.append(f"+{extended:g}m")
                    parts.append(f"LEFT {int(remaining // 60)}m")
                    self.lbl_budget.config(text="  ".join(parts))

                if (
                    self.progress_canvas is not None
                    and self.progress_fill_id is not None
                ):
                    fill_w = int(self.PROGRESS_WIDTH * self.session.progress)
                    fill_color = Theme.WARN if self.session.paused_at else Theme.ACCENT
                    self.progress_canvas.coords(
                        self.progress_fill_id, 0, 0, fill_w, self.PROGRESS_HEIGHT
                    )
                    self.progress_canvas.itemconfig(
                        self.progress_fill_id, fill=fill_color
                    )

        elif self.status == "OVERTIME":
            self._update_overtime_growth()

        self.after(500, self.tick)

    # --- History UI ---
    def _get_filtered_history(self) -> list[tuple[int, HistoryEntry]]:
        if not self.history_filter:
            return [
                (len(self.history) - 1 - i, e)
                for i, e in enumerate(reversed(self.history))
            ]
        kw = self.history_filter.lower()
        return [
            (len(self.history) - 1 - i, e)
            for i, e in enumerate(reversed(self.history))
            if kw in e["intent"].lower()
        ]

    def _delete_entry(self, real_idx: int) -> None:
        if not messagebox.askyesno("DELETE", "Delete this record?"):
            return
        self.history = self.history_store.delete_entry(self.history, real_idx)
        self._rebuild_history_ui()

    def _on_filter_keyrelease(self, event: tk.Event) -> None:
        self.history_filter = event.widget.get()
        self.history_page = 0
        self._rebuild_history_ui()

    def _clear_filter(self) -> None:
        self.filter_ent.delete(0, "end")
        self.history_filter = ""
        self.history_page = 0
        self._rebuild_history_ui()

    def _prev_page(self) -> None:
        if self.history_page > 0:
            self.history_page -= 1
            self._rebuild_history_ui()

    def _next_page(self) -> None:
        indexed = self._get_filtered_history()
        total_pages = max(
            1, (len(indexed) + self.HISTORY_VISIBLE - 1) // self.HISTORY_VISIBLE
        )
        if self.history_page < total_pages - 1:
            self.history_page += 1
            self._rebuild_history_ui()

    def _rebuild_history_ui(self) -> None:
        for w in self.history_content.winfo_children():
            w.destroy()

        indexed = self._get_filtered_history()

        if not self.history:
            return

        if not indexed:
            tk.Label(
                self.history_content,
                text="NO MATCHES",
                font=Theme.FONT_MONO,
                fg="#555",
                bg=Theme.BG,
            ).pack(pady=(20, 8))
            return

        total_pages = max(
            1, (len(indexed) + self.HISTORY_VISIBLE - 1) // self.HISTORY_VISIBLE
        )
        self.history_page = min(self.history_page, total_pages - 1)
        start = self.history_page * self.HISTORY_VISIBLE
        end = start + self.HISTORY_VISIBLE
        page_indexed = indexed[start:end]

        # --- Header ---
        tk.Label(
            self.history_content,
            text="RECENT RELEASES",
            font=Theme.FONT_MONO,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        ).pack(pady=(6, 4))

        # --- Entries ---
        box = tk.Frame(self.history_content, bg=Theme.BG)
        box.pack(fill="x", pady=(0, 4))

        for real_idx, entry in page_indexed:
            row = tk.Frame(box, bg=Theme.BG)
            row.pack(fill="x")

            released = entry["released_at"][5:16].replace("T", " ")
            intent = entry["intent"]
            focus = entry["actual_focus_min"]
            ot = entry["overtime_min"]
            has_ot = ot >= 1.0

            fg = Theme.WARN if has_ot else Theme.FG
            text = f"{released}  {intent:<14}  {focus:g}m"
            if has_ot:
                text += f"  +{ot:g}m"

            tk.Label(
                row,
                text=text,
                font=Theme.FONT_MONO,
                fg=fg,
                bg=Theme.BG,
                anchor="w",
            ).pack(side="left")

            tk.Button(
                row,
                text="\u00d7",
                command=lambda idx=real_idx: self._delete_entry(idx),
                bg=Theme.BG,
                fg="#555",
                relief="flat",
                padx=4,
            ).pack(side="right")

        # --- Pagination ---
        if total_pages > 1:
            nav = tk.Frame(self.history_content, bg=Theme.BG)
            nav.pack(pady=(0, 8))

            prev_btn = tk.Button(
                nav,
                text="\u25c0 PREV",
                command=self._prev_page,
                bg=Theme.BG,
                fg=Theme.FG,
                relief="flat",
                padx=8,
            )
            prev_btn.pack(side="left", padx=2)
            if self.history_page <= 0:
                prev_btn.config(state="disabled")

            tk.Label(
                nav,
                text=f"{self.history_page + 1}/{total_pages}",
                font=Theme.FONT_MONO,
                fg=Theme.FG,
                bg=Theme.BG,
            ).pack(side="left", padx=8)

            next_btn = tk.Button(
                nav,
                text="NEXT \u25b6",
                command=self._next_page,
                bg=Theme.BG,
                fg=Theme.FG,
                relief="flat",
                padx=8,
            )
            next_btn.pack(side="left", padx=2)
            if self.history_page >= total_pages - 1:
                next_btn.config(state="disabled")


if __name__ == "__main__":
    GateKeeper().mainloop()

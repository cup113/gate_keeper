import tkinter as tk
from time import time
from dataclasses import dataclass, field


# --- Configuration & Theme ---
class Theme:
    BG = "#050505"
    FG = "#34d399"
    ACCENT = "#10b981"
    FONT_H = ("Microsoft YaHei", 24, "bold")
    FONT_P = ("Microsoft YaHei", 12)
    FONT_MONO = ("Consolas", 10)


@dataclass
class Session:
    intent: str = ""
    total_sec: float = 0
    start_at: float = 0
    checkpoints: list[float] = field(default_factory=lambda: [0.5, 0.8])
    passed_checkpoints: int = 0


class VibeGate(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GateKeeper")
        self.configure(bg=Theme.BG)
        self.attributes("-topmost", True)  # type: ignore
        self.overrideredirect(True)

        self.session = Session()
        self.status = "VOID"

        # UI Elements Container
        self.stage = tk.Frame(self, bg=Theme.BG)
        self.stage.pack(expand=True, fill="both")

        self.to_void()
        self.tick()

    def clear_stage(self):
        for widget in self.stage.winfo_children():
            widget.destroy()

    def transition(self, target: str, size: tuple[int, int] | None = None):
        self.status = target
        self.clear_stage()
        if size:
            w, h = size
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"{w}x{h}+{int((sw - w) / 2)}+{int((sh - h) / 4)}")
        else:
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

    # --- States ---

    def to_void(self):
        self.transition("VOID")
        # Layout
        tk.Label(
            self.stage,
            text="INTENT",
            font=Theme.FONT_MONO,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        ).pack(pady=(100, 5))
        ent_intent = tk.Entry(
            self.stage,
            font=Theme.FONT_H,
            fg=Theme.FG,
            bg=Theme.BG,
            bd=0,
            insertbackground=Theme.FG,
            justify="center",
        )
        ent_intent.pack(pady=10)
        ent_intent.focus_set()

        tk.Label(
            self.stage,
            text="MINUTES",
            font=Theme.FONT_MONO,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        ).pack(pady=(20, 5))
        ent_time = tk.Entry(
            self.stage,
            font=Theme.FONT_H,
            fg=Theme.FG,
            bg=Theme.BG,
            bd=0,
            insertbackground=Theme.FG,
            justify="center",
            width=5,
        )
        ent_time.insert(0, "25")
        ent_time.pack(pady=10)

        def launch(_e: tk.Event | None = None):
            self.session = Session(
                intent=ent_intent.get() or "STAYING FOCUSED",
                total_sec=float(ent_time.get() or 25) * 60,
                start_at=time(),
            )
            self.to_silent()

        self.bind("<Return>", launch)
        tk.Button(
            self.stage,
            text="ENGAGE",
            font=Theme.FONT_P,
            command=launch,
            bg=Theme.ACCENT,
            fg=Theme.BG,
            relief="flat",
            padx=20,
        ).pack(pady=40)

    def to_silent(self):
        self.transition("SILENT", size=(180, 40))
        self.lbl_time = tk.Label(
            self.stage, text="--:--", font=Theme.FONT_P, fg=Theme.FG, bg=Theme.BG
        )
        self.lbl_time.pack(expand=True)
        self.unbind("<Return>")

    def to_check(self, progress: float):
        self.transition("CHECK", size=(400, 200))
        tk.Label(
            self.stage,
            text=f"{int(progress * 100)}% COMPLETE",
            font=Theme.FONT_MONO,
            fg=Theme.ACCENT,
            bg=Theme.BG,
        ).pack(pady=20)
        tk.Label(
            self.stage,
            text=f"Still {self.session.intent}?",
            font=Theme.FONT_P,
            fg=Theme.FG,
            bg=Theme.BG,
        ).pack()
        tk.Button(
            self.stage,
            text="YES",
            command=self.to_silent,
            bg=Theme.FG,
            fg=Theme.BG,
            relief="flat",
            width=10,
        ).pack(pady=20)

    def to_overtime(self):
        self.transition("OVERTIME", size=(400, 200))
        tk.Label(
            self.stage,
            text="TIME EXPIRED",
            font=Theme.FONT_H,
            fg="#ef4444",
            bg=Theme.BG,
        ).pack(pady=20)
        tk.Button(
            self.stage,
            text="RELEASE",
            command=self.to_void,
            bg="#ef4444",
            fg=Theme.BG,
            relief="flat",
        ).pack()

    # --- Logic ---

    def tick(self):
        if self.status in ["SILENT", "CHECK", "OVERTIME"]:
            elapsed = time() - self.session.start_at
            remaining = self.session.total_sec - elapsed
            progress = elapsed / self.session.total_sec

            # Update Display
            if hasattr(self, "lbl_time") and self.lbl_time.winfo_exists():
                sign = "+" if remaining < 0 else ""
                m, s = divmod(abs(int(remaining)), 60)
                self.lbl_time.config(
                    text=f"{sign}{m:02d}:{s:02d} | {self.session.intent[:10]}"
                )

            # State Logic
            if self.status == "SILENT":
                if progress >= 1.0:
                    self.to_overtime()
                elif (
                    self.session.passed_checkpoints < len(self.session.checkpoints)
                    and progress
                    >= self.session.checkpoints[self.session.passed_checkpoints]
                ):
                    self.session.passed_checkpoints += 1
                    self.to_check(progress)

        self.after(1000, self.tick)


if __name__ == "__main__":
    VibeGate().mainloop()

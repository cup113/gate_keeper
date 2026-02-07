import tkinter as tk
from time import time
from dataclasses import dataclass, field


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
    passed_checkpoints: int = 0
    paused_at: float | None = None
    total_paused: float = 0
    checkpoints: list[float] = field(default_factory=lambda: [0.5, 0.8])


class VibeGate(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GateKeeper")
        self.configure(bg=Theme.BG)
        self.attributes("-topmost", True)  # type: ignore
        self.overrideredirect(True)

        self.session = Session()
        self.status = "VOID"

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
        dx = event.x - self.x
        dy = event.y - self.y
        x = self.winfo_x() + dx
        y = self.winfo_y() + dy
        self.geometry(f"+{x}+{y}")

    def transition(self, target: str, size: tuple[int, int]):
        self.status = target
        for w in self.stage.winfo_children():
            w.destroy()
        w, h = size
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # 居中逻辑优化
        self.geometry(f"{w}x{h}+{int((sw - w) / 2)}+{int((sh - h) / 4)}")

    # --- States ---
    def to_void(self):
        self.transition("VOID", (400, 500))

        tk.Label(
            self.stage, text="GOAL", font=Theme.FONT_MONO, fg=Theme.ACCENT, bg=Theme.BG
        ).pack(pady=(60, 5))
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

        def validation_core(p: str) -> bool:
            try:
                float(p)
                return True
            except ValueError:
                return False

        # Validation Logic (ROI: 1)
        vcmd = (self.register(validation_core), "%P")
        ent_time = tk.Entry(
            self.stage,
            font=Theme.FONT_H,
            fg=Theme.FG,
            bg=Theme.BG,
            bd=0,
            insertbackground=Theme.FG,
            justify="center",
            width=5,
            validate="key",
            validatecommand=vcmd,
        )
        ent_time.insert(0, "25")
        ent_time.pack(pady=10)

        def launch(_e: tk.Event | None = None):
            try:
                mins = float(ent_time.get() or 25)
                self.session = Session(
                    intent=ent_intent.get() or "FOCUS",
                    total_sec=mins * 60,
                    start_at=time(),
                )
                self.to_silent()
            except:
                pass

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
        ).pack(pady=40)
        tk.Button(
            self.stage,
            text="EXIT",
            font=Theme.FONT_MONO,
            command=self.quit,
            bg=Theme.BG,
            fg="#444",
            relief="flat",
        ).pack()

    def to_silent(self):
        self.transition("SILENT", (220, 80))
        self.lbl_time = tk.Label(
            self.stage, text="--:--", font=Theme.FONT_H, fg=Theme.FG, bg=Theme.BG
        )
        self.lbl_time.pack(expand=True)
        # ROI: 8 (Pause interaction)
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
        self.transition("OVERTIME", (300, 250))
        tk.Label(
            self.stage,
            text="LIMIT REACHED",
            font=Theme.FONT_MONO,
            fg=Theme.CRITICAL,
            bg=Theme.BG,
        ).pack(pady=20)

        # ROI: 7 (Snooze/Extra time)
        btn_frame = tk.Frame(self.stage, bg=Theme.BG)
        btn_frame.pack(pady=10)

        def snooze():
            self.session.total_sec += 300  # Add 5 mins
            self.to_silent()

        tk.Button(
            btn_frame,
            text="+5 MIN",
            command=snooze,
            bg=Theme.BG,
            fg=Theme.FG,
            relief="flat",
            padx=10,
        ).pack(side="left", padx=5)
        tk.Button(
            btn_frame,
            text="RELEASE",
            command=self.to_void,
            bg=Theme.CRITICAL,
            fg=Theme.BG,
            relief="flat",
            padx=20,
        ).pack(side="left", padx=5)

    def tick(self):
        if self.status == "SILENT":
            now = time()
            # Calculate effective elapsed time
            current_pause = (
                (now - self.session.paused_at) if self.session.paused_at else 0
            )
            effective_elapsed = (
                (now - self.session.start_at)
                - self.session.total_paused
                - current_pause
            )

            remaining = self.session.total_sec - effective_elapsed

            if remaining <= 0:
                self.to_overtime()
            else:
                m, s = divmod(abs(int(remaining)), 60)
                pause_icon = " ⏸" if self.session.paused_at else ""
                self.lbl_time.config(text=f"{m:02d}:{s:02d}{pause_icon}")

        self.after(500, self.tick)


if __name__ == "__main__":
    VibeGate().mainloop()

from tkinter import Tk, Button, Label, StringVar, Entry, Frame
from time import time
from typing import Literal, Callable, Any
from dataclasses import dataclass

class Config:
    BG = "#0c0c0c"
    FG = "#34d399"
    HL = "#00633f"

Status = Literal["void", "silent", "check", "overtime", "quit"]

@dataclass
class State:
    status: Status
    running: bool
    time_start: float
    time_end: float
    checkpoints: list[float]
    next_checkpoint_index: int


class GateKeeper(Tk):
    def __init__(self):
        super().__init__()

        self.config(background=Config.BG)
        self.overrideredirect(True)
        self.attributes("-topmost", True) # type: ignore
        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        self.resize(self.screen_width, self.screen_height)

        self.state = State(status="void", running=True, time_start=time(), time_end=time(), checkpoints=[0.5, 0.75], next_checkpoint_index=0)

        self.frames: dict[Status, Frame] = {}

        self.var_intent = StringVar(self, "")
        self.var_time_total = StringVar(self, "10")
        self.var_time_left_display = StringVar(self, "00:00")
        self.var_hint = StringVar(self, "")

        frame_status_list: list[Status] = ["void", "check", "silent", "overtime"]

        for status in frame_status_list:
            self.new_frame(status)

        self.label_intent = self.new_label("void", "你要去做什么？", 16)
        self.entry_intent = self.new_entry("void", self.var_intent)
        self.label_time_total = self.new_label("void", "请输入时间 (分钟): ", 16)
        self.entry_time_total = self.new_entry("void", self.var_time_total)
        self.btn_act = self.new_button("void", "开始", self.start_timer)
        self.label_time = self.new_label("silent", self.var_time_left_display, 16)
        self.label_hint = self.new_label("check", self.var_hint, 12)
        self.btn_check = self.new_button("check", "确认", self.check_ok)
        self.label_overtime = self.new_label("overtime", "已超时", 14)
        self.btn_back = self.new_button("overtime", "返回", self.back_void)

        self._leave_for("void")

        self.update()

    def new_frame(self, name: Status):
        self.frames[name] = Frame(self, name=name, background="#0c0c0c")
        return self

    def new_label(self, status: Status, text: str | StringVar, font_size: int) -> Label:
        kwargs = { "text": text } if isinstance(text, str) else { "textvariable": text }
        label = Label(self.frames[status], kwargs, background=Config.BG, foreground=Config.FG, font=("Microsoft YaHei", font_size))
        label.pack()
        return label

    def new_entry(self, status: Status, textvariable: StringVar) -> Entry:
        entry = Entry(self.frames[status], background=Config.BG, foreground=Config.FG, textvariable=textvariable)
        entry.pack()
        return entry

    def new_button(self, status: Status, text: str, command: Callable[[], Any]):
        button = Button(self.frames[status], background=Config.BG, foreground=Config.FG, text=text, activebackground=Config.HL, command=command)
        button.pack()
        return button

    def resize(self, width: int, height: int):
        self.geometry(f"{width}x{height}+{int(self.screen_width / 2 - width / 2)}+0")
        return self

    def _leave_for(self, to: Status):
        self.frames[self.state.status].pack_forget()
        self.state.status = to
        self.frames[to].pack()
        return self

    def to_void(self):
        self._leave_for("void").resize(self.screen_width, self.screen_height)

    def to_silent(self):
        self._leave_for("silent").resize(120, 30)

    def start_timer(self):
        self.time_start = time()
        self.time_end = self.time_start + float(self.var_time_total.get()) * 60.0
        self.to_silent()

    def to_check(self):
        self._leave_for("check").resize(240, 80)

    def to_overtime(self):
        self._leave_for("overtime").resize(320, 120)

    def check(self, portion: float):
        self.to_check()
        self.state.next_checkpoint_index += 1
        self.var_hint.set(f"现在已经过了 {(portion * 100):.0f}%\n你还在 {self.var_intent.get()} 吗？")

    def check_ok(self):
        self.to_silent()

    def overtime(self):
        self.state.next_checkpoint_index += 1
        self.to_overtime()

    def back_void(self):
        self.to_void()
        self.state.next_checkpoint_index = 0

    def update_time_left(self) -> float:
        left = self.time_end - time()
        self.var_time_left_display.set(self.format_time(left))
        return 1 - left / (self.time_end - self.time_start)


    def update(self):
        if self.state.status == "quit":
            return
        if self.state.status == "silent":
            portion = self.update_time_left()
            if self.state.next_checkpoint_index < len(self.state.checkpoints):
                if portion >= self.state.checkpoints[self.state.next_checkpoint_index]:
                    self.check(portion)
            elif self.state.next_checkpoint_index == len(self.state.checkpoints):
                self.overtime()
        elif self.state.status == "check":
            self.update_time_left()
        elif self.state.status == "overtime":
            self.update_time_left()

        self.after(1000, self.update)

    def destroy(self) -> None:
        self.state.status = "quit"
        return super().destroy()

    @staticmethod
    def format_time(sec: float) -> str:
        neg = sec < 0
        if neg:
            sec *= -1
        sec = int(sec)
        s = sec % 60
        m = sec // 60
        return f"{'+' if neg else ''}{m:02d}:{s:02d}"


if __name__ == "__main__":
    app = GateKeeper()
    app.mainloop()

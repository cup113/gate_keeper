# GateKeeper v1.0.1 — 专注力守卫者

> 用着用着就跑偏？GateKeeper 会在你走神时温柔地提醒你，并记录每一次专注的历程。

## ⚠️ 请您知晓

1. 本项目目前仅支持 **Windows** 系统。
2. 本项目禁用了关闭窗口的快捷键，以保证专注。君子协定：若您想要脱离此应用，可前往任务管理器杀进程。

## 🎯 痛点场景

你是否经历过这样的循环？

1. 打开电脑，告诉自己「就查点资料，5分钟」
2. 刷了半小时 Bilibili/知乎
3. 意识到时间流逝，但已经陷入无尽分心
4. 一天结束，想不起自己到底「专注」完成了什么

**GateKeeper 的核心价值**：不只是计时器，而是一个**意图确认机制**——在你开始前写下 `「我要专注的事」`，在到时间时提醒你“放下电脑，回归生活”。

---

## 🚀 功能亮点

### 1. 极简无干扰模式

- **VOID 状态**：启动界面，输入任务意图和时长（支持预设按钮）
- **SILENT 状态**：全屏或小窗口显示剩余时间，点击可暂停
- **OVERTIME 状态**：时间到后触发，可选择延长或释放

### 2. 智能扩展机制

- 每次专注结束后，记录实际专注时长
- 超时部分计入 **overtime**
- 延长预算 = 计划时长 / 5，防止无限拖延

### 3. 历史追踪

- 自动保存最近 1000 次释放记录到 `%APPDATA%\GateKeeper\gate_keeper_history.json`
- VOID 界面显示最近 12 条记录，支持分页浏览
- 支持按意图关键词筛选历史记录
- 每条记录可单独删除
- 超时记录（overtime ≥ 1min）以黄色高亮显示

### 4. 平滑过渡动画

- 状态切换时（VOID ↔ SILENT ↔ OVERTIME）带有淡入淡出动画
- 避免生硬跳变，视觉体验更流畅

### 5. 窗格生长动画（OVERTIME 状态）

- 进入超时状态后，窗口每 **2秒** 自动增长：
  - 宽度 +16px
  - 高度 +9px
- 视觉上营造「时间正在流逝，且不可逆」的紧迫感

---

## 🛠️ 安装与运行

### 环境要求

- Python 3.9+
- 无需额外依赖（标准库：`tkinter`, `json`, `dataclasses`, `pathlib` 等）

### 运行

```bash
python main.pyw
```

---

## 📖 使用指南

### 1. 开始专注（VOID 状态）

- 在 `GOAL` 输入框填写 **本次专注意图**（如：写报告、学Python）
- 在 `MINUTES` 输入计划时长（或点击预设按钮）
- 按 `Enter` 或点击 `ENGAGE` 启动

### 2. 专注中（SILENT 状态）

- 窗口居中显示剩余时间（格式：`MM:SS`）
- 点击时间或按 `Space` 可暂停/继续（暂停时变黄）
- 按 `Esc` 或点击 `BACK` 可放弃本次，返回 VOID 状态
- 状态切换带有淡入淡出动画
- 窗口支持拖拽，边界自动吸附屏幕边缘

### 3. 时间到（OVERTIME 状态）

- 显示剩余延长预算（分钟）
- 可选 `+2 MIN` / `+5 MIN` / `+15 MIN` 继续
- 或点击 `RELEASE` 结束并记录本次数据

---

## 🧠 设计哲学

| 原则 | 实现 |
|------|------|
| **意图先行** | 启动前必须填写任务描述 |
| **无干扰** | 专注窗口不可关闭，仅可拖动 |
| **数据反馈** | 每次结束生成记录，长期可见「实际专注时长」 |
| **防沉迷** | 延长有预算上限，避免自我欺骗 |

---

## 📊 数据记录示例

`%APPDATA%\GateKeeper\gate_keeper_history.json` 片段：
```json
[
  {
    "released_at": "2024-06-15T14:30:00",
    "intent": "写项目文档",
    "planned_min": 30.0,
    "actual_focus_min": 28.5,
    "overtime_min": 0.0,
    "status": "released"
  }
]
```

---

## 🔧 自定义配置

如需调整，可修改代码中的常量类：

```python
class GateKeeper(tk.Tk):
    PROGRESS_WIDTH = 180   # 进度条宽度
    PROGRESS_HEIGHT = 8     # 进度条高度

    PRESETS = [0.5, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180]

    EXTEND_OPTIONS = [2, 5, 15]

    OVERTIME_BASE_W = 420
    OVERTIME_BASE_H = 170
    OVERTIME_GROWTH_SEC = 2
    OVERTIME_GROWTH_W = 16
    OVERTIME_GROWTH_H = 9

    HISTORY_LIMIT = 1000       # 保留上限
    HISTORY_VISIBLE = 12       # 每页显示条数
```

---

## 📂 项目结构

```
gate_keeper/
├── main.pyw                 # 单文件实现，无外部依赖
├── build.bat                # Nuitka 构建脚本
├── README.md                # 本文档
├── AGENTS.md                # AI助手指令
├── CHANGELOG.md             # 变更日志
├── LICENSE                  # Apache 2.0
└── dist/                    # 构建产物（Git忽略）
```

# mano-cua MCP

桌面 GUI 自动化 MCP Server，为 OpenCode 和兼容 MCP 的 AI Agent 提供鼠标、键盘、截图等原子操作。

## 特性

- **12 个 GUI 操作工具** — 点击、右键、双击、拖拽、滚动、输入、快捷键、组合键点击等
- **自动截图返回** — 每个动作执行后可选择自动截图返回给 Agent
- **可选截图开关** — `screenshot=False` 跳过 2s 等待和截图，适合多步连续操作
- **多步批量执行** — 一次发出多个 tool_call，中间不截图，省 Token
- **0~1000 归一化坐标** — 与 Qwen3-VL 视觉 token 网格一致的坐标系统
- **截图参考网格** — 每张截图自动叠加 0~1000 网格线和坐标标注，Agent 可直接对照定位
- **智能应用启动** — 通过 PowerToys Run 或 Win 键开始菜单搜索打开应用
- **固定截图尺寸** — 短边 1080px，保证视觉模型输入一致性

## 系统要求

- **Windows** 10/11（仅支持 Windows）
- **Python** 3.12+
- **[PowerToys](https://github.com/microsoft/PowerToys)**（推荐，用于 `open_app` 快速启动；未安装时自动回退到 Win 键开始菜单）

## 安装

```bash
# 克隆仓库
git clone https://github.com/ConstantinopleMayor/mano-cua-mcp.git
cd mano-cua-mcp

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

## 在 OpenCode 中配置

**1. 配置 MCP Server**

在 `~/.config/opencode/config.json` 中添加：

```json
{
  "mcp": {
    "mano-cua": {
      "type": "local",
      "command": [
        "D:\\path\\to\\mano-cua-mcp\\.venv\\Scripts\\python.exe",
        "D:\\path\\to\\mano-cua-mcp\\server.py"
      ],
      "enabled": true
    }
  }
}
```

**2. 安装 Skill 文件**

将 `SKILL.md` 复制到 `~/.agents/skills/mano-cua/` 目录下，然后在 OpenCode 中通过 `@mano-cua` 使用。

```powershell
# 复制 Skill 文件
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills\mano-cua"
Copy-Item -Path "SKILL.md" -Destination "$env:USERPROFILE\.agents\skills\mano-cua\"
```

配置完成后重启 OpenCode，即可用 `@mano-cua` 提示词触发桌面自动化。

## 工具列表

| 工具 | 参数 | 说明 |
|---|---|---|
| `left_click(x, y, screenshot?)` | 0~1000 坐标 | 左键点击 |
| `right_click(x, y, screenshot?)` | 0~1000 坐标 | 右键点击 |
| `double_click(x, y, screenshot?)` | 0~1000 坐标 | 双击 |
| `mouse_move(x, y, screenshot?)` | 0~1000 坐标 | 鼠标悬停（不点击） |
| `left_click_drag(sx, sy, ex, ey, screenshot?)` | 0~1000 坐标 | 拖拽 |
| `scroll(x, y, scroll_y, screenshot?)` | 0~1000 坐标 + 方向 | 滚动（正数向上，负数向下） |
| `type_text(text, screenshot?)` | 字符串 | 输入文本（剪贴板粘贴，支持中文） |
| `key_combination(keys, screenshot?)` | 字符串数组 | 快捷键，如 `["ctrl","c"]` |
| `hotkey_click(x, y, keys, screenshot?)` | 0~1000 坐标 + 修饰键 | 按住修饰键同时点击（如 Ctrl+点击新标签打开） |
| `wait(seconds)` | 秒数 | 等待后截图（任务开始用 0 看状态） |
| `open_app(name, screenshot?)` | 应用名 | 打开应用，默认等 5s 截图 |
| `open_url(url, screenshot?)` | URL | 浏览器打开链接，默认等 2s 截图 |

**`screenshot` 参数**（默认 `True`）：
- `screenshot=True`：动作后等待 2s + 截图返回（`TextContent + ImageContent`）
- `screenshot=False`：动作后立即返回文字（`TextContent` 仅文本），适合多步连续操作

## 使用示例

### 基本用法：发送消息

```
@mano-cua 帮我打开微信，给张三发消息"你好，明天开会吗"
```

Agent 执行流程：
```
wait(0)                                      → 看当前屏幕
open_app("微信")                              → 打开微信，自动等 5s 截图
left_click(x=500, y=600)                     → 点击搜索框
type_text("张三")                             → 输入联系人
key_combination(["enter"])                   → 回车搜索
left_click(x=500, y=700)                     → 点击联系人
left_click(x=500, y=800)                     → 点击输入框
type_text("你好，明天开会吗")                   → 输入消息
key_combination(["enter"])                   → 发送
```

### 多步批量模式（省 Token）

已确认目标位置后，关闭中间截图：

```
left_click(x=500, y=800, screenshot=False)   → 点击输入框，不截图不等待
type_text("你好", screenshot=False)           → 输入文本，不截图不等待
key_combination(["enter"])                   → 发送，截图确认（默认 True）
```

## 坐标系统

```
(0,0)  ─────────────────────── (1000,0)
  │        200  400  600  800      │
  │   ├────┼────┼────┼────┤        │
  │ 200                            │
  │ 400    每张截图自动叠加         │
  │ 600    0~1000 参考网格         │
  │ 800                            │
  │        可直接对照坐标点击       │
(0,1000) ───────────────────── (1000,1000)
```

## 架构对比

MCP Server 负责接收 LLM 的 tool call → 调用 `executor.py`（mss+pynput+Pillow）执行操作 → 返回截图。

相较[上游 mano-skill](https://github.com/Mininglamp-AI/mano-skill)（Qwen3-VL 专用、macOS 为主），本方案使用通用 MCP 协议，适配任何支持 tool_use 的 LLM（Claude、GPT、DeepSeek 等）。

## 致谢

本项目的设计受 [Mininglamp-AI/mano-skill](https://github.com/Mininglamp-AI/mano-skill) 启发。

## 许可证

MIT
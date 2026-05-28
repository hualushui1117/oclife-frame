# oclife-frame Skill 诊断与修改建议

> 基于 [oclife-frame GitHub 项目](https://github.com/hualushui1117/oclife-frame) 现有 `.claude/skills/frame-produce/SKILL.md` 及其关联代码的审阅分析。

---

## 一、现有问题诊断

| # | 问题 | 现状 | 影响 |
|---|------|------|------|
| 1 | **frontmatter 不兼容** | 使用了 `argument-hint`、`user-invocable` 等 Claude Code 专属字段 | OpenClaw 只读取 `name` + `description` 两个字段，其余被忽略，skill 触发和参数传递机制失效 |
| 2 | **硬编码绝对路径** | 写死 `cd "/Users/hualushui/Desktop/for palpal/oclife-frame"` | 换台机器、换个用户、换个目录结构直接报错 |
| 3 | **description 触发面窄** | 只写了"生产角色素材、开始frame生产" | 用户说"用 oclife 做个角色包""帮我生成几个待机视频""我要首尾帧模式"等表述可能无法触发 skill |
| 4 | **视角混乱（致命）** | 大量"请用户提供..."、"展示给用户确认" | 这是**用户文档**，不是 **agent 操作手册**。另一个 AI 拿到后不知道怎么执行 |
| 5 | **工具链路径不统一** | 有的地方走 CLI (`python3 src/cli.py ...`)，有的地方直接内嵌 Python 代码块 (`python3 -c "..."`) | agent 不知道该走哪条路，上下文里两种风格混杂 |
| 6 | **步骤过度拆分** | Step 0→4 每个都要人工确认，用 CLI 逐个执行 | 实际 `workflow_frame.py` 里的 `run()` 函数已经能一键跑通全流程，skill 没有利用这个能力 |
| 7 | **references 加载不明确** | `prompt-rules.md`、`state-rules.md`、`profile-format.md` 被引用，但没有说明什么场景下该读哪个 | agent 可能会漏读、多读、读错 |
| 8 | **缺少 API 参数速查** | `jimeng_client.py` 里有大量 API 行为细节（frames 计算、超时时间、并发策略），但 skill 里没有提炼 | agent 遇到问题只能去翻源码 |
| 9 | **错误处理缺位** | skill 里没有说明常见失败场景怎么应对（API 限流、task 过期、ffmpeg 缺失等） | agent 出错后不知道重试还是跳过 |
| 10 | **没有边界声明** | 没写"什么情况下不该用这个 skill" | 容易被误触发（比如用户只是想普通 AI 生图，不是做 Frame 角色包） |

---

## 二、建议修改方案

### 2.1 frontmatter 重写

**核心原则：** `description` 是 agent 判断是否调用此 skill 的**唯一依据**。必须塞满触发词和边界条件。

```yaml
---
name: oclife-frame
description: >
  OcLife Frame 模式视频素材批量生产工具。基于单张角色图，通过即梦（Jimeng）API
  自动生成完整的 7 视频角色素材包（idle ×3 + transition ×2 + listen + dialogue），
  供定格故事（Frame Story）使用。

  当用户需要以下任一操作时触发：
  - 批量生成 AI 视频角色素材 / frame 素材包 / 角色视频包
  - 使用 oclife / 即梦 / jimeng 生成视频
  - 生成角色待机视频、聆听视频、说话视频、过渡视频
  - 首帧模式 / 尾帧模式 / 首尾帧模式视频生成
  - 生产清单（manifest + metadata）生成
  - 5s 预览视频生成（首帧模式）
  - 角色图标准化（I2I）或中性帧生成
  - 角色档案（profile snapshot）生成

  不适用：非 Frame 模式的普通 AI 视频生成、不涉及角色一致性的视频制作。
---
```

**变化点：**
- 删除 `argument-hint`、`user-invocable` 等 Claude Code 专属字段
- 在 description 中明确列举所有触发场景
- 新增"不适用"声明，防止误触发

---

### 2.2 去掉所有硬编码路径

**问题示例：**
```bash
# ❌ 不要这样写
cd "/Users/hualushui/Desktop/for palpal/oclife-frame"
```

**建议改成：**
```markdown
## 项目定位

oclife-frame 是用户 workspace 中的项目。执行前先定位项目根目录：

```bash
# 方式1：在 workspace 中搜索
PROJECT_DIR=$(find ~ -maxdepth 4 -type d -name "oclife-frame" 2>/dev/null | head -1)
cd "$PROJECT_DIR"

# 方式2：若当前目录已在项目内
if [ -f "src/cli.py" ] && [ -f "src/workflow_frame.py" ]; then
  # 已在项目根目录
  :
else
  echo "错误：未找到 oclife-frame 项目。请确认项目路径。"
  exit 1
fi
```
```

**更优做法：** 优先使用 Python API（相对导入），完全避开路径问题。

---

### 2.3 统一工具链：Python API 为主，CLI 为辅

**现状问题：** skill 教 agent 一步一步走 CLI，但 `workflow_frame.py` 里已经有 `run()` 能一键跑通。

**建议结构：**

```markdown
## 路径 A：全自动快速生产（推荐）

适用：用户已提供角色图 URL + 角色描述，不需要中途人工确认。

```python
import sys
sys.path.insert(0, "src")
from workflow_frame import run

result = run(
    character_id="char001",
    version="v1",
    source_image_url="https://...",
    standardize_prompt="...",
    video_prompts={
        "idle_001": "...",
        "idle_002": "...",
        "idle_003": "...",
        "transition_state_change_001": "...",
        "transition_return_to_idle_001": "...",
        "listen_001": "...",
        "dialogue_base_001": "...",
    },
    output_root="output",
)
# result["package_dir"] 即最终包路径
# result["results"] 包含每个视频的生成状态
```

## 路径 B：分步生产（含人工确认节点）

适用：用户需要在标准图、预览视频、生产清单等节点确认。

| 步骤 | 操作 | 代码 |
|------|------|------|
| Step 0 | 环境检查 | `python3 src/cli.py check-env` |
| Step 1-A | 生成标准图+中性帧 | `workflow_frame.step1a_generate_anchors()` 或 CLI |
| Step 1-B | 保存角色档案 | `python3 src/cli.py save-profile-snapshot ...` |
| Step 1-C | 生成预览视频 | `workflow_frame.step1c_generate_preview()` 或 CLI |
| Step 2 | 状态描述（全自动） | agent 直接生成文本写入文件 |
| Step 3 | 批量生成 7 视频 | `python3 src/cli.py run-workflow ...` |
| Step 4 | 质检+打包 | `python3 src/cli.py verify-package ...` + `make-demo` |
```

---

### 2.4 把"教用户"改成"教 agent"

**问题示例：**
```markdown
❌ 【介入点 1】 展示两张图，询问是否满意。不满意则重新生成。
```

**改成：**
```markdown
✅ **介入点 1 — 角色图确认**

执行 Step 1-A 后，会生成两张图：
- `session/角色标准正面图.png`
- `session/中性帧.png`

用 `read` 工具读取图片文件并向用户展示。
等待用户回复：
- "满意" → 继续 Step 1-B
- "重新生成" → 调整 `standardize_prompt`（规则见 references/prompt-rules.md），重跑 Step 1-A
- "修改 xxx" → 按用户反馈调整 prompt 后重跑
```

---

### 2.5 references 文件拆分与加载策略

**建议的目录结构：**

```
oclife-frame/
├── SKILL.md                          # 核心流程 + 触发逻辑（< 500 行）
├── references/
│   ├── api-params.md                 # 即梦 API 参数表、超时、限流、错误码
│   ├── prompt-rules.md               # 7 视频 prompt 构造规则（现有，可复用）
│   ├── state-rules.md                # 状态描述生成规则（现有，可复用）
│   ├── profile-format.md             # 角色档案 JSON 格式（现有，可复用）
│   └── workflow-mapping.md           # Skill 步骤 ↔ 代码函数 ↔ CLI 命令 映射
```

**workflow-mapping.md 内容示例：**
```markdown
| Skill 步骤 | 对应 Python 函数 | 对应 CLI 命令 | 触发方式 | 人工确认 |
|-----------|-----------------|-------------|---------|---------|
| Step 0 环境检查 | — | `cli.py check-env` | CLI | 否 |
| Step 1-A 标准化+中性帧 | `workflow_frame.step1a_generate_anchors()` | — | Python API | 是（介入点1） |
| Step 1-B 角色档案 | — | `cli.py save-profile-snapshot` | CLI | 是（介入点2） |
| Step 1-C 预览视频 | `workflow_frame.step1c_generate_preview()` | — | Python API | 是（介入点3） |
| Step 2 状态描述 | — | — | Agent 文本生成 | 否 |
| Step 3 批量视频 | `workflow_frame.step3_generate_videos()` | `cli.py run-workflow` | Python API / CLI | 否 |
| Step 4 打包 | `workflow_frame.step4_write_package()` | `cli.py verify-package` + `make-demo` | Python API / CLI | 否 |
| 一键全跑 | `workflow_frame.run()` | — | Python API | 否（默认） |
```

---

### 2.6 增加错误处理指南

在 SKILL.md 末尾增加：

```markdown
## 常见故障处理

| 现象 | 原因 | 处理 |
|------|------|------|
| `check-env` 报 `volcenginesdkcore` 缺失 | 未安装火山引擎 SDK | `pip install volcenginesdkcore` |
| `.env 凭据完整` 但 API 报 403 | AK/SK 错误或无权限 | 检查 `.env` 值，确认火山引擎已开通即梦 API |
| Video task `expired` | 任务超时（默认 600s） | 检查视频时长参数，单条重试 |
| Video task `not_found` | task_id 失效 | 重新提交 |
| `ffmpeg 未安装` | 可选依赖缺失 | 跳过 `make-demo` 步骤，或提醒用户安装 ffmpeg |
| 7 视频中部分失败 | API 限流或单条异常 | `run-workflow` 会自动继续其余视频；失败列表在 stdout 中打印 |
```

---

### 2.7 SKILL.md 全文结构建议

```markdown
---
name: oclife-frame
description: >
  [见 2.1]
---

# OcLife Frame 生产工具

## 前置条件
[项目定位、.env、Python 版本、依赖]

## 全自动快速生产（推荐）
[路径 A：run() 一键调用]

## 分步生产（含人工确认）
[路径 B：Step 0→4，每个步骤的代码 + 介入点说明]

## Prompt 生成规则
[简要说明 + references/prompt-rules.md 链接]

## 常见故障处理
[见 2.6]

## References
[各 reference 文件说明及加载时机]
```

---

## 三、两个实施选项

| 选项 | 做法 | 投入 | 产出 |
|------|------|------|------|
| **A. 最小改动** | 仅把现有 `.claude/skills/frame-produce/SKILL.md` 改成 OpenClaw 格式：修正 frontmatter、去掉硬编码路径、改 agent 视角 | 30 分钟 | 立即可用，但结构保持原有 CLI 分步模式 |
| **B. 彻底重构** | 按本方案重新设计：双路径（全自动/分步）、workflow-mapping、错误处理、references 拆分 | 1-2 小时 | 长期维护更省力，agent 执行更可靠 |

---

## 四、快速检查清单（自测用）

写完 skill 后，用以下问题自测：

- [ ] `name` 是否全小写、只用字母/数字/连字符？
- [ ] `description` 是否包含至少 5 种不同的用户表达触发方式？
- [ ] 是否声明了"不适用"场景？
- [ ] 文中是否还有任何硬编码的绝对路径？
- [ ] 是否出现了"请用户..."、"展示给用户..."等用户文档口吻？
- [ ] 是否明确了 Python API vs CLI 的调用时机？
- [ ] references 文件是否都在 SKILL.md 中提到了加载时机？
- [ ] 是否包含常见错误处理？
- [ ] 全文是否 < 500 行？（超过则拆分）
- [ ] 用 `package_skill.py` 验证是否通过？

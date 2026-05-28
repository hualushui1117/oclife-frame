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
  - 首帧 / 尾帧 / 首尾帧模式视频生成
  - 生产清单（manifest + metadata）生成
  - 5s 预览视频生成
  - 角色图标准化（I2I）或中性帧生成
  - 角色档案（profile snapshot）生成

  不适用：非 Frame 模式的普通 AI 视频生成、不涉及角色一致性的视频制作。
---

# OcLife Frame 生产工具

## 前置条件

**定位项目根目录：**

```bash
if [ ! -f "src/cli.py" ]; then
  PROJECT_DIR=$(find ~ -maxdepth 5 -type d -name "oclife-frame" 2>/dev/null | head -1)
  cd "$PROJECT_DIR"
fi
```

**环境检查：**

```bash
python3 src/cli.py check-env
```

通过后继续。任一失败则告知缺失项后停止。

**必要配置：**
- `.env` 包含 `JIMENG_ACCESS_KEY_ID` 和 `JIMENG_SECRET_ACCESS_KEY`
- Python ≥ 3.10，`pip install -r requirements.txt`

---

## 路径 A — 全自动快速生产（推荐）

**适用：** 用户已提供角色图 URL + 完整描述，不需要中途确认节点。

生成 prompt 前先读取：[`references/prompt-rules.md`](./references/prompt-rules.md)

```python
import sys
sys.path.insert(0, "src")
from workflow_frame import run

result = run(
    character_id="char001",          # 替换为实际角色 ID
    version="v1",
    source_image_url="https://...",  # 用户提供的角色原图 URL
    standardize_prompt="...",        # 按 references/prompt-rules.md 规则生成
    video_prompts={
        "idle_001": "...",
        "idle_002": "...",
        "idle_003": "...",
        "transition_state_change_001": "保持镜头固定不变，保持人物一致，角色看向镜头，仿佛在聆听一般",
        "transition_return_to_idle_001": "...",
        "listen_001": "...",
        "dialogue_base_001": "...",
    },
    output_root="output",
)
# result["package_dir"] — 最终包路径
# result["results"]    — 每个视频的生成状态列表
```

完成后执行质检和 demo：

```bash
python3 src/cli.py verify-package --package-dir "output/char001_frame_package_v1"
python3 src/cli.py make-demo \
  --source "output/char001_frame_package_v1/videos/char001_frame_idle_001_v1.mp4" \
  --output "session/demo.mp4"
```

向用户交付包路径和 `session/demo.mp4`。

---

## 路径 B — 分步生产（含人工确认）

步骤与代码函数的完整映射见 [`references/workflow-mapping.md`](./references/workflow-mapping.md)。

### Step 0 — 环境检查

```bash
python3 src/cli.py check-env
```

通过则继续。任一失败则告知缺失项后停止。

---

### Step 1-A — 角色图标准化 + 中性帧

**收集：** 等待用户提供角色图 URL、角色描述、目标风格（二次元/写实/Q版/3D渲染）。

**分析：** 读取 [`references/prompt-rules.md`](./references/prompt-rules.md)，判断角色类型和图片资质（构图是否正面/微侧面，清晰度是否 ≥1024×1024），确定 `STANDARDIZE_PROMPT`。

**生成角色标准正面图：**

```bash
python3 src/cli.py generate-image \
  --prompt "STANDARDIZE_PROMPT" \
  --source-url "SOURCE_IMAGE_URL" \
  --output "session/角色标准正面图.png" \
  --save-url "session/urls.json" --key "idle_anchor_url"
```

**生成中性帧：**

```bash
IDLE_URL=$(python3 -c "import json; print(json.load(open('session/urls.json'))['idle_anchor_url'])")
python3 src/cli.py generate-image \
  --prompt "保持镜头固定不变，保持人物一致，角色看向镜头，仿佛在聆听一般" \
  --source-url "$IDLE_URL" \
  --output "session/中性帧.png" \
  --save-url "session/urls.json" --key "neutral_anchor_url"
```

**介入点 1 — 角色图确认**

用 Read 工具读取并展示 `session/角色标准正面图.png` 和 `session/中性帧.png`。

等待用户回复：
- 满意 → 继续 Step 1-B
- 重新生成 → 按 `references/prompt-rules.md` 调整 `STANDARDIZE_PROMPT`，重跑 Step 1-A
- 指定修改 → 按反馈调整后重跑

---

### Step 1-B — 角色档案

读取 [`references/profile-format.md`](./references/profile-format.md)，基于角色图 + 描述生成档案内容，然后写入 session：

```bash
python3 -c "
content = '''PROFILE_CONTENT'''
import os; os.makedirs('session', exist_ok=True)
open('session/角色档案.txt', 'w', encoding='utf-8').write(content)
"
python3 src/cli.py save-profile-snapshot \
  --profile "session/角色档案.txt" \
  --output "session/profile_snapshot.json"
```

**介入点 2 — 档案确认**

向用户展示用户字段（姓名/年龄/性格/兴趣等）。

等待用户回复：
- 确认 → 继续 Step 1-C
- 修改某字段 → 按反馈更新 `session/角色档案.txt`，重新执行 `save-profile-snapshot`

---

### Step 1-C — 生产清单 + 5s 预览

**确定场景/事件：**
- 用户描述中已包含 → 直接提取
- 未包含 → 基于档案「兴趣爱好」+「性格风格」自动生成

写入 session：

```bash
python3 -c "
import json, os
os.makedirs('session', exist_ok=True)
data = json.load(open('session/urls.json')) if os.path.exists('session/urls.json') else {}
data['scene'] = 'SCENE_NAME'
data['event'] = 'EVENT_DESCRIPTION'
json.dump(data, open('session/urls.json', 'w'), ensure_ascii=False, indent=2)
"
```

**生成 5s 预览视频：**

```bash
IDLE_URL=$(python3 -c "import json; print(json.load(open('session/urls.json'))['idle_anchor_url'])")
python3 src/cli.py generate-preview \
  --source-url "$IDLE_URL" \
  --output "session/5s预览视频.mp4"
```

向用户展示 mode_production_plan（见文末模板）、场景/事件描述和预览视频路径。

**介入点 3 — 预览确认**

等待用户回复：
- 确认 → 继续 Step 2
- 重新生成 → 调整场景/事件后重跑 `generate-preview`

---

### Step 2 — 状态描述（全自动）

读取 [`references/state-rules.md`](./references/state-rules.md)，基于档案 + 场景/事件生成三段状态描述，写入文件：

```bash
python3 -c "
content = '''STATE_DESCRIPTIONS'''
char_name = 'CHAR_NAME'
open(f'session/{char_name}的场景事件状态描述.txt', 'w', encoding='utf-8').write(content)
"
```

无需确认，直接进入 Step 3。

---

### Step 3 — 批量生成 7 个视频

读取 [`references/prompt-rules.md`](./references/prompt-rules.md)，生成 7 个视频 prompt 后写入 session：

```bash
python3 -c "
import json
data = json.load(open('session/urls.json'))
data['video_prompts'] = {
  'idle_001': 'IDLE_001_PROMPT',
  'idle_002': 'IDLE_002_PROMPT',
  'idle_003': 'IDLE_003_PROMPT',
  'transition_state_change_001': '保持镜头固定不变，保持人物一致，角色看向镜头，仿佛在聆听一般',
  'transition_return_to_idle_001': 'RETURN_PROMPT',
  'listen_001': 'LISTEN_PROMPT',
  'dialogue_base_001': 'DIALOGUE_PROMPT'
}
json.dump(data, open('session/urls.json', 'w'), ensure_ascii=False, indent=2)
"
```

**批量生成：**

```bash
python3 src/cli.py run-workflow \
  --session "session/urls.json" \
  --character-id "CHARACTER_ID" \
  --version "v1" \
  --output-root "output"
```

实时输出每个视频进度。单条失败自动继续其余，失败列表在 stdout 中打印。

---

### Step 4 — 质检 + 打包交付

```bash
python3 src/cli.py verify-package \
  --package-dir "output/CHARACTER_ID_frame_package_v1"

python3 src/cli.py make-demo \
  --source "output/CHARACTER_ID_frame_package_v1/videos/CHARACTER_ID_frame_idle_001_v1.mp4" \
  --output "session/demo.mp4"
```

向用户交付：
- 包目录：`output/CHARACTER_ID_frame_package_v1/`
- 预览文件：`session/demo.mp4`
- 生产清单（✓/✗ 标记每个文件）

---

## 常见故障处理

| 现象 | 原因 | 处理 |
|------|------|------|
| `check-env` 报 `volcenginesdkcore` 缺失 | 未安装火山引擎 SDK | `pip install volcenginesdkcore` |
| `.env 凭据完整` 但 API 报 403 | AK/SK 错误或无即梦 API 权限 | 检查 `.env` 值，确认火山引擎已开通即梦 |
| Video task `expired` | 任务超时（默认 600s） | 检查视频时长参数，单条重新提交 |
| Video task `not_found` | task_id 失效 | 重新提交该条视频 |
| `ffmpeg 未安装` | 可选依赖缺失 | 跳过 `make-demo`，提示用户安装 ffmpeg |
| 7 视频中部分失败 | API 限流或单条异常 | `run-workflow` 自动继续其余；失败条目在 stdout 中打印 |

---

## References

| 文件 | 加载时机 |
|------|---------|
| [`references/prompt-rules.md`](./references/prompt-rules.md) | Step 1-A（确定 standardize_prompt）、Step 3（生成 7 个视频 prompt）、路径 A |
| [`references/profile-format.md`](./references/profile-format.md) | Step 1-B（生成角色档案） |
| [`references/state-rules.md`](./references/state-rules.md) | Step 2（生成三段状态描述） |
| [`references/workflow-mapping.md`](./references/workflow-mapping.md) | 需要查步骤与代码函数/CLI 命令的对应关系时 |

---

## mode_production_plan 模板

```
package_id: {character_id}_frame_package_v1
mode: frame

【预览阶段】
1. 角色标准正面图.png  ✓
2. 中性帧.png          ✓
3. 5s预览视频.mp4      ✓

【批量生产阶段】
1. {id}_frame_idle_001_v1.mp4                        — 长待机，10s
2. {id}_frame_idle_002_v1.mp4                        — 小动作1，10s
3. {id}_frame_idle_003_v1.mp4                        — 小动作2，10s
4. {id}_frame_transition_state_change_001_v1.mp4     — 过渡1，3s
5. {id}_frame_transition_return_to_idle_001_v1.mp4   — 过渡2，3s
6. {id}_frame_listen_001_v1.mp4                      — 聆听，3s
7. {id}_frame_dialogue_base_001_v1.mp4               — 说话，3s
```

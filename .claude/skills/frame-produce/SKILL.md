---
name: frame-produce
description: "OcLife Frame 模式视频素材批量生产。Use when: 生产角色素材、开始frame生产、批量生成视频、生成角色包。完整流程：角色图 → 标准化 → 中性帧 → 档案 → 预览 → 7个视频 → 打包交付。"
argument-hint: "[character_id] (可选，默认 char001)"
user-invocable: true
---

# Frame 模式视频素材批量生产

从角色图输入到完整视频包交付的全自动流程（含3个人工确认节点）。

## 环境

- 项目根目录：`/Users/hualushui/Desktop/for palpal/oclife-frame`
- 凭据：`.env`（JIMENG_ACCESS_KEY_ID / JIMENG_SECRET_ACCESS_KEY）
- 状态文件：`session/urls.json`（跨步骤传递 URL、场景事件、视频 prompts）

---

## Step 0 — 环境检查

```bash
cd "/Users/hualushui/Desktop/for palpal/oclife-frame"
python3 src/cli.py check-env
```

失败则告知用户缺失项，停止。通过则说"环境就绪，开始生产流程"。

---

## Step 1-A — 角色图标准化 + 中性帧

**收集**：请用户提供角色图片 URL + 角色描述（性格、风格、名字等）+ 目标风格（二次元/写实/Q版/3D渲染）。

**分析（Claude 完成）**：判断角色类型，检查图片构图（正/微侧面）和清晰度（≥1024×1024），按 [prompt 规则](./references/prompt-rules.md) 确定 `STANDARDIZE_PROMPT`。

**生成角色标准正面图**：

```bash
cd "/Users/hualushui/Desktop/for palpal/oclife-frame"
python3 src/cli.py generate-image \
  --prompt "STANDARDIZE_PROMPT" \
  --source-url "SOURCE_IMAGE_URL" \
  --output "session/角色标准正面图.png" \
  --save-url "session/urls.json" --key "idle_anchor_url"
```

**生成中性帧**（用上一步返回的 idle_anchor_url）：

```bash
IDLE_URL=$(python3 -c "import json; print(json.load(open('session/urls.json'))['idle_anchor_url'])")
python3 src/cli.py generate-image \
  --prompt "保持镜头固定不变，保持人物一致，角色看向镜头，仿佛在聆听一般" \
  --source-url "$IDLE_URL" \
  --output "session/中性帧.png" \
  --save-url "session/urls.json" --key "neutral_anchor_url"
```

**【介入点 1】** 展示两张图，询问是否满意。不满意则重新生成。

---

## Step 1-B — 角色档案

基于角色图 + 描述，生成角色档案（格式见 [角色档案格式](./references/profile-format.md)）。

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

**【介入点 2】** 展示用户字段（姓名/年龄/性格/兴趣等）给用户确认，可修改。

---

## Step 1-C — 生产清单 + 5s 预览

**确定场景/事件**：
- 用户描述中有 → 直接提取
- 用户描述中没有 → 基于档案「兴趣爱好」+「性格风格」自动生成

将场景/事件写入 session：

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

**生成 5s 预览视频**：

```bash
IDLE_URL=$(python3 -c "import json; print(json.load(open('session/urls.json'))['idle_anchor_url'])")
python3 src/cli.py generate-preview \
  --source-url "$IDLE_URL" \
  --output "session/5s预览视频.mp4"
```

展示 mode_production_plan 清单（见文末模板），场景/事件 + 预览视频一并给用户确认。

**【介入点 3】** 不满意则调整场景/事件后重新生成预览。

---

## Step 2 — 状态描述生成（全自动）

基于档案 + 场景/事件，生成三段状态描述并保存：

```bash
python3 -c "
content = '''STATE_DESCRIPTIONS'''
char_name = 'CHAR_NAME'
open(f'session/{char_name}的场景事件状态描述.txt', 'w', encoding='utf-8').write(content)
"
```

三段描述格式见 [状态描述规则](./references/state-rules.md)。无需用户确认，直接进入 Step 3。

---

## Step 3 — 批量生成 7 个视频

**生成 7 个 prompt（Claude 完成）**，规则见 [视频 prompt 规则](./references/prompt-rules.md)。

将 prompts 写入 session：

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

**批量生成**（CHARACTER_ID 替换为实际值，默认 char001）：

```bash
python3 src/cli.py run-workflow \
  --session "session/urls.json" \
  --character-id "CHARACTER_ID" \
  --version "v1" \
  --output-root "output"
```

实时输出每个视频进度。单条失败自动重试，其余继续。

---

## Step 4 — 质检 + 打包交付

```bash
python3 src/cli.py verify-package \
  --package-dir "output/CHARACTER_ID_frame_package_v1"

python3 src/cli.py make-demo \
  --source "output/CHARACTER_ID_frame_package_v1/videos/CHARACTER_ID_frame_idle_001_v1.mp4" \
  --output "session/demo.mp4"
```

**交付给用户**：
- 告知包目录路径 `output/CHARACTER_ID_frame_package_v1/`
- 告知预览路径 `session/demo.mp4`
- 显示生产清单（✓/✗ 标记每个文件）

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

# Workflow Frame — Agent 批量生成项目素材

> 基于「定格故事（Frame Story）」生成规则，定义 agent 驱动的视频素材生成工作流。
> 第一阶段目标：跑通单角色 × 单场景 × 单事件的完整流程（定格模式，1个故事 = 7个视频）。

---

## 一、范围与目标

| 项目 | 说明 |
|------|------|
| 阶段 | V1：单角色 × 单故事 × 定格模式 |
| 输入 | 角色图片 + 角色描述 + 风格选择 |
| 输出 | `char{id}_frame_package_v1/` 完整视频包 |

---

## 二、流程总览

```
[输入] 角色图片 + 角色描述
        ↓
[Step 0] 环境检查
        ↓
[Step 1-A] 上传图+描述 → 资质检查 → 风格选择 → 角色图标准化 → 生成中性帧
        ↓ 介入点：确认角色图 + 中性帧
[Step 1-B] 生成角色档案 → 生成 profile_snapshot.json
        ↓ 介入点：确认/修改档案
[Step 1-C] 生成 mode_production_plan → 生成5s预览视频
        ↓ 介入点：确认预览视频
[Step 2] 自动生成3个状态描述 → 写入txt（全自动，无介入）
        ↓
[Step 3] 按 mode_production_plan 批量生成7个视频（按命名规范保存）
        ↓
[Step 4] 自动质检 → 写入每条视频 metadata → 生成 manifest.json → 打包
        ↓ 单条失败自动重试
[输出] char{id}_frame_package_v1/ + demo.mp4 交付用户
```

---

## 三、步骤详细说明

### Step 0 — 环境检查

在任何生成操作开始前执行，全部通过才继续；任一失败则告知用户缺失项并停止。

#### 检查项

| 检查项 | 内容 | 失败处理 |
|--------|------|----------|
| Python 版本 | ≥ 3.10 | 提示升级 Python |
| 依赖包 | `requests`、`python-dotenv` 已安装 | 运行 `pip install -r requirements.txt` |
| 凭据文件 | `.env` 存在且包含 `JIMENG_ACCESS_KEY_ID` 和 `JIMENG_SECRET_ACCESS_KEY` | 提示用户补充 `.env` |
| 核心脚本 | `src/cli.py`、`src/jimeng_client.py`、`src/workflow_frame.py` 均存在 | 提示文件缺失 |
| ffmpeg | 系统中可调用 `ffmpeg`（用于生成 demo.mp4） | 警告但不停止，demo 步骤将跳过 |

#### 执行方式

```bash
cd "/Users/hualushui/Desktop/for palpal/oclife-frame"
python3 src/cli.py check-env
```

#### 检查通过输出示例

```
[✓] Python 3.11.4
[✓] requests 2.31.0
[✓] python-dotenv 1.0.0
[✓] .env 凭据完整
[✓] 核心脚本完整
[⚠] ffmpeg 未安装（demo.mp4 生成步骤将跳过）
[✓] session/ 已就绪
[✓] output/ 已就绪

环境就绪，开始生产流程。
```

---

### Step 1 — 角色建立

Step 1 分为三个子步骤，每个子步骤含一个人工确认介入点。

#### Step 1-A｜角色分析与资质检查 + 角色图确认

**输入**：用户上传角色图 + 一段简单的角色描述

**1. Agent分析任务：**

- 判断角色类型（人类 / 动物 / 精灵 / 机械 / AI生命体 / 潮玩等）
- 推荐创建模式（Frame / Daily / Narrative，当前默认 **Frame**）
- 基础资质检查：

| 检查项 | 说明 |
|--------|------|
| 正面形象 | 图中是否有可用的正面或微侧面角色形象 |
| 描述充分 | 用户描述是否足够生成角色档案 |
| 内容合规 | 角色是否符合生产规范（无违规内容） |

```
资质检查不通过 → 告知用户缺失项，提示补充描述或重新上传
资质检查通过 → 进入风格确认
```

**2. 风格选择与角色图标准化：**

用户选择目标风格（二次元 / 写实 / Q版 / 3D渲染 等）

```
用户选择风格 ≠ 上传图风格
→ 上传原图为附件，生成所选风格的角色标准正面图（Case 1）

用户选择风格 = 上传图风格
→ 检查清晰度（≥1024×1024）与构图（正面/微侧面）
    ├── 清晰度不达标，构图达标 → 生成修正清晰度的角色图（Case 2-A）
    ├── 清晰度达标，构图不达标 → 生成修正构图的角色图（Case 2-B）
    ├── 两者均不达标 → 生成修正后的角色图（Case 2-C）
    └── 两者均达标 → 直接使用原图作为角色标准正面图
```

→ 上传角色标准正面图，生成**中性帧**
- Prompt：`保持镜头固定不变，保持人物一致，角色看向镜头，仿佛在聆听一般`

**介入点**：角色标准正面图 + 中性帧同步展示给用户确认，不满意则两张一起重新生成

**Step 1-A 产出物：**
- 角色标准正面图
- 中性帧
- 角色分析结果（角色类型 + 推荐模式）

---

#### Step 1-B｜角色档案确认

Agent 基于角色图 + 分析结果自动生成角色档案，分两个区块：

**用户字段（展示给用户确认）：**

| 字段 | 说明 |
|------|------|
| 姓名 | 自动生成候选，默认选第一个 |
| 代号 | 基于姓名或视觉特征生成 |
| 年龄 | 基于外观推断 |
| 身份来历 | 角色的背景设定与存在定义 |
| 性格风格 | 性格气质方向与行为底色 |
| 标志特征 | 高度独特、可被视觉化呈现的标志性细节 |
| 兴趣爱好 | 日常行为偏好与核心驱动 |

**技术字段（agent自动生成，不需用户填写）：**

| 字段 | 说明 |
|------|------|
| 视觉锚点 | 基于**中性帧**提取，必须保持的外观特征（发型/五官/服装/材质/标志性装饰等） |
| 正向提示词 | 告诉生成模型角色应该长什么样、什么风格、什么气质 |
| 负向提示词 | 告诉生成模型禁止改变的外观、风格、物种等 |
| 动作方向 | 适合的动作 / 不适合的动作 |
| 对话镜头方向 | 半身特写要求（背景、面部、嘴部、表情） |

**介入点**：用户确认用户字段内容，可按需修改；技术字段随档案一并保存。

确认后：
- 角色档案保存为 `角色档案.txt`
- 同步生成 **`profile_snapshot.json`**（角色基础信息存档，供后续模式复用及追溯）
- 存入角色名文件夹

---

#### Step 1-C｜生产清单 + 5s预览确认（Frame模式）

1. 基于角色档案自动生成 **`mode_production_plan`**（Frame模式生产清单）：

**定义**：根据角色生产档案 + 当前模式自动生成的视频生产任务列表。

```
mode_production_plan（Frame 模式）

package_id: char001_frame_package_v1
character_id: char001
mode: frame

【预览阶段】
1. 角色标准正面图.png
2. 中性帧.png
3. 5s预览视频.mp4

【批量生产阶段】
1. char001_frame_idle_001_v1.mp4         — 长待机，10s，首尾帧：角色标准正面图
2. char001_frame_idle_002_v1.mp4         — 小动作1，10s，首尾帧：角色标准正面图
3. char001_frame_idle_003_v1.mp4         — 小动作2，10s，首尾帧：角色标准正面图
4. char001_frame_transition_state_change_001_v1.mp4 — 过渡1，3s，首帧：角色标准正面图，尾帧：中性帧
5. char001_frame_transition_return_to_idle_001_v1.mp4 — 过渡2，3s，首帧：中性帧，尾帧：角色标准正面图
6. char001_frame_listen_001_v1.mp4       — 聆听，3s，首尾帧：中性帧
7. char001_frame_dialogue_base_001_v1.mp4 — 说话，3s，首尾帧：中性帧
```

2. 自动确定**场景**与**事件**：

```
用户角色描述中已包含场景/事件信息
→ 直接提取使用

用户角色描述中未包含
→ agent 基于角色档案（兴趣爱好/性格风格）自动生成一个场景和事件
```

3. 以**角色标准正面图**为首尾帧，生成 **5s 预览视频**
   - Prompt：`保持镜头不变，保持人物的一致性，角色有轻微呼吸起伏，持续做着自己的事情`

4. **介入点**：场景/事件 + 预览视频同步展示给用户确认，不满意则重新生成

**Step 1 产出物：**

| 文件 | 说明 |
|------|------|
| 角色标准正面图.png | 人物基准图 |
| 中性帧.png | 状态3类视频（listen / dialogue_base / state_change尾帧 / return_to_idle首帧）的帧锚点 |
| 角色档案.txt | 用户字段 + 技术字段 |
| profile_snapshot.json | 角色基础信息结构化存档 |
| mode_production_plan | Frame模式视频生产清单 |
| 5s预览视频.mp4 | 确认用，不进最终包 |

---

### Step 2 — 状态描述生成（全自动）

**输入**：Step 1全部产出物

在角色文件夹中创建 txt，命名为 **"[角色名]的场景事件状态描述"**，包含以下字段：

| 字段 | 来源 | 说明 |
|------|------|------|
| 场景 | Step 1锁定 | 单一固定场景名称及描述 |
| 事件 | Step 1锁定 | 一句话：角色正在这个场景里持续做什么 |
| 状态1 - 沉浸 | AI生成 | 3-5句。身体姿态+具体动作+表情/眼神+环境氛围，不看镜头 |
| 状态2 - 微变 | AI生成 | 2-3句。在状态1基础上叠加一个轻微变化，参考事件类型对应的微变方向 |
| 状态3 - 发现 | AI生成 | 3-4句。察觉→确认→回应，视线转向镜头 |

三个状态描述基于**中性帧**生成，遵循「视频生成-定格故事.md」的状态拆解规则与句数要求。

**状态2微变方向参考（按事件类型）：**

| 事件类型 | 微变方向 |
|----------|----------|
| 睡觉/休息 | 轻轻翻身、蹬腿、耳朵动、嘴巴咂一下、调整睡姿 |
| 看书/写字 | 翻一页、调整坐姿、揉眼睛、托腮、轻叹 |
| 画画 | 换笔、歪头看画布、退远端详、调色 |
| 发呆 | 换方向看、轻叹、托腮、抱膝、低头 |
| 玩耍/摆弄物品 | 换一个物品、重新排列、歪头端详、拿起放下 |

**介入点**：无，全自动，直接进入 Step 3。

---

### Step 3 — 批量生成7个视频

**工具**：即梦 API（图生视频，首尾帧模式）
**视频规格**：9:16，1080p
**命名规范**：`{characterId}_frame_{type}_{index}_v{version}.mp4`

#### 生成顺序

```
第一批（可并行）
├── frame_idle_001（长待机）
├── frame_idle_002（小动作1）
└── frame_idle_003（小动作2）

第二批（可并行）
├── frame_transition_state_change_001（过渡1）
├── frame_transition_return_to_idle_001（过渡2）
├── frame_listen_001（聆听）
└── frame_dialogue_base_001（说话）
```

#### 7个视频清单

| 文件名 | 类型 | 来源状态 | 时长 | 首帧 | 尾帧 | 循环 |
|--------|------|----------|:----:|------|------|------|
| `char001_frame_idle_001_v1.mp4` | idle | 状态1 | 10s | 角色标准正面图 | 角色标准正面图 | 无缝循环 |
| `char001_frame_idle_002_v1.mp4` | idle | 状态2 | 10s | 角色标准正面图 | 角色标准正面图 | 触发式，播完回idle_001 |
| `char001_frame_idle_003_v1.mp4` | idle | 状态2 | 10s | 角色标准正面图 | 角色标准正面图 | 触发式，播完回idle_001 |
| `char001_frame_transition_state_change_001_v1.mp4` | transition (state_change) | 状态1→3 | 3s | 角色标准正面图 | 中性帧 | 触发式，唤醒时播放 |
| `char001_frame_transition_return_to_idle_001_v1.mp4` | transition (return_to_idle) | 状态3→1 | 3s | 中性帧 | 角色标准正面图 | 触发式，退出后接idle循环 |
| `char001_frame_listen_001_v1.mp4` | listen | 状态3 | 3s | 中性帧 | 中性帧 | 触发式，播完回idle |
| `char001_frame_dialogue_base_001_v1.mp4` | dialogue_base | 状态3 | 3s | 中性帧 | 中性帧 | 触发式，播完回idle |

---

### Step 4 — 质检 + metadata + 打包

#### 4-A｜自动质检

| 检查项 | 说明 |
|--------|------|
| 角色一致性 | 所有视频中角色外观是否一致 |
| 首尾帧闭环 | 首尾帧是否符合各视频规定的帧锚点（idle用角色标准正面图，状态3类用中性帧） |
| 背景一致性 | 所有视频背景是否一致 |
| 动作自然度 | 动作是否自然，无突变 |

失败策略：单条视频自动重试；重试仍失败则标记，其余正常继续。

#### 4-B｜写入 metadata

每条视频生成对应 metadata，示例：

```json
{
  "id": "char001_frame_idle_001_v1",
  "character_id": "char001",
  "package_id": "char001_frame_package_v1",
  "mode": "frame",
  "type": "idle",
  "duration": 10,
  "loopable": true,
  "start_state": "neutral",
  "end_state": "neutral",
  "next_allowed": ["idle", "transition", "listen"],
  "can_interrupt": true
}
```

#### 4-C｜生成 metadata.json + manifest.json + 打包

- 所有视频 metadata 汇总写入独立 `metadata.json`
- 基于 metadata 生成包级播放说明书 `manifest.json`（含入口、状态机、调度规则）
- 打包为 `char001_frame_package_v1/`

#### 4-D｜Demo 交付

- 从 `frame_idle_001` 截取开头 **1-3s** → 保存为 `demo.mp4`
- 交付用户确认

---

## 四、文件夹结构（输出）

```
char001_frame_package_v1/
├── manifest.json               ← 包级播放说明书（入口、状态机、调度规则）
├── metadata.json               ← 所有视频单条 metadata 汇总
├── profile_snapshot.json       ← 生产时使用的角色基础信息存档
├── videos/
│   ├── char001_frame_idle_001_v1.mp4
│   ├── char001_frame_idle_002_v1.mp4
│   ├── char001_frame_idle_003_v1.mp4
│   ├── char001_frame_transition_state_change_001_v1.mp4
│   ├── char001_frame_transition_return_to_idle_001_v1.mp4
│   ├── char001_frame_listen_001_v1.mp4
│   └── char001_frame_dialogue_base_001_v1.mp4
└── dialogue_base/
    └── （口型/表情驱动资源，后续补充）

[角色名]/                       ← 生产中间文件夹
├── 角色标准正面图.png
├── 中性帧.png
├── 角色档案.txt
├── [角色名]的场景事件状态描述.txt
└── demo.mp4
```

---

## 五、待讨论

- [x] Step 0：环境检查内容
- [x] Step 3：各视频的 prompt 完整策略（见 prompt.md）
- [x] mode_production_plan 的具体格式
- [x] Step 2：场景/事件来源（Step 1-C 中自动确定，有用户描述则提取，否则 agent 基于档案生成）
- [ ] 单角色多故事的扩展规则
- [ ] 多角色批量处理的流程设计

---

> 文档持续更新，记录每次讨论的结论。

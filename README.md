# oclife-frame

OcLife Frame 模式视频素材批量生产工具。输入一张角色图，输出完整的 7 视频角色包，供定格故事（Frame Story）使用。

## 工作流概览

```
角色图 + 角色描述
    ↓
[Step 0] 环境检查
    ↓
[Step 1-A] 角色图标准化 → 生成中性帧          ← 人工确认
    ↓
[Step 1-B] 生成角色档案 → profile_snapshot.json  ← 人工确认
    ↓
[Step 1-C] 生成生产清单 → 5s 预览视频           ← 人工确认
    ↓
[Step 2]  自动生成 3 个状态描述（全自动）
    ↓
[Step 3]  批量生成 7 个视频（即梦 API 首尾帧）
    ↓
[Step 4]  质检 → metadata → manifest → 打包交付
```

## 输出产物

```
char001_frame_package_v1/
├── manifest.json
├── metadata.json
├── profile_snapshot.json
└── videos/
    ├── char001_frame_idle_001_v1.mp4              # 10s，无缝循环
    ├── char001_frame_idle_002_v1.mp4              # 10s，触发式小动作
    ├── char001_frame_idle_003_v1.mp4              # 10s，触发式小动作
    ├── char001_frame_transition_state_change_001_v1.mp4   # 3s，唤醒过渡
    ├── char001_frame_transition_return_to_idle_001_v1.mp4 # 3s，退出过渡
    ├── char001_frame_listen_001_v1.mp4            # 3s，聆听
    └── char001_frame_dialogue_base_001_v1.mp4     # 3s，说话
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置凭据

在项目根目录创建 `.env`：

```
JIMENG_ACCESS_KEY_ID=你的火山引擎 Access Key ID
JIMENG_SECRET_ACCESS_KEY=你的火山引擎 Secret Access Key
```

### 3. 环境检查

```bash
python3 src/cli.py check-env
```

### 4. 启动生产流程（Claude Code Skill）

在 Claude Code 中直接调用：

```
/frame-produce char001
```

或手动调用各步骤 CLI 命令（详见 `docs/workflow-frame.md`）。

## CLI 命令

| 命令 | 说明 |
|------|------|
| `check-env` | 检查 Python 版本、依赖、凭据、核心脚本 |
| `generate-image` | 调用即梦 API 生成单张图片 |
| `generate-preview` | 生成 5s 预览视频 |
| `run-workflow` | 读取 session 状态，运行 Step 3 + Step 4 |
| `save-profile-snapshot` | 将角色档案保存为结构化 JSON |
| `verify-package` | 检查输出包完整性 |
| `make-demo` | 从 idle_001 截取 demo.mp4 |

## 项目结构

```
oclife-frame/
├── src/
│   ├── cli.py              # CLI 入口
│   ├── jimeng_client.py    # 即梦 API 客户端（HMAC-SHA256 鉴权）
│   └── workflow_frame.py   # 完整流程封装
├── docs/
│   ├── workflow-frame.md   # 工作流详细文档
│   └── prompt.md           # 提示词规则
├── .claude/
│   └── skills/frame-produce/
│       ├── SKILL.md        # Claude Code Skill 定义
│       └── references/     # prompt 规则、状态规则、档案格式
├── requirements.txt
└── .env.example            # 凭据模板（需自行创建 .env）
```

## 依赖

- Python ≥ 3.10
- [requests](https://pypi.org/project/requests/)
- [python-dotenv](https://pypi.org/project/python-dotenv/)
- [ffmpeg](https://ffmpeg.org/)（可选，用于生成 demo.mp4）
- 火山引擎 即梦 AI API 账号

## API 说明

底层调用即梦（Jimeng）三个端点：

| 用途 | req_key |
|------|---------|
| 图片生成（I2I） | `jimeng_seedream46_cvtob` |
| 视频首帧（I2V） | `jimeng_ti2v_v30_pro` |
| 视频首尾帧（I2V） | `jimeng_i2v_first_tail_v30_1080` |

鉴权方式：火山引擎 HMAC-SHA256（Region: cn-north-1，Service: cv）。

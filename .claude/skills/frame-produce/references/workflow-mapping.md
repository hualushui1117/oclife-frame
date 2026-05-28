# Workflow Mapping — 步骤 × 函数 × CLI 对应表

| Skill 步骤 | Python 函数 | CLI 命令 | 触发方式 | 人工确认 |
|-----------|------------|---------|---------|---------|
| Step 0 环境检查 | — | `cli.py check-env` | CLI | 否 |
| Step 1-A 标准化+中性帧 | `workflow_frame.step1a_generate_anchors()` | `cli.py generate-image` | CLI（分步）/ Python API（路径 A） | 是（介入点 1） |
| Step 1-B 角色档案 | — | `cli.py save-profile-snapshot` | CLI | 是（介入点 2） |
| Step 1-C 预览视频 | `workflow_frame.step1c_generate_preview()` | `cli.py generate-preview` | CLI（分步）/ Python API（路径 A） | 是（介入点 3） |
| Step 2 状态描述 | — | — | Agent 文本生成，直接写文件 | 否 |
| Step 3 批量视频 | `workflow_frame.step3_generate_videos()` | `cli.py run-workflow` | Python API / CLI | 否 |
| Step 4 打包 | `workflow_frame.step4_write_package()` | `cli.py verify-package` + `make-demo` | Python API / CLI | 否 |
| 一键全跑（路径 A） | `workflow_frame.run()` | — | Python API | 否 |

## session/urls.json 字段说明

| 字段 | 写入时机 | 读取时机 |
|------|---------|---------|
| `idle_anchor_url` | Step 1-A 生成角色标准正面图后 | Step 1-A 生成中性帧、Step 1-C 预览、Step 3 |
| `neutral_anchor_url` | Step 1-A 生成中性帧后 | Step 3 |
| `scene` | Step 1-C 确定场景/事件后 | Step 2 |
| `event` | Step 1-C 确定场景/事件后 | Step 2 |
| `video_prompts` | Step 3 写入前 | `cli.py run-workflow` |

## API 参数速查

| 参数 | 值 |
|------|----|
| 图片生成 req_key | `jimeng_seedream46_cvtob` |
| 视频首帧 req_key | `jimeng_ti2v_v30_pro` |
| 视频首尾帧 req_key | `jimeng_i2v_first_tail_v30_1080` |
| 5s 视频 frames | 121 |
| 10s 视频 frames | 241 |
| 图片生成超时 | 300s |
| 视频生成超时 | 600s |
| 并发策略 | Batch 1（idle ×3）先跑，Batch 2（其余 4 个）后跑，批内并行 |

"""
workflow_frame.py — Frame 模式完整生产流程

覆盖范围（对应 workflow-frame.md）：
  Step 1-A  生成角色标准正面图 + 中性帧（即梦 I2I）
  Step 1-C  生成 5s 预览视频（即梦首帧 I2V）
  Step 3    批量生成 7 个正式视频（即梦首尾帧 I2V）
  Step 4    写入 metadata.json + manifest.json

Step 0-2 的角色分析/档案/状态描述由 Claude agent 交互完成后，
将结果填入 run() 的参数即可触发本脚本完整跑通。
"""

import os
import json
import shutil
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv

from jimeng_client import JimengClient

load_dotenv(Path(__file__).parent.parent / ".env")

CLIENT = JimengClient(
    access_key_id=os.environ["JIMENG_ACCESS_KEY_ID"],
    secret_access_key=os.environ["JIMENG_SECRET_ACCESS_KEY"],
)


# ── Step 1-A: 生成角色标准正面图 + 中性帧 ────────────────────────────────

def step1a_generate_anchors(
    source_image_url: str,
    standardize_prompt: str,
    neutral_frame_prompt: str,
    work_dir: Path,
) -> dict:
    """
    生成两张锚点图并下载到 work_dir。
    本地文件也走 I2I 重新生成，确保标准化。
    返回 {"idle_url": ..., "neutral_url": ..., "idle_path": ..., "neutral_path": ...}
    """
    # 检测本地文件
    local_source = source_image_url.replace("file://", "") if source_image_url.startswith("file://") else source_image_url
    if os.path.isfile(local_source):
        print(f"\n── Step 1-A: 使用本地原图作为参考，重新生成角色标准正面图 ──")
        idle_url = CLIENT.generate_image(
            prompt=standardize_prompt,
            image_paths=[local_source],
        )
        idle_path = work_dir / "角色标准正面图.png"
        CLIENT.download_file(idle_url, str(idle_path))
        print(f"[done] 角色标准正面图 → {idle_path}")

        print(f"\n── Step 1-A: 生成中性帧 ──")
        neutral_url = CLIENT.generate_image(
            prompt=neutral_frame_prompt,
            image_paths=[str(idle_path)],
        )
        neutral_path = work_dir / "中性帧.png"
        CLIENT.download_file(neutral_url, str(neutral_path))
        print(f"[done] 中性帧 → {neutral_path}")

        return {
            "idle_url": idle_url,
            "neutral_url": neutral_url,
            "idle_path": str(idle_path),
            "neutral_path": str(neutral_path),
        }

    # 远程 URL，走 I2I
    print("\n── Step 1-A: 生成角色标准正面图 ──")
    idle_url = CLIENT.generate_image(
        prompt=standardize_prompt,
        image_urls=[source_image_url],
    )
    idle_path = work_dir / "角色标准正面图.png"
    CLIENT.download_file(idle_url, str(idle_path))
    print(f"[done] 角色标准正面图 → {idle_path}")

    print("\n── Step 1-A: 生成中性帧 ──")
    neutral_url = CLIENT.generate_image(
        prompt=neutral_frame_prompt,
        image_urls=[idle_url],
    )
    neutral_path = work_dir / "中性帧.png"
    CLIENT.download_file(neutral_url, str(neutral_path))
    print(f"[done] 中性帧 → {neutral_path}")

    return {
        "idle_url": idle_url,
        "neutral_url": neutral_url,
        "idle_path": str(idle_path),
        "neutral_path": str(neutral_path),
    }


# ── Step 1-C: 生成 5s 预览视频 ───────────────────────────────────────────

def step1c_generate_preview(
    idle_anchor_url: str,
    preview_prompt: str,
    work_dir: Path,
) -> str:
    """生成 5s 预览视频（首尾帧模式，首尾帧=角色标准图）。返回本地保存路径。"""
    print("\n── Step 1-C: 生成 5s 预览视频 ──")
    # Auto-detect local file
    idle_path = None
    if idle_anchor_url.startswith("file://"):
        idle_path = idle_anchor_url.replace("file://", "")
        idle_anchor_url = None
    elif os.path.isfile(idle_anchor_url):
        idle_path = idle_anchor_url
        idle_anchor_url = None
    
    video_url = CLIENT.generate_video(
        prompt=preview_prompt,
        first_frame_url=idle_anchor_url,
        first_frame_path=idle_path,
        last_frame_url=idle_anchor_url,
        last_frame_path=idle_path,
        duration_s=5,
    )
    save_path = work_dir / "5s预览视频.mp4"
    CLIENT.download_file(video_url, str(save_path))
    print(f"[done] 5s预览视频 → {save_path}")
    return str(save_path)


# ── Step 3: 批量生成 7 个正式视频 ────────────────────────────────────────

def _build_video_tasks(
    character_id: str,
    version: str,
    idle_url: str,
    neutral_url: str,
    prompts: dict,
) -> list:
    c, v = character_id, version
    return [
        # ── Batch 1: idle（10s，首尾帧=角色标准正面图）──────────────────
        {"filename": f"{c}_frame_idle_001_{v}.mp4",
         "type": "idle", "duration_s": 10,
         "first_frame": idle_url, "last_frame": idle_url,
         "prompt": prompts["idle_001"]},
        {"filename": f"{c}_frame_idle_002_{v}.mp4",
         "type": "idle", "duration_s": 10,
         "first_frame": idle_url, "last_frame": idle_url,
         "prompt": prompts["idle_002"]},
        {"filename": f"{c}_frame_idle_003_{v}.mp4",
         "type": "idle", "duration_s": 10,
         "first_frame": idle_url, "last_frame": idle_url,
         "prompt": prompts["idle_003"]},
        # ── Batch 2: transition + listen + dialogue（3s）────────────────
        {"filename": f"{c}_frame_transition_state_change_001_{v}.mp4",
         "type": "transition", "duration_s": 3,
         "first_frame": idle_url, "last_frame": neutral_url,
         "prompt": prompts["transition_state_change_001"]},
        {"filename": f"{c}_frame_transition_return_to_idle_001_{v}.mp4",
         "type": "transition", "duration_s": 3,
         "first_frame": neutral_url, "last_frame": idle_url,
         "prompt": prompts["transition_return_to_idle_001"]},
        {"filename": f"{c}_frame_listen_001_{v}.mp4",
         "type": "listen", "duration_s": 3,
         "first_frame": neutral_url, "last_frame": neutral_url,
         "prompt": prompts["listen_001"]},
        {"filename": f"{c}_frame_dialogue_base_001_{v}.mp4",
         "type": "dialogue_base", "duration_s": 3,
         "first_frame": neutral_url, "last_frame": neutral_url,
         "prompt": prompts["dialogue_base_001"]},
    ]


def _submit_and_download(task: dict, videos_dir: Path) -> dict:
    save_path = videos_dir / task["filename"]
    if save_path.exists() and save_path.stat().st_size > 0:
        print(f"[skip] {task['filename']} 已存在 ({save_path.stat().st_size // 1024} KB)")
        return {"filename": task["filename"], "status": "ok", "skipped": True}
    
    print(f"[submit] {task['filename']}")
    # Auto-detect local file paths
    first_url = task["first_frame"]
    last_url = task["last_frame"]
    first_path = None
    last_path = None
    
    for url_var, path_var in [(first_url, "first_path"), (last_url, "last_path")]:
        local = url_var.replace("file://", "") if url_var.startswith("file://") else url_var
        if os.path.isfile(local):
            if path_var == "first_path":
                first_path = local
                first_url = None
            else:
                last_path = local
                last_url = None
    
    task_id = CLIENT.submit_video_first_last(
        prompt=task["prompt"],
        first_frame_url=first_url,
        first_frame_path=first_path,
        last_frame_url=last_url,
        last_frame_path=last_path,
        duration_s=task["duration_s"],
    )
    print(f"[waiting] {task['filename']}  task_id={task_id}")
    video_url = CLIENT.poll_video(task_id)
    save_path = videos_dir / task["filename"]
    CLIENT.download_file(video_url, str(save_path))
    print(f"[done] {task['filename']} → {save_path}")
    return {"filename": task["filename"], "task_id": task_id, "status": "ok"}


def step3_generate_videos(tasks: list, videos_dir: Path, max_workers: int = 4) -> list:
    """Batch 1（idle x3）先跑，Batch 2（其余4个）后跑，批内并行。"""
    results = []
    batches = [("batch1_idle", tasks[:3]), ("batch2_interactive", tasks[3:])]
    for batch_name, batch in batches:
        print(f"\n── Step 3 {batch_name} ──")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_submit_and_download, t, videos_dir): t for t in batch}
            for future in concurrent.futures.as_completed(futures):
                t = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"[ERROR] {t['filename']}: {e}")
                    results.append({"filename": t["filename"], "status": "error", "error": str(e)})
    return results


# ── Step 4: metadata.json + manifest.json ────────────────────────────────

_STATE_MAP = {
    "idle": {
        "start": "neutral", "end": "neutral", "loopable": True,
        "next_allowed": ["idle", "transition", "listen"], "can_interrupt": True,
    },
    "transition_state_change": {
        "start": "neutral", "end": "interactive", "loopable": False,
        "next_allowed": ["listen", "dialogue_base"], "can_interrupt": False,
    },
    "transition_return_to_idle": {
        "start": "interactive", "end": "neutral", "loopable": False,
        "next_allowed": ["idle"], "can_interrupt": False,
    },
    "listen": {
        "start": "interactive", "end": "interactive", "loopable": False,
        "next_allowed": ["dialogue_base", "transition_return_to_idle"], "can_interrupt": True,
    },
    "dialogue_base": {
        "start": "interactive", "end": "interactive", "loopable": False,
        "next_allowed": ["listen", "transition_return_to_idle"], "can_interrupt": True,
    },
}


def _state_key(filename: str) -> str:
    name = Path(filename).stem  # e.g. char001_frame_dialogue_base_001_v1
    for key in ("transition_state_change", "transition_return_to_idle"):
        if key in name:
            return key
    # 匹配 _STATE_MAP 的 key（idle / listen / dialogue_base）
    after_frame = name.split("_frame_")[1]  # dialogue_base_001_v1
    for key in _STATE_MAP.keys():
        if after_frame.startswith(key):
            return key
    fallback = after_frame.split("_")[0]
    if fallback == "dialogue":
        return "dialogue_base"
    return fallback


def step4_write_package(
    character_id: str,
    package_id: str,
    version: str,
    tasks: list,
    package_dir: Path,
) -> None:
    print("\n── Step 4: 写入 metadata.json + manifest.json ──")

    metadata = []
    for task in tasks:
        sm = _STATE_MAP[_state_key(task["filename"])]
        metadata.append({
            "id": Path(task["filename"]).stem,
            "character_id": character_id,
            "package_id": package_id,
            "mode": "frame",
            "type": task["type"],
            "duration": task["duration_s"],
            "loopable": sm["loopable"],
            "start_state": sm["start"],
            "end_state": sm["end"],
            "next_allowed": sm["next_allowed"],
            "can_interrupt": sm["can_interrupt"],
        })

    idle_ids = [m["id"] for m in metadata if m["type"] == "idle"]
    manifest = {
        "package_id": package_id,
        "character_id": character_id,
        "mode": "frame",
        "version": version,
        "entry_point": f"{character_id}_frame_idle_001_{version}",
        "idle_loop": {
            "primary": f"{character_id}_frame_idle_001_{version}",
            "variants": idle_ids[1:],
            "variant_trigger": "random",
            "variant_interval_s": 30,
        },
        "state_machine": {
            "idle_to_interactive": f"{character_id}_frame_transition_state_change_001_{version}",
            "interactive_to_idle": f"{character_id}_frame_transition_return_to_idle_001_{version}",
            "listen": f"{character_id}_frame_listen_001_{version}",
            "dialogue": f"{character_id}_frame_dialogue_base_001_{version}",
        },
        "scheduling": {
            "wake_trigger": "voice_detected",
            "sleep_trigger": "interaction_end",
        },
    }

    with open(package_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    with open(package_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[done] metadata.json + manifest.json → {package_dir}")


# ── 完整入口 ──────────────────────────────────────────────────────────────

def run(
    character_id: str,
    version: str,
    source_image_url: str,       # 用户上传的角色原图 URL
    standardize_prompt: str,     # Step 1-A: 生成角色标准正面图的 I2I prompt
    video_prompts: dict,         # Step 3: 7 个视频的 prompt dict
    output_root: str = ".",
    # 以下两个 prompt 通常固定，无需每次修改
    neutral_frame_prompt: str = "保持镜头固定不变，保持人物一致，角色看向镜头，仿佛在聆听一般",
    preview_prompt: str = "保持镜头不变，保持人物的一致性，角色有轻微呼吸起伏，持续做着自己的事情",
):
    """
    完整 Frame 模式生产流程。

    video_prompts 需包含以下 key：
        idle_001, idle_002, idle_003,
        transition_state_change_001, transition_return_to_idle_001,
        listen_001, dialogue_base_001
    """
    package_id = f"{character_id}_frame_package_{version}"
    root = Path(output_root)

    # 中间产物（图、预览视频）放在角色工作目录
    work_dir = root / character_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 正式视频包
    package_dir = root / package_id
    videos_dir = package_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1-A ──
    anchors = step1a_generate_anchors(
        source_image_url, standardize_prompt, neutral_frame_prompt, work_dir
    )

    # ── Step 1-C ──
    step1c_generate_preview(anchors["idle_url"], preview_prompt, work_dir)

    # ── Step 3 ──
    tasks = _build_video_tasks(
        character_id, version,
        anchors["idle_url"], anchors["neutral_url"],
        video_prompts,
    )
    results = step3_generate_videos(tasks, videos_dir)

    # ── Step 4 ──
    step4_write_package(character_id, package_id, version, tasks, package_dir)

    failed = [r for r in results if r["status"] != "ok"]
    print(f"\n=== 完成: {len(results) - len(failed)}/{len(tasks)} 成功, {len(failed)} 失败 ===")
    if failed:
        for r in failed:
            print(f"  FAIL {r['filename']}: {r.get('error')}")

    return {
        "anchors": anchors,
        "package_dir": str(package_dir),
        "results": results,
    }


# ── 示例入口（填入真实值后运行）────────────────────────────────────────────

if __name__ == "__main__":
    run(
        character_id="char001",
        version="v1",
        source_image_url="https://REPLACE_WITH_USER_SOURCE_IMAGE_URL",
        standardize_prompt="REPLACE_WITH_STYLE_STANDARDIZE_PROMPT",
        video_prompts={
            "idle_001": "固定镜头，镜头和背景都不做任何变化，保持人物一致性，角色动作轻微起伏，专注自己的事情上。",
            "idle_002": "REPLACE_小动作1_prompt",
            "idle_003": "REPLACE_小动作2_prompt",
            "transition_state_change_001": "保持镜头固定不变，保持人物一致，角色看向镜头，仿佛在聆听一般",
            "transition_return_to_idle_001": "REPLACE_过渡2_prompt",
            "listen_001": "REPLACE_聆听_prompt",
            "dialogue_base_001": "REPLACE_说话_prompt",
        },
        output_root=".",
    )

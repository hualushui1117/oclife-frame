"""
cli.py — 供 /frame-produce skill 调用的命令行入口

用法示例：
  python3 src/cli.py generate-image --prompt "..." --source-url "..." --output "session/角色标准正面图.png" --save-url "session/urls.json" --key "idle_anchor_url"
  python3 src/cli.py generate-preview --source-url "..." --output "session/5s预览视频.mp4"
  python3 src/cli.py run-workflow --session "session/urls.json" --character-id "char001" --version "v1" --output-root "output"
  python3 src/cli.py save-profile-snapshot --profile "session/角色档案.txt" --output "session/profile_snapshot.json"
  python3 src/cli.py verify-package --package-dir "output/char001_frame_package_v1"
  python3 src/cli.py make-demo --source "output/.../idle_001.mp4" --output "session/demo.mp4"
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))


def _load_client():
    """Lazy-load JimengClient so check-env can run without deps installed."""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from jimeng_client import JimengClient
    return JimengClient(
        access_key_id=os.environ["JIMENG_ACCESS_KEY_ID"],
        secret_access_key=os.environ["JIMENG_SECRET_ACCESS_KEY"],
    )


# ── helpers ──────────────────────────────────────────────────────────────

def _load_session(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_session(path: str, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── commands ─────────────────────────────────────────────────────────────

def cmd_generate_image(args):
    """Step 1-A: 生成角色标准正面图 或 中性帧。"""
    client = _load_client()
    image_urls = [args.source_url] if args.source_url else None
    url = client.generate_image(
        prompt=args.prompt,
        image_urls=image_urls,
        size=args.size,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    client.download_file(url, args.output)
    print(f"saved → {args.output}")

    if args.save_url and args.key:
        data = _load_session(args.save_url)
        data[args.key] = url
        _save_session(args.save_url, data)
        print(f"url saved to {args.save_url}[{args.key}]")


def cmd_generate_preview(args):
    """Step 1-C: 生成 5s 预览视频（首帧模式）。"""
    client = _load_client()
    video_url = client.generate_preview_video(
        prompt=args.prompt or "保持镜头不变，保持人物的一致性，角色有轻微呼吸起伏，持续做着自己的事情",
        first_frame_url=args.source_url,
        duration_s=5,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    client.download_file(video_url, args.output)
    print(f"saved → {args.output}")


def cmd_run_workflow(args):
    """Step 3+4: 读取 session，批量生成 7 个视频并打包。"""
    from workflow_frame import step3_generate_videos, step4_write_package, _build_video_tasks

    session = _load_session(args.session)
    required = ["idle_anchor_url", "neutral_anchor_url", "video_prompts"]
    missing = [k for k in required if k not in session]
    if missing:
        print(f"ERROR: session missing fields: {missing}", file=sys.stderr)
        sys.exit(1)

    package_id = f"{args.character_id}_frame_package_{args.version}"
    package_dir = Path(args.output_root) / package_id
    videos_dir = package_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    tasks = _build_video_tasks(
        args.character_id, args.version,
        session["idle_anchor_url"], session["neutral_anchor_url"],
        session["video_prompts"],
    )
    results = step3_generate_videos(tasks, videos_dir)
    step4_write_package(args.character_id, package_id, args.version, tasks, package_dir)

    failed = [r for r in results if r["status"] != "ok"]
    print(f"\n完成: {len(results) - len(failed)}/{len(tasks)} 成功, {len(failed)} 失败")
    if failed:
        for r in failed:
            print(f"  FAIL {r['filename']}: {r.get('error')}")
        sys.exit(1)


def cmd_save_profile_snapshot(args):
    """Step 1-B: 将角色档案.txt 转存为 profile_snapshot.json。"""
    profile_text = Path(args.profile).read_text(encoding="utf-8")
    snapshot = {
        "source_file": args.profile,
        "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "raw": profile_text,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved → {args.output}")


def cmd_verify_package(args):
    """Step 4: 检查 package 目录完整性。"""
    pkg = Path(args.package_dir)
    expected_files = [
        "manifest.json",
        "metadata.json",
        "profile_snapshot.json",
    ]
    expected_videos = [
        "videos/",
    ]

    ok = True
    for f in expected_files:
        p = pkg / f
        status = "✓" if p.exists() and p.stat().st_size > 0 else "✗"
        if status == "✗":
            ok = False
        print(f"  {status}  {f}")

    videos_dir = pkg / "videos"
    if videos_dir.exists():
        for mp4 in sorted(videos_dir.glob("*.mp4")):
            size_kb = mp4.stat().st_size // 1024
            status = "✓" if size_kb > 0 else "✗"
            if status == "✗":
                ok = False
            print(f"  {status}  videos/{mp4.name} ({size_kb} KB)")
    else:
        print("  ✗  videos/ 目录不存在")
        ok = False

    sys.exit(0 if ok else 1)


def cmd_make_demo(args):
    """Step 4: 从 idle_001 截取前 3s 生成 demo.mp4（需要 ffmpeg）。"""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", args.source, "-t", "3", "-c", "copy", args.output],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"saved → {args.output}")


def cmd_check_env(args):
    """Step 0: 环境检查。"""
    import importlib
    ok = True

    # Python version
    v = sys.version_info
    status = "✓" if v >= (3, 10) else "✗"
    if status == "✗":
        ok = False
    print(f"[{status}] Python {v.major}.{v.minor}.{v.micro}")

    # Dependencies
    for pkg, import_name in [("requests", "requests"), ("python-dotenv", "dotenv"), ("volcenginesdkcore", "volcenginesdkcore")]:
        try:
            importlib.import_module(import_name)
            print(f"[✓] {pkg}")
        except ImportError:
            print(f"[✗] {pkg} 未安装 → 运行 pip install -r requirements.txt")
            ok = False

    # .env credentials
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    missing_keys = [k for k in ("JIMENG_ACCESS_KEY_ID", "JIMENG_SECRET_ACCESS_KEY")
                    if not os.getenv(k)]
    if missing_keys:
        print(f"[✗] .env 缺少字段: {', '.join(missing_keys)}")
        ok = False
    else:
        print("[✓] .env 凭据完整")

    # Core scripts
    scripts = ["src/cli.py", "src/jimeng_client.py", "src/workflow_frame.py"]
    missing = [s for s in scripts if not (ROOT / s).exists()]
    if missing:
        print(f"[✗] 缺少脚本: {', '.join(missing)}")
        ok = False
    else:
        print("[✓] 核心脚本完整")

    # ffmpeg (optional)
    ffmpeg_ok = subprocess.run(
        ["ffmpeg", "-version"], capture_output=True
    ).returncode == 0
    print(f"[{'✓' if ffmpeg_ok else '⚠'}] ffmpeg {'已安装' if ffmpeg_ok else '未安装（demo.mp4 生成步骤将跳过）'}")

    if ok:
        print("\n环境就绪，开始生产流程。")
    else:
        print("\n环境检查未通过，请修复以上问题后重试。")
        sys.exit(1)


# ── CLI parser ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="cli.py")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate-image
    p = sub.add_parser("generate-image")
    p.add_argument("--prompt", required=True)
    p.add_argument("--source-url", default=None)
    p.add_argument("--output", required=True)
    p.add_argument("--save-url", default=None, help="session JSON file to update")
    p.add_argument("--key", default=None, help="key to store URL under in session JSON")
    p.add_argument("--size", type=int, default=None, help="image area in pixels (e.g. 4194304 for 2048x2048)")

    # generate-preview
    p = sub.add_parser("generate-preview")
    p.add_argument("--source-url", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--prompt", default=None)

    # run-workflow
    p = sub.add_parser("run-workflow")
    p.add_argument("--session", required=True)
    p.add_argument("--character-id", required=True)
    p.add_argument("--version", default="v1")
    p.add_argument("--output-root", default="output")

    # save-profile-snapshot
    p = sub.add_parser("save-profile-snapshot")
    p.add_argument("--profile", required=True)
    p.add_argument("--output", required=True)

    # verify-package
    p = sub.add_parser("verify-package")
    p.add_argument("--package-dir", required=True)

    # make-demo
    p = sub.add_parser("make-demo")
    p.add_argument("--source", required=True)
    p.add_argument("--output", required=True)

    # check-env
    sub.add_parser("check-env")

    args = parser.parse_args()
    {
        "generate-image": cmd_generate_image,
        "generate-preview": cmd_generate_preview,
        "run-workflow": cmd_run_workflow,
        "save-profile-snapshot": cmd_save_profile_snapshot,
        "verify-package": cmd_verify_package,
        "make-demo": cmd_make_demo,
        "check-env": cmd_check_env,
    }[args.command](args)


if __name__ == "__main__":
    main()

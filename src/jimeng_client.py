"""
即梦 (Jimeng) API client — 基于火山引擎官方 SDK signv4 签名 + requests。

APIs:
  - 图片生成 4.6 (I2I):          jimeng_seedream46_cvtob
  - 视频生成 3.0 Pro (首帧):     jimeng_ti2v_v30_pro
  - 视频生成 3.0 1080P (首尾帧): jimeng_i2v_first_tail_v30_1080
"""

import json
import time
import requests


class JimengClient:
    BASE_URL = "https://visual.volcengineapi.com"
    REGION = "cn-north-1"
    SERVICE = "cv"

    REQ_KEY_IMAGE = "jimeng_t2i_v30"
    REQ_KEY_VIDEO_FIRST = "jimeng_ti2v_v30_pro"
    REQ_KEY_VIDEO_FIRST_LAST = "jimeng_i2v_first_tail_v30_1080"

    def __init__(self, access_key_id: str, secret_access_key: str):
        self.ak = access_key_id
        self.sk = secret_access_key

    def _post(self, action: str, body: dict) -> dict:
        body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        query = {"Action": action, "Version": "2022-08-31"}
        from volcenginesdkcore.signv4 import SignerV4
        headers = {"Content-Type": "application/json"}
        SignerV4().sign("/", "POST", headers, body_str, None, query,
                        self.ak, self.sk, self.REGION, self.SERVICE)
        resp = requests.post(self.BASE_URL + "/", headers=headers, params=query,
                             data=body_str.encode("utf-8"), timeout=60)
        resp.raise_for_status()
        return resp.json()

    # ── Image ───────────────────────────────────────────────────────────

    def submit_image(self, prompt: str, image_urls: list = None,
                     width: int = 1080, height: int = 1920) -> str:
        body = {"req_key": self.REQ_KEY_IMAGE, "prompt": prompt,
                "width": width, "height": height, "force_single": True}
        if image_urls:
            body["image_urls"] = image_urls
        r = self._post("CVSync2AsyncSubmitTask", body)
        if r.get("code") != 10000:
            raise RuntimeError(f"Submit failed: {r}")
        return r["data"]["task_id"]

    def poll_image(self, task_id: str, timeout_s: int = 300) -> list:
        body = {"req_key": self.REQ_KEY_IMAGE, "task_id": task_id,
                "req_json": json.dumps({"return_url": True})}
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            r = self._post("CVSync2AsyncGetResult", body)
            if r.get("code") != 10000:
                raise RuntimeError(f"Poll failed: {r}")
            d = r["data"]
            if d["status"] == "done":
                return d.get("image_urls", [])
            if d["status"] in ("not_found", "expired"):
                raise RuntimeError(f"Task {task_id}: {d['status']}")
            time.sleep(5)
        raise TimeoutError(f"Task {task_id} timeout")

    def generate_image(self, prompt: str, image_urls: list = None,
                       width: int = 1080, height: int = 1920) -> str:
        return self.poll_image(self.submit_image(prompt, image_urls, width, height))[0]

    # ── Video (首尾帧) ──────────────────────────────────────────────────

    def submit_video_first_last(self, prompt: str, first_frame_url: str,
                                last_frame_url: str, duration_s: int = 5) -> str:
        frames = 121 if duration_s <= 5 else 241
        body = {"req_key": self.REQ_KEY_VIDEO_FIRST_LAST, "prompt": prompt,
                "image_urls": [first_frame_url, last_frame_url], "frames": frames}
        r = self._post("CVSync2AsyncSubmitTask", body)
        if r.get("code") != 10000:
            raise RuntimeError(f"Submit failed: {r}")
        return r["data"]["task_id"]

    def poll_video(self, task_id: str, req_key: str = None, timeout_s: int = 600) -> str:
        req_key = req_key or self.REQ_KEY_VIDEO_FIRST_LAST
        body = {"req_key": req_key, "task_id": task_id}
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            r = self._post("CVSync2AsyncGetResult", body)
            if r.get("code") != 10000:
                raise RuntimeError(f"Poll failed: {r}")
            d = r["data"]
            if d["status"] == "done":
                return d["video_url"]
            if d["status"] in ("not_found", "expired"):
                raise RuntimeError(f"Task {task_id}: {d['status']}")
            time.sleep(10)
        raise TimeoutError(f"Task {task_id} timeout")

    def generate_video(self, prompt: str, first_frame_url: str,
                       last_frame_url: str, duration_s: int = 5) -> str:
        return self.poll_video(
            self.submit_video_first_last(prompt, first_frame_url, last_frame_url, duration_s))

    # ── Download ─────────────────────────────────────────────────────────

    def download_file(self, url: str, save_path: str) -> None:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

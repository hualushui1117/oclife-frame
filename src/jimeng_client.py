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
from typing import Optional
from urllib.parse import urlencode


class JimengClient:
    BASE_URL = "https://visual.volcengineapi.com"
    REGION = "cn-north-1"
    SERVICE = "cv"

    REQ_KEY_IMAGE = "jimeng_seedream46_cvtob"
    REQ_KEY_VIDEO_FIRST = "jimeng_ti2v_v30_pro"
    REQ_KEY_VIDEO_FIRST_LAST = "jimeng_i2v_first_tail_v30_1080"

    def __init__(self, access_key_id: str, secret_access_key: str):
        self.ak = access_key_id
        self.sk = secret_access_key

    def _post(self, action: str, body: dict) -> dict:
        """POST request via SDK-signed headers."""
        body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        query = {"Action": action, "Version": "2022-08-31"}

        from volcenginesdkcore.signv4 import SignerV4
        signer = SignerV4()
        headers = {"content-type": "application/json"}
        signer.sign("/", "POST", headers, body_str, None, query,
                    self.ak, self.sk, self.REGION, self.SERVICE)

        resp = requests.post(
            self.BASE_URL + "/",
            headers=headers,
            params=query,
            data=body_str.encode("utf-8"),
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Image generation (I2I) ──────────────────────────────────────────

    def submit_image(
        self,
        prompt: str,
        image_urls: Optional[list] = None,
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        body = {
            "req_key": self.REQ_KEY_IMAGE,
            "prompt": prompt,
            "width": width,
            "height": height,
            "force_single": True,
        }
        if image_urls:
            body["image_urls"] = image_urls
        result = self._post("CVSync2AsyncSubmitTask", body)
        if result.get("ResponseMetadata", {}).get("Error"):
            raise RuntimeError(f"Image submit failed: {result}")
        return result["data"]["task_id"]

    def poll_image(self, task_id: str, timeout_s: int = 300) -> list:
        body = {
            "req_key": self.REQ_KEY_IMAGE,
            "task_id": task_id,
            "req_json": json.dumps({"return_url": True}),
        }
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            result = self._post("CVSync2AsyncGetResult", body)
            err = result.get("ResponseMetadata", {}).get("Error")
            if err:
                raise RuntimeError(f"Image poll failed: {err}")
            data = result["data"]
            if data["status"] == "done":
                return data["image_urls"]
            if data["status"] in ("not_found", "expired"):
                raise RuntimeError(f"Image task {task_id}: {data['status']}")
            time.sleep(5)
        raise TimeoutError(f"Image task {task_id} timed out after {timeout_s}s")

    def generate_image(
        self, prompt: str, image_urls: Optional[list] = None,
        width: int = 1080, height: int = 1920,
    ) -> str:
        task_id = self.submit_image(prompt, image_urls, width, height)
        urls = self.poll_image(task_id)
        return urls[0]

    # ── Video generation — 首尾帧 ────────────────────────────────────────

    def submit_video_first_last(
        self, prompt: str, first_frame_url: str, last_frame_url: str,
        duration_s: int = 5,
    ) -> str:
        frames = 121 if duration_s <= 5 else 241
        body = {
            "req_key": self.REQ_KEY_VIDEO_FIRST_LAST,
            "prompt": prompt,
            "image_urls": [first_frame_url, last_frame_url],
            "frames": frames,
        }
        result = self._post("CVSync2AsyncSubmitTask", body)
        if result.get("ResponseMetadata", {}).get("Error"):
            raise RuntimeError(f"Video submit failed: {result}")
        return result["data"]["task_id"]

    def poll_video(self, task_id: str, req_key: Optional[str] = None,
                   timeout_s: int = 600) -> str:
        req_key = req_key or self.REQ_KEY_VIDEO_FIRST_LAST
        body = {"req_key": req_key, "task_id": task_id}
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            result = self._post("CVSync2AsyncGetResult", body)
            err = result.get("ResponseMetadata", {}).get("Error")
            if err:
                raise RuntimeError(f"Video poll failed: {err}")
            data = result["data"]
            if data["status"] == "done":
                return data["video_url"]
            if data["status"] in ("not_found", "expired"):
                raise RuntimeError(f"Video task {task_id}: {data['status']}")
            time.sleep(10)
        raise TimeoutError(f"Video task {task_id} timed out after {timeout_s}s")

    def generate_video(
        self, prompt: str, first_frame_url: str, last_frame_url: str,
        duration_s: int = 5,
    ) -> str:
        task_id = self.submit_video_first_last(
            prompt, first_frame_url, last_frame_url, duration_s
        )
        return self.poll_video(task_id)

    # ── Video generation — 首帧 only ─────────────────────────────────────

    def submit_video_first_frame(
        self, prompt: str, first_frame_url: str,
        duration_s: int = 5, aspect_ratio: str = "9:16",
    ) -> str:
        frames = 121 if duration_s <= 5 else 241
        body = {
            "req_key": self.REQ_KEY_VIDEO_FIRST,
            "prompt": prompt,
            "image_urls": [first_frame_url],
            "frames": frames,
            "aspect_ratio": aspect_ratio,
        }
        result = self._post("CVSync2AsyncSubmitTask", body)
        if result.get("ResponseMetadata", {}).get("Error"):
            raise RuntimeError(f"Video (首帧) submit failed: {result}")
        return result["data"]["task_id"]

    def generate_preview_video(
        self, prompt: str, first_frame_url: str, duration_s: int = 5,
    ) -> str:
        task_id = self.submit_video_first_frame(prompt, first_frame_url, duration_s)
        return self.poll_video(task_id, req_key=self.REQ_KEY_VIDEO_FIRST)

    # ── Download ─────────────────────────────────────────────────────────

    def download_file(self, url: str, save_path: str) -> None:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

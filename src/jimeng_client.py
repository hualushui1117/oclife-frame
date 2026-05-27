"""
即梦 (Jimeng) API client — 火山引擎 HMAC-SHA256 signing + async task polling.

APIs wrapped:
  - 图片生成 4.6 (I2I):          jimeng_seedream46_cvtob
  - 视频生成 3.0 Pro (首帧):     jimeng_ti2v_v30_pro
  - 视频生成 3.0 1080P (首尾帧): jimeng_i2v_first_tail_v30_1080
"""

import hashlib
import hmac
import json
import time
import datetime
import requests
from typing import Optional


class JimengClient:
    BASE_URL = "https://visual.volcengineapi.com"
    REGION = "cn-north-1"
    SERVICE = "cv"
    VERSION = "2022-08-31"

    REQ_KEY_IMAGE = "jimeng_seedream46_cvtob"
    REQ_KEY_VIDEO_FIRST = "jimeng_ti2v_v30_pro"
    REQ_KEY_VIDEO_FIRST_LAST = "jimeng_i2v_first_tail_v30_1080"

    def __init__(self, access_key_id: str, secret_access_key: str):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

    # ── Auth / signing ──────────────────────────────────────────────────

    def _hmac_sha256(self, key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signing_key(self, date: str) -> bytes:
        k = self._hmac_sha256(("VOLC" + self.secret_access_key).encode("utf-8"), date)
        k = self._hmac_sha256(k, self.REGION)
        k = self._hmac_sha256(k, self.SERVICE)
        k = self._hmac_sha256(k, "request")
        return k

    def _build_auth_headers(self, action: str, body_str: str) -> dict:
        now = datetime.datetime.utcnow()
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        date = now.strftime("%Y%m%d")
        host = "visual.volcengineapi.com"
        query = f"Action={action}&Version={self.VERSION}"

        body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
        canonical_headers = (
            f"content-type:application/json\n"
            f"host:{host}\n"
            f"x-date:{x_date}\n"
        )
        signed_headers = "content-type;host;x-date"
        canonical_request = "\n".join([
            "POST", "/", query,
            canonical_headers, signed_headers, body_hash,
        ])

        cr_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        credential_scope = f"{date}/{self.REGION}/{self.SERVICE}/request"
        string_to_sign = "\n".join([
            "HMAC-SHA256", x_date, credential_scope, cr_hash,
        ])

        sig = hmac.new(
            self._get_signing_key(date),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        auth = (
            f"HMAC-SHA256 Credential={self.access_key_id}/{credential_scope},"
            f" SignedHeaders={signed_headers},"
            f" Signature={sig}"
        )
        return {
            "Content-Type": "application/json",
            "Host": host,
            "X-Date": x_date,
            "Authorization": auth,
        }

    def _post(self, action: str, body: dict) -> dict:
        body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        headers = self._build_auth_headers(action, body_str)
        url = f"{self.BASE_URL}?Action={action}&Version={self.VERSION}"
        resp = requests.post(url, headers=headers, data=body_str.encode("utf-8"))
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
        """Submit I2I image generation task. Returns task_id."""
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
        if result.get("code") != 10000:
            raise RuntimeError(f"Image submit failed: {result}")
        return result["data"]["task_id"]

    def poll_image(self, task_id: str, timeout_s: int = 300) -> list:
        """Poll image task until done. Returns list of image URLs."""
        body = {
            "req_key": self.REQ_KEY_IMAGE,
            "task_id": task_id,
            "req_json": json.dumps({"return_url": True}),
        }
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            result = self._post("CVSync2AsyncGetResult", body)
            if result.get("code") != 10000:
                raise RuntimeError(f"Image poll failed: {result}")
            data = result["data"]
            if data["status"] == "done":
                return data["image_urls"]
            if data["status"] in ("not_found", "expired"):
                raise RuntimeError(f"Image task {task_id}: {data['status']}")
            time.sleep(5)
        raise TimeoutError(f"Image task {task_id} timed out after {timeout_s}s")

    def generate_image(
        self,
        prompt: str,
        image_urls: Optional[list] = None,
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        """Submit + poll image generation. Returns first image URL."""
        task_id = self.submit_image(prompt, image_urls, width, height)
        urls = self.poll_image(task_id)
        return urls[0]

    # ── Video generation — 首尾帧 (main, all 7 production videos) ───────

    def submit_video_first_last(
        self,
        prompt: str,
        first_frame_url: str,
        last_frame_url: str,
        duration_s: int = 5,
    ) -> str:
        """Submit 首尾帧 video generation. Returns task_id.
        image_urls = [first_frame, last_frame] per API spec.
        """
        frames = 121 if duration_s <= 5 else 241  # 5s=121, 10s=241
        body = {
            "req_key": self.REQ_KEY_VIDEO_FIRST_LAST,
            "prompt": prompt,
            "image_urls": [first_frame_url, last_frame_url],
            "frames": frames,
        }
        result = self._post("CVSync2AsyncSubmitTask", body)
        if result.get("code") != 10000:
            raise RuntimeError(f"Video submit failed: {result}")
        return result["data"]["task_id"]

    def poll_video(
        self,
        task_id: str,
        req_key: Optional[str] = None,
        timeout_s: int = 600,
    ) -> str:
        """Poll video task until done. Returns video URL (valid 1h)."""
        req_key = req_key or self.REQ_KEY_VIDEO_FIRST_LAST
        body = {"req_key": req_key, "task_id": task_id}
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            result = self._post("CVSync2AsyncGetResult", body)
            if result.get("code") != 10000:
                raise RuntimeError(f"Video poll failed: {result}")
            data = result["data"]
            if data["status"] == "done":
                return data["video_url"]
            if data["status"] in ("not_found", "expired"):
                raise RuntimeError(f"Video task {task_id}: {data['status']}")
            time.sleep(10)
        raise TimeoutError(f"Video task {task_id} timed out after {timeout_s}s")

    def generate_video(
        self,
        prompt: str,
        first_frame_url: str,
        last_frame_url: str,
        duration_s: int = 5,
    ) -> str:
        """Submit + poll 首尾帧 video. Returns video URL."""
        task_id = self.submit_video_first_last(
            prompt, first_frame_url, last_frame_url, duration_s
        )
        return self.poll_video(task_id)

    # ── Video generation — 首帧 only (5s preview) ───────────────────────

    def submit_video_first_frame(
        self,
        prompt: str,
        first_frame_url: str,
        duration_s: int = 5,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit 首帧 video generation (for 5s preview). Returns task_id."""
        frames = 121 if duration_s <= 5 else 241
        body = {
            "req_key": self.REQ_KEY_VIDEO_FIRST,
            "prompt": prompt,
            "image_urls": [first_frame_url],
            "frames": frames,
            "aspect_ratio": aspect_ratio,
        }
        result = self._post("CVSync2AsyncSubmitTask", body)
        if result.get("code") != 10000:
            raise RuntimeError(f"Video (首帧) submit failed: {result}")
        return result["data"]["task_id"]

    def generate_preview_video(
        self,
        prompt: str,
        first_frame_url: str,
        duration_s: int = 5,
    ) -> str:
        """Submit + poll 首帧 preview video. Returns video URL."""
        task_id = self.submit_video_first_frame(prompt, first_frame_url, duration_s)
        return self.poll_video(task_id, req_key=self.REQ_KEY_VIDEO_FIRST)

    # ── File download utility ───────────────────────────────────────────

    def download_file(self, url: str, save_path: str) -> None:
        """Download a URL (image or video) to local path."""
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

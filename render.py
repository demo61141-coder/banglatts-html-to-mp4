# -*- coding: utf-8 -*-
"""HTML অ্যানিমেশন → MP4 রেন্ডারার (headless Chromium + ffmpeg).

পদ্ধতি: Playwright-এর ভিডিও রেকর্ডিং পুরো ভিউপোর্ট ধরে — তাই canvas-এর
ছবি আর DOM ওভারলে (HUD লেখা) দুটোই MP4-এ আসে। শুধু canvas ক্যাপচার
করলে HUD লেখাগুলো হারিয়ে যেত।

প্রবাহ:
  1. headless Chromium-এ HTML খোলা হয় (file:// URL)।
  2. পেজের TOTAL_DURATION (যদি থাকে) পড়ে সময় ঠিক করা হয়।
  3. ভিউপোর্টের মাঝখানে ক্লিক — start overlay থাকলে অ্যানিমেশন শুরু হয়।
  4. রিয়েল-টাইমে রেকর্ড (৫৫ সেকেন্ডের অ্যানিমেশন = ৫৫ সেকেন্ড রেকর্ড)।
  5. ffmpeg দিয়ে WebM → H.264 MP4 (yuv420p, faststart); অডিও থাকলে
     AAC হিসেবে জুড়ে দেওয়া হয় (ছোট অডিওতে নীরবতা দিয়ে প্যাড করা হয়)।
"""
import subprocess
import sys
import time
from pathlib import Path

FFMPEG = "ffmpeg"

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--mute-audio",
    "--autoplay-policy=no-user-gesture-required",
    "--force-device-scale-factor=1",
    "--hide-scrollbars",
]


def _launch(playwright):
    """Chromium চালু করো; ব্রাউজার না থাকলে আগে ডাউনলোড করে নাও।

    channel="chromium" — পুরো Chromium বিল্ড ব্যবহার হয় (headless shell
    নয়), তাই শুধু এই একটাই ডাউনলোড লাগে।
    """
    try:
        return playwright.chromium.launch(
            headless=True, channel="chromium", args=CHROMIUM_ARGS)
    except Exception as exc:  # noqa: BLE001 - missing browser is expected once
        if "Executable doesn't exist" not in str(exc):
            raise
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                       check=True)
        return playwright.chromium.launch(
            headless=True, channel="chromium", args=CHROMIUM_ARGS)


def detect_duration(page, manual_s: float, auto: bool = True) -> float:
    """auto চালু থাকলে পেজের TOTAL_DURATION থাকলে সেটা, নাহলে হাতে দেওয়া সময়।"""
    if auto:
        try:
            v = page.evaluate(
                "typeof window.TOTAL_DURATION === 'number' ? window.TOTAL_DURATION : null")
            if v and float(v) > 0:
                return float(v)
        except Exception:  # noqa: BLE001 - fall back to manual duration
            pass
    return float(manual_s)


def record_html_to_mp4(html_path, duration_s: float, width: int, height: int,
                       audio_path=None, progress_cb=None, workdir=None,
                       auto_duration: bool = True):
    """HTML ফাইল → MP4। ফেরত: (mp4_path, info dict)।

    progress_cb(stage, frac, message) — stage: 'browser' | 'record' |
    'encode' | 'done'; frac: 0..1 (record চলাকালীন) বা None।
    """
    from playwright.sync_api import sync_playwright

    html_path = Path(html_path)
    workdir = Path(workdir) if workdir else Path.cwd()
    workdir.mkdir(parents=True, exist_ok=True)
    video_dir = workdir / "video"
    video_dir.mkdir(exist_ok=True)

    def report(stage, frac, msg):
        if progress_cb:
            progress_cb(stage, frac, msg)

    report("browser", None, "ব্রাউজার চালু হচ্ছে…")
    with sync_playwright() as p:
        browser = _launch(p)
        try:
            t0 = time.monotonic()
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                record_video_dir=str(video_dir),
                record_video_size={"width": width, "height": height},
            )
            page = context.new_page()
            page.goto(html_path.as_uri())
            page.wait_for_load_state("load")
            page.wait_for_timeout(800)  # ফন্ট / প্রথম ফ্রেম বসতে দাও
            duration = detect_duration(page, duration_s, auto=auto_duration)
            report("record", 0.0,
                   f"রেকর্ড চলছে — মোট {duration:.0f} সেকেন্ডের অ্যানিমেশন…")
            # মাঝখানে ক্লিক: start overlay থাকলে অ্যানিমেশন শুরু হবে
            page.mouse.click(width // 2, height // 2)
            t_click = time.monotonic()
            offset = max(0.0, t_click - t0)
            # রেকর্ড: duration + 0.5s বাড়তি (শেষের দিকে কাটার জন্য)
            end_at = t_click + duration + 0.5
            while True:
                now = time.monotonic()
                if now >= end_at:
                    break
                elapsed = now - t_click
                report("record", min(1.0, elapsed / max(duration, 1)),
                       f"রেকর্ড চলছে… {elapsed:.0f} / {duration:.0f} সেকেন্ড")
                time.sleep(0.5)
            video = page.video
            context.close()
            webm_path = Path(video.path())
        finally:
            browser.close()

    report("encode", None, "MP4 এনকোড হচ্ছে (ffmpeg)…")
    mp4_path = workdir / "output.mp4"
    cmd = [FFMPEG, "-y", "-v", "error",
           "-ss", f"{offset:.2f}", "-i", str(webm_path)]
    if audio_path:
        cmd += ["-i", str(audio_path)]
    cmd += ["-t", f"{duration:.2f}",
            "-map", "0:v:0"]
    if audio_path:
        cmd += ["-map", "1:a:0", "-af", "apad", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "21", "-preset", "veryfast",
            "-movflags", "+faststart"]
    if audio_path:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += [str(mp4_path)]
    subprocess.run(cmd, check=True)

    info = {
        "duration_s": round(duration, 2),
        "width": width,
        "height": height,
        "offset_s": round(offset, 2),
        "size_bytes": mp4_path.stat().st_size,
        "audio": bool(audio_path),
    }
    report("done", 1.0, "শেষ!")
    return mp4_path, info


def probe(path):
    """ffprobe দিয়ে (duration, width, height, vcodec, acodec) বের করো।"""
    import json
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "audio"), None)
    return {
        "duration_s": round(float(data.get("format", {}).get("duration", 0)), 2),
        "width": video.get("width"),
        "height": video.get("height"),
        "vcodec": video.get("codec_name"),
        "fps": video.get("avg_frame_rate"),
        "acodec": audio.get("codec_name") if audio else None,
        "size_bytes": int(data.get("format", {}).get("size", 0)),
    }

# -*- coding: utf-8 -*-
"""HTML অ্যানিমেশন → MP4 (Streamlit Community Cloud).

অ্যানিমেটেড HTML ফাইল আপলোড করুন — সার্ভার headless Chromium-এ সেটা
চালিয়ে রেকর্ড করে H.264 MP4 বানিয়ে দেবে। চাইলে অডিও (wav/mp3) জুড়ে
দেওয়া যায় — সেটা MP4-এর সাথে মিশিয়ে দেওয়া হয়।
"""
import os
import subprocess
import tempfile
import time
from pathlib import Path

import streamlit as st

import render

RESOLUTIONS = {
    "৭২০x১২৮০ (৯:১৬, ডিফল্ট)": (720, 1280),
    "৫৪০x৯৬০ (৯:১৬, হালকা)": (540, 960),
    "১০৮০x১৯২০ (৯:১৬ HD)": (1080, 1920),
}

AUDIO_EXTS = ["wav", "mp3", "m4a", "aac", "flac", "ogg"]


def fmt_size(n: int) -> str:
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f} MB"
    return f"{n / 1024:.0f} KB"


def main():
    st.set_page_config(page_title="HTML → MP4", page_icon="🎬", layout="centered")
    st.title("🎬 HTML অ্যানিমেশন → MP4")
    st.write("অ্যানিমেটেড HTML ফাইল দিন — সার্ভার সেটা চালিয়ে রেকর্ড করে MP4 "
             "বানিয়ে দেবে। Canvas-এর ছবি আর লেখা (HUD) — দুটোই ভিডিওতে আসবে।")

    html_file = st.file_uploader("HTML ফাইল", type=["html", "htm"])
    audio_file = st.file_uploader(
        "অডিও ফাইল (ঐচ্ছিক — থাকলে MP4-এ জুড়ে দেওয়া হবে)",
        type=AUDIO_EXTS)

    res_label = st.selectbox("রেজোলিউশন", list(RESOLUTIONS.keys()), index=0)
    width, height = RESOLUTIONS[res_label]

    auto_dur = st.checkbox("সময় অটো নাও (পেজের TOTAL_DURATION থেকে, যদি থাকে)",
                           value=True)
    manual_s = st.number_input("সময় — সেকেন্ড (অটো না পেলে এটা ব্যবহার হবে)",
                               min_value=5, max_value=600, value=55, step=5)

    st.info("⏱️ রেন্ডার রিয়েল-টাইমে হয়: ৫৫ সেকেন্ডের অ্যানিমেশন বানাতে "
            "রেকর্ড ৫৫ সেকেন্ড + এনকোড আরও কিছু সময় লাগবে। পাতা বন্ধ করবেন না। "
            "প্রথমবার চালু হতে ব্রাউজার ডাউনলোডের জন্য কয়েক মিনিট লাগতে পারে।")

    if st.button("🎬 MP4 বানাও", type="primary", use_container_width=True):
        if html_file is None:
            st.warning("আগে HTML ফাইল দিন।")
            st.stop()
        status = st.empty()
        bar = st.progress(0)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = Path(tmp)
                html_path = tmpdir / "page.html"
                html_path.write_bytes(html_file.getbuffer())
                audio_path = None
                if audio_file is not None:
                    ext = audio_file.name.rsplit(".", 1)[-1].lower()
                    audio_path = tmpdir / f"audio.{ext}"
                    audio_path.write_bytes(audio_file.getbuffer())

                def progress_cb(stage, frac, msg):
                    status.write(msg)
                    if stage == "record" and frac is not None:
                        bar.progress(min(1.0, frac))
                    elif stage == "encode":
                        bar.progress(0.95)
                    elif stage == "done":
                        bar.progress(1.0)

                t0 = time.time()
                mp4_path, info = render.record_html_to_mp4(
                    html_path, float(manual_s),
                    width, height, audio_path=audio_path,
                    progress_cb=progress_cb, workdir=tmpdir,
                    auto_duration=auto_dur)
                mp4_bytes = mp4_path.read_bytes()
                elapsed = time.time() - t0

            status.success(
                f"শেষ! ভিডিও {info['duration_s']:.0f} সেকেন্ড • "
                f"{info['width']}x{info['height']} • {fmt_size(info['size_bytes'])}"
                f"{' • অডিওসহ' if info['audio'] else ''} • "
                f"মোট সময় লেগেছে {elapsed:.0f} সেকেন্ড")
            st.video(mp4_bytes, format="video/mp4")
            st.download_button("⬇️ MP4 ডাউনলোড", mp4_bytes,
                               file_name="animation.mp4", mime="video/mp4",
                               use_container_width=True)
        except subprocess.CalledProcessError as exc:
            status.error(f"ffmpeg-এ সমস্যা হয়েছে: {exc}")
        except Exception as exc:  # noqa: BLE001 - show the real error
            status.error(f"বানানো যায়নি: {exc}")


if __name__ == "__main__":
    main()

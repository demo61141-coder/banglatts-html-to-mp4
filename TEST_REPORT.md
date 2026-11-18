# টেস্ট রিপোর্ট — HTML অ্যানিমেশন → MP4

তারিখ: ২০২৬-১১-১৮ | পরিবেশ: এই VM (Ubuntu, root) | Python 3.12.3

## সংস্করণ

- streamlit 1.67.0, playwright 1.65.2
- Chromium: Chrome for Testing 159.0.8154.6 (playwright chromium v1255)
- ffmpeg 8.1.2 (system, /usr/bin/ffmpeg)
- Playwright-এর নিজের ffmpeg: ffmpeg-1013 (ভিডিও রেকর্ডিংয়ের জন্য লাগে)

## পরীক্ষার উপাদান

- HTML: `/home/hatch/workspace/user/files/gemini-code-1794983685556.html`
  (সুনামগঞ্জের নৌপথে ইজারা ও চাঁদাবাজি — ৯:১৬ ডকুমেন্টারি, TOTAL_DURATION = 55.0,
  canvas + DOM HUD ওভারলে, চালু হতে start overlay-তে ক্লিক লাগে)
- অডিও: `/home/hatch/workspace/soja-sotto/news1_rakib/news1_rakib.wav`
  (রাকিব কণ্ঠ, ৪৮.৬ সেকেন্ড, 22050 Hz)

## পরীক্ষা ১ — ভিডিও-শুধু রেন্ডার (৭২০x১২৮০, অটো সময়)

- সময় লেগেছে: ৭৪ সেকেন্ড (৫৫ সেকেন্ড রেকর্ড + ~১৯ সেকেন্ড এনকোড)
- ফাইল: `test_outputs/run1/output.mp4` (৩.৮ MB)
- ffprobe:

```
duration: 55.000000, size: 3795027
streams: [("video", "h264", 720, 1280, "25/1")]
```

- মাঝখানের ফ্রেম (t=27s) বের করে দেখা হয়েছে: গড় উজ্জ্বলতা ২৪.৯
  (০ হলে কালো হতো — ডকুমেন্টারি অন্ধকার থিমের, তাই কম; আসল কনটেন্ট আছে)
  ফাইল: `test_outputs/mid_frame.png`
- ✅ duration ~৫৫ সেকেন্ড, ৭২০x১২৮০, h264 — সব মিলেছে

## পরীক্ষা ২ — অডিওসহ রেন্ডার (রাকিব কণ্ঠ mux)

- সময় লেগেছে: ৭৫ সেকেন্ড
- ফাইল: `test_outputs/run2/output.mp4` (৪.৪ MB)
- ffprobe:

```
duration: 55.000000, size: 4439364
streams: [("video", "h264", 720, 1280, "25/1"), ("audio", "aac", sample_rate 22050)]
```

- ✅ MP4-এ অডিও স্ট্রিম আছে (AAC); অডিও ৪৮.৬ সেকেন্ড হলেও ভিডিও পুরো
  ৫৫ সেকেন্ড — বাকি সময় নীরবতা দিয়ে প্যাড করা হয়েছে

## পরীক্ষা ৩ — Streamlit অ্যাপ স্মোক টেস্ট

- লোকালি চালিয়ে HTTP 200, লগে কোনো error/traceback নেই

## সেটআপে যা সমস্যা হয়েছিল (আর সমাধান)

1. `playwright install chromium` দুইবার ব্যর্থ — বড় ডাউনলোড (১৯৯ MB)
   মাঝপথে (১৩৬ MB) কেটে যাচ্ছিল। সমাধান: curl দিয়ে resume সহ সরাসরি
   Google-এর Chrome-for-Testing zip নামানো হয়েছে
   (`storage.googleapis.com/chrome-for-testing-public/159.0.8154.6/linux64/chrome-linux64.zip`),
   তারপর `~/.cache/ms-playwright/chromium-1255/chrome-linux64/`-এ বসানো হয়েছে।
2. Playwright headless-এ ডিফল্টভাবে headless-shell খোঁজে — সমাধান:
   `launch(channel="chromium")` দিয়ে পুরো Chromium ব্যবহার করা হয়েছে।
3. ভিডিও রেকর্ডিংয়ে Playwright-এর নিজের ffmpeg লাগে —
   `playwright install ffmpeg` (২.২ MB) দিয়ে মেটানো হয়েছে।
4. হাতে বসানো ব্রাউজার `playwright install` চালালে মুছে ফেলছিল
   ("Removing unused browser") — সমাধান: `INSTALLATION_COMPLETE` ও
   `DEPENDENCIES_VALIDATED` মার্কার ফাইল বসানো হয়েছে।
   ⚠️ Streamlit Cloud-এ প্রথমবার `playwright install chromium` চালালে
   সেখানে এই সমস্যা হওয়ার কথা নয় (সেখানেই ডাউনলোড হবে) — তবে নেটওয়ার্ক
   ধীর হলে প্রথম রান কয়েক মিনিট নিতে পারে।

## সীমাবদ্ধতা

- রিয়েল-টাইম রেন্ডার: ৫৫ সেকেন্ডের অ্যানিমেশন = ৫৫ সেকেন্ড রেকর্ড +
  এনকোড ~২০ সেকেন্ড। fast-forward করা যায় না।
- ফ্রেমরেট ২৫ fps (Playwright-এর রেকর্ডিং)।
- পেজের নিজের শব্দ (Web Audio) রেকর্ড হয় না — শুধু আপলোড করা অডিও
  ফাইল MP4-এ জোড়া দেওয়া যায়।
- RAM: headless Chromium + Streamlit মিলিয়ে ~৫০০ MB–১ GB; একসাথে একটাই
  রেন্ডার করা নিরাপদ (ফ্রি টিয়ারে)।
- রেকর্ড শুরুর ~১ সেকেন্ড (পেজ লোড + ক্লিক) অটো কেটে ফেলা হয়, তাই
  MP4 ঠিক `TOTAL_DURATION` দৈর্ঘ্যের হয়।

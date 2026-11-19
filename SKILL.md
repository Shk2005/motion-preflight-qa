---
name: motion-preflight-qa
description: Automated pre-flight and post-render quality assurance for motion graphics, AI-coded videos (HyperFrames, Remotion, HTML/GSAP), and short-form social ads (Instagram Reels, TikTok, YouTube Shorts, LinkedIn). Audits codecs, pixel format (yuv420p), faststart streaming flags, EBU R128 loudness (-14 LUFS / -1 dBTP), dead black hooks, renders a 6-frame platform safe-zone QA contact sheet, and masters delivery-ready MP4s. Use whenever verifying, fixing, or preparing a rendered video for client delivery or social upload.
---

# Motion Preflight QA

Deterministic broadcast and social-platform quality gate for code-rendered motion graphics and short-form video ads. Built to eliminate blind re-renders, cropped captions, muted/crushed audio, and iOS/QuickTime playback bugs.

## Prerequisites

- **Python 3.9+** (standard library only — no third-party Python packages required)
- **FFmpeg & FFprobe** on `PATH`

## Standard QA Workflow (Run Before Every Delivery)

### Step 1: Audit the rendered video
Run the 8-gate technical audit against the target platform (`reels`, `tiktok`, `shorts`, `youtube`, `linkedin`, `square`, or `auto`):

```bash
python3 scripts/audit_video.py path/to/video.mp4 --platform reels
```

Use `--json` for machine-readable output when chaining into automated pipelines.

**What it verifies:**
1. **Container & Codec:** H.264 (`libx264`) or HEVC MP4 compatibility.
2. **Pixel Format (`yuv420p`):** Catches `yuv444p` / 10-bit exports that render as black screens in QuickTime, Safari, and Instagram iOS.
3. **Web Faststart (`moov` before `mdat`):** Verifies instant progressive mobile playback without buffering delays.
4. **Aspect Ratio & Resolution:** Checks match against target platform dimensions (e.g., `1080x1920` for 9:16 vertical).
5. **Frame Rate Consistency:** Verifies clean standard FPS (`24`, `30`, `60`, or `120`) and flags non-standard variable frame rates.
6. **Hook Integrity (Black-Frame Scan):** Flags any dead black intro (> 0.25 s at start) or unexpected black gaps mid-video.
7. **Audio Loudness (EBU R128):** Measures Integrated Loudness (`I` in LUFS) and True Peak (`TP` in dBTP) against the `-14 LUFS` / `-1.0 dBTP` social standard.
8. **File Size & Bitrate Budget:** Flags bloated film-grain exports that trigger aggressive platform re-compression.

### Step 2: Generate the Safe-Zone Contact Sheet
Generate a 6-frame visual proof sheet with pixel-accurate platform HUD danger zones masked in translucent red and the title-safe perimeter outlined in green:

```bash
python3 scripts/safe_zone_overlay.py path/to/video.mp4 --platform reels --out qa_contact_sheet.png
```

Inspect `qa_contact_sheet.png` (visually or with an image-reading tool):
- **Red zones = UI hazard areas** (top header, right like/comment/share rail, bottom caption/audio drawer).
- **Green box = Title-safe zone.** Any headline, stat, product callout, or CTA touching red MUST be repositioned before delivery.
- To inspect a single problem timestamp at full resolution, add `--at <seconds> --out proof_frame.png`.

### Step 3: Auto-Master for Delivery (if any technical check warns or fails)
Fix pixel format, inject `+faststart`, apply two-pass EBU R128 loudness normalization (`-14 LUFS`, `-1.0 dBTP`), and optimize bitrate cleanly:

```bash
python3 scripts/fix_delivery.py path/to/video.mp4 --out path/to/video_master.mp4 --crf 20
```

Use `--crf 23` for heavy film-grain or noisy backgrounds to shrink file size without mushy typography. Then re-run Step 1 on the mastered file to confirm a **100/100 PASS**.

## Reference Documentation

- `references/platform-safe-zones.md` — Exact 2026 safe-zone coordinates and pixel margins for Instagram Reels, TikTok, YouTube Shorts, LinkedIn, and 16:9 widescreen.
- `references/delivery-specs.md` — Codec, color space, loudness, bitrate, and common code-to-video failure fixes.

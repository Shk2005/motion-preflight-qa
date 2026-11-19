#!/usr/bin/env python3
"""
Motion Preflight QA — Platform Safe-Zone Overlay & 6-Frame Contact Sheet Generator.
Burns pixel-accurate platform HUD hazard masks (translucent red) and title-safe
perimeter (green) directly via FFmpeg drawbox filters. Zero Python image deps.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Normalized unsafe margin fractions: (top, bottom, left, right)
SAFE_ZONES = {
    "reels": {
        "label": "Instagram Reels (9:16)",
        "top": 0.14,      # Top status bar + Reels camera/title header
        "bottom": 0.22,   # Username, caption preview, audio marquee, nav bar
        "left": 0.05,     # Edge bezel buffer
        "right": 0.16,    # Like, comment, share, remix, options rail
    },
    "tiktok": {
        "label": "TikTok (9:16)",
        "top": 0.12,      # Following/For You tabs + live/search icons
        "bottom": 0.24,   # Creator handle, description, sound ticker, bottom nav
        "left": 0.05,
        "right": 0.17,    # Profile avatar, like, comment, bookmark, share, disc
    },
    "shorts": {
        "label": "YouTube Shorts (9:16)",
        "top": 0.12,      # Search + menu bar
        "bottom": 0.20,   # Subscribe button, title, music pill
        "left": 0.05,
        "right": 0.15,    # Thumbs up/down, comment, share, remix
    },
    "youtube": {
        "label": "YouTube / 16:9 Title Safe",
        "top": 0.08,
        "bottom": 0.14,   # Scrubber bar + captions band
        "left": 0.08,
        "right": 0.08,
    },
    "linkedin": {
        "label": "LinkedIn Feed Safe",
        "top": 0.08,
        "bottom": 0.16,
        "left": 0.06,
        "right": 0.06,
    },
    "square": {
        "label": "1:1 Square Feed Safe",
        "top": 0.08,
        "bottom": 0.12,
        "left": 0.08,
        "right": 0.08,
    },
}


def probe_video_info(video_path: Path) -> tuple[int, int, float]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    vstream = next(s for s in data["streams"] if s["codec_type"] == "video")
    width = int(vstream["width"])
    height = int(vstream["height"])
    duration = float(data.get("format", {}).get("duration") or vstream.get("duration") or 1.0)
    return width, height, duration


def build_overlay_filter(width: int, height: int, platform: str) -> str:
    z = SAFE_ZONES[platform]
    top_px = int(round(height * z["top"]))
    bot_px = int(round(height * z["bottom"]))
    left_px = int(round(width * z["left"]))
    right_px = int(round(width * z["right"]))

    safe_x = left_px
    safe_y = top_px
    safe_w = max(1, width - left_px - right_px)
    safe_h = max(1, height - top_px - bot_px)
    mid_h = safe_h

    # Translucent crimson masks on hazard edges + crisp emerald title-safe frame
    filters = [
        f"drawbox=x=0:y=0:w={width}:h={top_px}:color=red@0.35:t=fill",
        f"drawbox=x=0:y={height - bot_px}:w={width}:h={bot_px}:color=red@0.35:t=fill",
        f"drawbox=x=0:y={top_px}:w={left_px}:h={mid_h}:color=red@0.28:t=fill",
        f"drawbox=x={width - right_px}:y={top_px}:w={right_px}:h={mid_h}:color=red@0.35:t=fill",
        f"drawbox=x={safe_x}:y={safe_y}:w={safe_w}:h={safe_h}:color=lime@0.92:t=4",
    ]
    return ",".join(filters)


def render_single_frame(video_path: Path, timestamp: float, vf: str, out_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-ss", f"{timestamp:.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-vf", vf,
            str(out_path),
        ],
        check=True,
    )


def render_contact_sheet(video_path: Path, platform: str, out_path: Path, tile_width: int = 420) -> dict:
    width, height, duration = probe_video_info(video_path)
    if platform == "auto":
        ratio = width / height if height else 1.0
        platform = "reels" if abs(ratio - 9 / 16) < 0.08 else ("square" if abs(ratio - 1.0) < 0.08 else "youtube")

    # 6 key moments: hook (0.4s), 20%, 40%, 60%, 80%, CTA (end - 0.3s)
    timestamps = [
        min(0.4, max(0.0, duration * 0.05)),
        duration * 0.20,
        duration * 0.40,
        duration * 0.60,
        duration * 0.80,
        max(0.0, duration - 0.3),
    ]
    overlay_vf = build_overlay_filter(width, height, platform)
    scaled_vf = f"{overlay_vf},scale={tile_width}:-2"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        frame_paths = []
        for idx, ts in enumerate(timestamps):
            fp = tmp / f"frame_{idx:02d}.png"
            render_single_frame(video_path, ts, scaled_vf, fp)
            frame_paths.append(fp)

        # Stitch 6 frames into a crisp 3x2 grid with dark 12px padding
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for fp in frame_paths:
            cmd.extend(["-i", str(fp)])
        cmd.extend([
            "-filter_complex",
            "[0:v][1:v][2:v][3:v][4:v][5:v]xstack=inputs=6:layout=0_0|w0+12_0|w0+w1+24_0|0_h0+12|w0+12_h0+12|w0+w1+24_h0+12:fill=0x111318",
            "-frames:v", "1",
            str(out_path),
        ])
        subprocess.run(cmd, check=True)

    z = SAFE_ZONES[platform]
    return {
        "output": str(out_path),
        "platform": platform,
        "platform_label": z["label"],
        "video_size": f"{width}x{height}",
        "safe_box_px": {
            "x": int(round(width * z["left"])),
            "y": int(round(height * z["top"])),
            "width": int(round(width * (1.0 - z["left"] - z["right"]))),
            "height": int(round(height * (1.0 - z["top"] - z["bottom"]))),
        },
        "sampled_timestamps_s": [round(t, 2) for t in timestamps],
    }


def main():
    parser = argparse.ArgumentParser(description="Render platform safe-zone overlay proof frame or 6-up QA contact sheet.")
    parser.add_argument("video", help="Path to input video")
    parser.add_argument("--platform", choices=["auto", *SAFE_ZONES.keys()], default="auto")
    parser.add_argument("--out", default="qa_contact_sheet.png", help="Output PNG path")
    parser.add_argument("--at", type=float, default=None, help="Optional single timestamp (seconds) for full-res proof frame")
    args = parser.parse_args()

    video_path = Path(args.video)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.at is not None:
        width, height, _ = probe_video_info(video_path)
        platform = args.platform
        if platform == "auto":
            ratio = width / height if height else 1.0
            platform = "reels" if abs(ratio - 9 / 16) < 0.08 else ("square" if abs(ratio - 1.0) < 0.08 else "youtube")
        vf = build_overlay_filter(width, height, platform)
        render_single_frame(video_path, args.at, vf, out_path)
        print(json.dumps({"output": str(out_path), "platform": platform, "timestamp_s": args.at}, indent=2))
    else:
        result = render_contact_sheet(video_path, args.platform, out_path)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

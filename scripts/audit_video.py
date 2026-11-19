#!/usr/bin/env python3
"""
Motion Preflight QA — 8-Gate Technical Broadcast & Social Video Auditor.
Uses Python standard library + ffprobe/ffmpeg only. Zero external dependencies.
"""

import argparse
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

PLATFORM_SPECS = {
    "reels": {
        "label": "Instagram Reels (9:16)",
        "expected_ratio": 9 / 16,
        "min_w": 1080,
        "min_h": 1920,
        "target_lufs": -14.0,
        "lufs_tol": 2.0,
        "max_tp": -1.0,
        "max_mb_per_min": 120.0,
    },
    "tiktok": {
        "label": "TikTok (9:16)",
        "expected_ratio": 9 / 16,
        "min_w": 1080,
        "min_h": 1920,
        "target_lufs": -14.0,
        "lufs_tol": 2.0,
        "max_tp": -1.0,
        "max_mb_per_min": 120.0,
    },
    "shorts": {
        "label": "YouTube Shorts (9:16)",
        "expected_ratio": 9 / 16,
        "min_w": 1080,
        "min_h": 1920,
        "target_lufs": -14.0,
        "lufs_tol": 2.0,
        "max_tp": -1.0,
        "max_mb_per_min": 150.0,
    },
    "youtube": {
        "label": "YouTube / Widescreen (16:9)",
        "expected_ratio": 16 / 9,
        "min_w": 1920,
        "min_h": 1080,
        "target_lufs": -14.0,
        "lufs_tol": 2.0,
        "max_tp": -1.0,
        "max_mb_per_min": 250.0,
    },
    "linkedin": {
        "label": "LinkedIn Feed (4:5 or 16:9)",
        "expected_ratio": None,
        "min_w": 1080,
        "min_h": 1080,
        "target_lufs": -14.0,
        "lufs_tol": 2.5,
        "max_tp": -1.0,
        "max_mb_per_min": 150.0,
    },
    "square": {
        "label": "Square Feed (1:1)",
        "expected_ratio": 1.0,
        "min_w": 1080,
        "min_h": 1080,
        "target_lufs": -14.0,
        "lufs_tol": 2.0,
        "max_tp": -1.0,
        "max_mb_per_min": 120.0,
    },
}


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def check_faststart(file_path: Path) -> bool | None:
    """Inspect top-level MP4/MOV atoms to check whether 'moov' precedes 'mdat'."""
    if file_path.suffix.lower() not in {".mp4", ".mov", ".m4v"}:
        return None
    moov_pos = None
    mdat_pos = None
    try:
        with file_path.open("rb") as f:
            file_size = file_path.stat().st_size
            pos = 0
            while pos + 8 <= file_size:
                f.seek(pos)
                header = f.read(8)
                if len(header) < 8:
                    break
                size, box_type = struct.unpack(">I4s", header)
                if size == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        break
                    size = struct.unpack(">Q", ext)[0]
                elif size == 0:
                    size = file_size - pos
                if size < 8:
                    break
                if box_type == b"moov" and moov_pos is None:
                    moov_pos = pos
                elif box_type == b"mdat" and mdat_pos is None:
                    mdat_pos = pos
                if moov_pos is not None and mdat_pos is not None:
                    break
                pos += size
    except OSError:
        return None
    if moov_pos is None or mdat_pos is None:
        return None
    return moov_pos < mdat_pos


def parse_fps(rate_str: str) -> float:
    if not rate_str or rate_str == "0/0":
        return 0.0
    if "/" in rate_str:
        num, den = rate_str.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    return float(rate_str)


def probe_media(video_path: Path) -> dict:
    proc = run_cmd([
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ])
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"ffprobe failed on {video_path}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def measure_loudness(video_path: Path) -> dict | None:
    proc = run_cmd([
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i", str(video_path),
        "-af", "ebur128=peak=true",
        "-f", "null",
        "-",
    ])
    stderr = proc.stderr
    # Grab the Summary block at the end of ebur128 output
    summary_idx = stderr.rfind("Summary:")
    block = stderr[summary_idx:] if summary_idx != -1 else stderr

    i_match = re.search(r"I:\s+(-?\d+(?:\.\d+)?)\s+LUFS", block)
    tp_match = re.search(r"Peak:\s+(-?\d+(?:\.\d+)?)\s+dBFS", block)
    lra_match = re.search(r"LRA:\s+(-?\d+(?:\.\d+)?)\s+LU", block)

    if not i_match:
        return None
    return {
        "integrated_lufs": float(i_match.group(1)),
        "true_peak_dbtp": float(tp_match.group(1)) if tp_match else None,
        "lra_lu": float(lra_match.group(1)) if lra_match else None,
    }


def detect_black_frames(video_path: Path) -> list[dict]:
    proc = run_cmd([
        "ffmpeg",
        "-hide_banner",
        "-i", str(video_path),
        "-vf", "blackdetect=d=0.25:pix_th=0.08",
        "-an",
        "-f", "null",
        "-",
    ])
    segments = []
    for line in proc.stderr.splitlines():
        if "black_start:" in line:
            m = re.search(
                r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)",
                line,
            )
            if m:
                segments.append({
                    "start": float(m.group(1)),
                    "end": float(m.group(2)),
                    "duration": float(m.group(3)),
                })
    return segments


def infer_platform(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "youtube"
    ratio = width / height
    if abs(ratio - (9 / 16)) < 0.08:
        return "reels"
    if abs(ratio - 1.0) < 0.08:
        return "square"
    if abs(ratio - (16 / 9)) < 0.08:
        return "youtube"
    return "linkedin"


def audit_video(video_path: Path, platform: str = "auto") -> dict:
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    meta = probe_media(video_path)
    streams = meta.get("streams", [])
    fmt = meta.get("format", {})

    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not vstream:
        raise RuntimeError("No video stream found in file.")

    width = int(vstream.get("width", 0))
    height = int(vstream.get("height", 0))
    codec = vstream.get("codec_name", "unknown")
    pix_fmt = vstream.get("pix_fmt", "unknown")
    fps = round(parse_fps(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate", "0/0")), 2)
    duration = float(fmt.get("duration") or vstream.get("duration") or 0.0)
    size_bytes = video_path.stat().st_size
    size_mb = round(size_bytes / (1024 * 1024), 2)

    if platform == "auto":
        platform = infer_platform(width, height)
    spec = PLATFORM_SPECS[platform]

    checks = []
    score = 100
    fixes = []

    def add_check(name: str, status: str, detail: str, penalty: int = 0, fix: str | None = None):
        nonlocal score
        score = max(0, score - penalty)
        checks.append({"gate": name, "status": status, "detail": detail})
        if fix:
            fixes.append(fix)

    # Gate 1: Codec
    if codec in {"h264", "hevc"}:
        add_check("Codec", "PASS", f"{codec} (universally supported)")
    else:
        add_check(
            "Codec",
            "WARN",
            f"{codec} may fail on mobile/social ingest; prefer h264",
            penalty=15,
            fix="Transcode to H.264 with scripts/fix_delivery.py",
        )

    # Gate 2: Pixel format
    if pix_fmt == "yuv420p":
        add_check("Pixel Format", "PASS", "yuv420p (QuickTime/iOS/social safe)")
    else:
        add_check(
            "Pixel Format",
            "FAIL",
            f"{pix_fmt} breaks playback on Safari, QuickTime, and Instagram iOS",
            penalty=25,
            fix="Re-encode with -pix_fmt yuv420p via scripts/fix_delivery.py",
        )

    # Gate 3: Faststart moov atom
    faststart = check_faststart(video_path)
    if faststart is True:
        add_check("Faststart (moov atom)", "PASS", "moov precedes mdat (instant mobile start)")
    elif faststart is False:
        add_check(
            "Faststart (moov atom)",
            "WARN",
            "moov atom is at end of file (delays mobile playback start)",
            penalty=10,
            fix="Remux or re-encode with -movflags +faststart via scripts/fix_delivery.py",
        )
    else:
        add_check("Faststart (moov atom)", "PASS", "N/A for non-MP4 container")

    # Gate 4: Resolution & Aspect Ratio
    ratio = width / height if height else 0.0
    ratio_ok = spec["expected_ratio"] is None or abs(ratio - spec["expected_ratio"]) < 0.05
    res_ok = width >= spec["min_w"] and height >= spec["min_h"]
    if ratio_ok and res_ok:
        add_check("Resolution & Aspect", "PASS", f"{width}x{height} matches {spec['label']}")
    elif not ratio_ok:
        add_check(
            "Resolution & Aspect",
            "FAIL",
            f"{width}x{height} (ratio {ratio:.2f}) does not match {spec['label']}",
            penalty=20,
            fix=f"Re-frame composition natively for {spec['label']} (avoid blind cropping)",
        )
    else:
        add_check(
            "Resolution & Aspect",
            "WARN",
            f"{width}x{height} is below recommended {spec['min_w']}x{spec['min_h']}",
            penalty=10,
            fix=f"Render at minimum {spec['min_w']}x{spec['min_h']}",
        )

    # Gate 5: Frame Rate
    standard_fps = [23.98, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0, 120.0]
    if any(abs(fps - s) < 0.15 for s in standard_fps):
        add_check("Frame Rate", "PASS", f"{fps} fps (clean standard cadence)")
    else:
        add_check(
            "Frame Rate",
            "WARN",
            f"{fps} fps is non-standard and may cause judder after platform transcode",
            penalty=10,
            fix="Render at constant 30 fps or 60 fps",
        )

    # Gate 6: Hook & Black Frame Scan
    black_segments = detect_black_frames(video_path)
    intro_black = [b for b in black_segments if b["start"] < 0.25]
    if intro_black:
        dur = intro_black[0]["duration"]
        add_check(
            "Hook Black-Frame Scan",
            "FAIL",
            f"Dead black intro detected ({dur:.2f}s at start) — hurts 0-1s retention",
            penalty=20,
            fix="Start visible hook visual on frame 0 (0.00s)",
        )
    elif black_segments:
        add_check(
            "Hook Black-Frame Scan",
            "WARN",
            f"{len(black_segments)} black gap(s) detected mid-video",
            penalty=5,
            fix="Review black timestamps to confirm they are intentional cuts",
        )
    else:
        add_check("Hook Black-Frame Scan", "PASS", "No dead black intros or unintentional gaps")

    # Gate 7: Audio Loudness (EBU R128)
    loudness = None
    if astream:
        loudness = measure_loudness(video_path)
        if loudness:
            lufs = loudness["integrated_lufs"]
            tp = loudness["true_peak_dbtp"]
            lufs_ok = abs(lufs - spec["target_lufs"]) <= spec["lufs_tol"]
            tp_ok = tp is None or tp <= spec["max_tp"] + 0.15
            if lufs_ok and tp_ok:
                add_check(
                    "Audio Loudness (EBU R128)",
                    "PASS",
                    f"{lufs:.1f} LUFS, True Peak {tp:.1f} dBTP (target {spec['target_lufs']:.0f} LUFS / <= {spec['max_tp']:.1f} dBTP)",
                )
            else:
                issues = []
                if not lufs_ok:
                    issues.append(f"loudness {lufs:.1f} LUFS (target {spec['target_lufs']:.0f} ±{spec['lufs_tol']:.0f})")
                if not tp_ok:
                    issues.append(f"true peak {tp:.1f} dBTP exceeds {spec['max_tp']:.1f} dBTP (clipping risk)")
                add_check(
                    "Audio Loudness (EBU R128)",
                    "WARN",
                    "; ".join(issues),
                    penalty=15,
                    fix="Run scripts/fix_delivery.py for 2-pass -14 LUFS / -1.0 dBTP normalization",
                )
        else:
            add_check("Audio Loudness (EBU R128)", "WARN", "Could not measure audio loudness", penalty=5)
    else:
        add_check(
            "Audio Loudness (EBU R128)",
            "WARN",
            "No audio track detected (silent videos underperform on Reels/TikTok)",
            penalty=10,
            fix="Add voiceover, SFX, or subtle music before publishing",
        )

    # Gate 8: File Size / Bitrate Efficiency
    mb_per_min = (size_mb / (duration / 60.0)) if duration > 0 else 0.0
    if duration > 0 and mb_per_min > spec["max_mb_per_min"]:
        add_check(
            "File Size Budget",
            "WARN",
            f"{size_mb:.1f} MB for {duration:.1f}s ({mb_per_min:.0f} MB/min) — high bitrate risks heavy platform re-compression",
            penalty=10,
            fix="Re-encode with scripts/fix_delivery.py --crf 23",
        )
    else:
        add_check("File Size Budget", "PASS", f"{size_mb:.2f} MB for {duration:.2f}s")

    overall = "PASS" if all(c["status"] == "PASS" for c in checks) else (
        "FAIL" if any(c["status"] == "FAIL" for c in checks) else "WARN"
    )

    return {
        "file": str(video_path),
        "platform": platform,
        "platform_label": spec["label"],
        "overall": overall,
        "score": score,
        "metadata": {
            "width": width,
            "height": height,
            "codec": codec,
            "pix_fmt": pix_fmt,
            "fps": fps,
            "duration_s": round(duration, 2),
            "size_mb": size_mb,
            "has_audio": astream is not None,
            "faststart": faststart,
            "loudness": loudness,
            "black_segments": black_segments,
        },
        "checks": checks,
        "recommended_fixes": fixes,
    }


def format_markdown(report: dict) -> str:
    lines = [
        f"# Motion Preflight QA Report — {report['overall']} ({report['score']}/100)",
        "",
        f"- **File:** `{report['file']}`",
        f"- **Target Platform:** {report['platform_label']}",
        f"- **Specs:** {report['metadata']['width']}x{report['metadata']['height']} @ {report['metadata']['fps']} fps | {report['metadata']['duration_s']}s | {report['metadata']['size_mb']} MB",
        "",
        "| Gate | Status | Details |",
        "|---|---|---|",
    ]
    for c in report["checks"]:
        lines.append(f"| {c['gate']} | **{c['status']}** | {c['detail']} |")

    if report["recommended_fixes"]:
        lines.extend(["", "## Recommended Fixes"])
        for i, fix in enumerate(report["recommended_fixes"], 1):
            lines.append(f"{i}. {fix}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="8-gate technical QA audit for motion graphics & social videos.")
    parser.add_argument("video", help="Path to input video (.mp4 / .mov)")
    parser.add_argument(
        "--platform",
        choices=["auto", *PLATFORM_SPECS.keys()],
        default="auto",
        help="Target platform profile (default: auto-detect from aspect ratio)",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON report")
    args = parser.parse_args()

    report = audit_video(Path(args.video), args.platform)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_markdown(report))

    sys.exit(0 if report["overall"] != "FAIL" else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Motion Preflight QA — Social & Client Delivery Masterer.
Fixes pixel format (yuv420p), injects +faststart, optimizes H.264 CRF,
and performs broadcast two-pass EBU R128 loudness normalization (-14 LUFS / -1.0 dBTP).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from audit_video import audit_video


def measure_loudnorm_pass1(video_path: Path, target_i: float, target_tp: float, target_lra: float) -> dict | None:
    af = f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i", str(video_path),
            "-af", af,
            "-vn",
            "-f", "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", proc.stderr)
    if not match:
        return None
    return json.loads(match.group(0))


def master_video(
    input_path: Path,
    output_path: Path,
    crf: int = 20,
    target_i: float = -14.0,
    target_tp: float = -1.0,
    target_lra: float = 11.0,
    platform: str = "auto",
) -> dict:
    before = audit_video(input_path, platform)
    has_audio = before["metadata"]["has_audio"]

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-crf", str(crf),
        "-preset", "medium",
        "-movflags", "+faststart",
    ]

    if has_audio:
        stats = measure_loudnorm_pass1(input_path, target_i, target_tp, target_lra)
        if stats and stats.get("input_i") != "-inf":
            af = (
                f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
                f"measured_I={stats['input_i']}:"
                f"measured_LRA={stats['input_lra']}:"
                f"measured_TP={stats['input_tp']}:"
                f"measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}:"
                f"linear=true"
            )
            cmd.extend(["-af", af])
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "48000"])
    else:
        cmd.append("-an")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd.append(str(output_path))
    subprocess.run(cmd, check=True)

    after = audit_video(output_path, before["platform"])
    return {
        "input": str(input_path),
        "output": str(output_path),
        "before_score": before["score"],
        "after_score": after["score"],
        "before_overall": before["overall"],
        "after_overall": after["overall"],
        "before_meta": before["metadata"],
        "after_meta": after["metadata"],
    }


def main():
    parser = argparse.ArgumentParser(description="Master a video for clean social/client delivery.")
    parser.add_argument("input", help="Path to source video")
    parser.add_argument("--out", required=True, help="Path to mastered output MP4")
    parser.add_argument("--crf", type=int, default=20, help="H.264 CRF quality (18-23, default 20)")
    parser.add_argument("--lufs", type=float, default=-14.0, help="Target Integrated Loudness (default -14.0)")
    parser.add_argument("--tp", type=float, default=-1.0, help="Target True Peak dBTP (default -1.0)")
    parser.add_argument("--platform", default="auto", help="Platform profile for before/after audit")
    args = parser.parse_args()

    result = master_video(
        Path(args.input),
        Path(args.out),
        crf=args.crf,
        target_i=args.lufs,
        target_tp=args.tp,
        platform=args.platform,
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["after_overall"] != "FAIL" else 1)


if __name__ == "__main__":
    main()

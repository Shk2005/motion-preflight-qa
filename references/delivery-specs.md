# Broadcast & Social Delivery Specs Reference

## Recommended Export Matrix

| Parameter | Social / Reels / TikTok / Shorts | YouTube / Web Hero | Transparent Overlay (NLE) |
|---|---|---|---|
| **Container** | `.mp4` with `+faststart` | `.mp4` with `+faststart` | `.mov` (ProRes 4444) |
| **Video Codec** | H.264 (`libx264`, High Profile) | H.264 (`libx264`) or HEVC | `prores_ks -profile:v 4` |
| **Pixel Format** | `yuv420p` (mandatory) | `yuv420p` | `yuva444p10le` |
| **Frame Rate** | Constant `30` or `60` fps | Constant `30` or `60` fps | Match timeline (`30` / `60`) |
| **CRF Quality** | `20` (clean UI) / `23` (heavy grain) | `18`–`20` | Visually lossless |
| **Audio Codec** | AAC-LC, 192 kbps, 48 kHz stereo | AAC-LC, 192–256 kbps, 48 kHz | PCM 24-bit 48 kHz |
| **Audio Loudness** | `-14.0 LUFS` (±1.5 LU) | `-14.0 LUFS` (±1.0 LU) | `-14.0 LUFS` |
| **True Peak Ceiling** | `<= -1.0 dBTP` | `<= -1.0 dBTP` | `<= -1.0 dBTP` |

## Top 5 Code-to-Video Failure Modes (and Fixes)

1. **Black screen in QuickTime, Safari, or Instagram iOS**
   - *Cause:* Headless capture encoded `yuv444p` or `rgb24` instead of `yuv420p`.
   - *Fix:* Run `scripts/fix_delivery.py` (enforces `-pix_fmt yuv420p`).
2. **Slow start / buffering spinner on mobile feeds**
   - *Cause:* MP4 `moov` metadata atom sits at the end of the file.
   - *Fix:* `-movflags +faststart` moves `moov` ahead of `mdat`.
3. **Instagram / TikTok crushes or pumps your music & voice**
   - *Cause:* Unmastered mix peaking above `0 dBFS` or sitting at `-24 LUFS`.
   - *Fix:* Two-pass EBU R128 loudness normalization to `-14 LUFS / -1.0 dBTP`.
4. **Blurry typography after uploading a 150 MB 15-second reel**
   - *Cause:* Animated SVG/canvas film grain balloons bitrate, triggering aggressive platform re-encoding.
   - *Fix:* Keep grain subtle (4%–8% opacity) and export with `--crf 23`.
5. **First 0.5 seconds is empty or fading in from solid black**
   - *Cause:* Entrance animation starts from `opacity: 0` at `t = 0`.
   - *Fix:* Always land a high-contrast visual anchor on Frame 0 (`0.00s`); animate movement rather than hiding the opening frame.

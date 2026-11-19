# Platform Safe Zones Reference (2026)

Every vertical social platform overlays interactive UI chrome directly on top of your 1080×1920 canvas. Place **all headlines, numbers, subtitles, product callouts, logos, and CTAs** strictly inside the Safe Title Box.

## 1080×1920 Vertical Safe Coordinates

| Platform | Top Hazard | Bottom Hazard | Left Buffer | Right Hazard | Safe Title Box (`x, y, w × h`) |
|---|---|---|---|---|---|
| **Instagram Reels** | 14% (269 px) | 22% (422 px) | 5% (54 px) | 16% (173 px) | `x: 54`, `y: 269`, **`853 × 1229 px`** |
| **TikTok** | 12% (230 px) | 24% (461 px) | 5% (54 px) | 17% (184 px) | `x: 54`, `y: 230`, **`842 × 1229 px`** |
| **YouTube Shorts** | 12% (230 px) | 20% (384 px) | 5% (54 px) | 15% (162 px) | `x: 54`, `y: 230`, **`864 × 1306 px`** |
| **Universal Cross-Post (Reels + TikTok + Shorts)** | **14% (269 px)** | **24% (461 px)** | **6% (65 px)** | **17% (184 px)** | `x: 65`, `y: 269`, **`831 × 1190 px`** |

## Widescreen & Feed Safe Coordinates

| Platform | Canvas | Safe Title Box | Notes |
|---|---|---|---|
| **YouTube / Landing Hero (16:9)** | 1920×1080 | `1612 × 842 px` (8% top/left/right, 14% bottom) | Bottom 14% protects progress scrubber + auto-captions |
| **LinkedIn Feed (4:5)** | 1080×1350 | `950 × 1026 px` (8% top, 16% bottom, 6% sides) | Bottom protects playback bar on mobile feed |
| **Square Feed (1:1)** | 1080×1080 | `907 × 864 px` (8% top/sides, 12% bottom) | Keeps corner logos and captions uncropped |

## Practical CSS Safe-Area Rules for HTML/GSAP/Remotion

```css
.safe-stage-vertical {
  position: absolute;
  top: 14%;
  bottom: 24%;
  left: 6%;
  right: 17%;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
```

Full-bleed background gradients, textures, and ambient video may extend edge-to-edge (`0%` to `100%`), while all readable copy and interactive cards remain constrained inside `.safe-stage-vertical`.

"""Render the motion study frame by frame (deterministic, no dropped frames) and encode with ffmpeg."""
import math, subprocess, json, pathlib, sys
from playwright.sync_api import sync_playwright

FPS, DUR, W, H = 60, 9.0, 1920, 1080
OUT = pathlib.Path(__file__).parent
FR = OUT / "frames"; FR.mkdir(exist_ok=True)

def smooth(u):  # calm finger-driven scroll with gentle start and settle
    u = max(0, min(1, u)); return u*u*(3-2*u) if u < 1 else 1
def _flick_v(u):  # finger push for the first ~60 ms, then momentum decays
    ramp = min(1, u / 0.09); ramp = ramp*ramp*(3-2*ramp)
    return ramp * (1-u)**3
_N = 2000; _cum = [0.0]
for k in range(_N):
    _cum.append(_cum[-1] + _flick_v((k+0.5)/_N))
def flick(u):
    u = max(0, min(1, u)); return _cum[int(round(u*_N))] / _cum[-1]

# (start_s, end_s, from_screens, to_screens, curve)
PLAN = [(0.0, 0.6, 0, 0, None),
        (0.6, 2.5, 0, 1, smooth),
        (2.5, 3.3, 1, 1, None),
        (3.3, 5.2, 1, 2, smooth),
        (5.2, 6.0, 2, 2, None),
        (6.0, 6.7, 2, 3, flick),
        (6.7, DUR, 3, 3, None)]

def pos(t):
    for a, b, f, to, c in PLAN:
        if a <= t < b or (t >= DUR - 1e-9 and b == DUR):
            return to if c is None else f + (to - f) * c((t - a) / (b - a))
    return PLAN[-1][3]

n = int(FPS * DUR); log = []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--force-color-profile=srgb"])
    pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    pg.goto((OUT / "index.html").as_uri() + "?record")
    pg.wait_for_timeout(500)
    for i in range(n):
        t = i / FPS; y = pos(t) * H
        pg.evaluate("([y,t,dt])=>window.__render(y,t,dt)", [y, t, 1/FPS if i else 0])
        pg.screenshot(path=str(FR / f"f{i:04d}.png"))
        log.append({"i": i, "t": round(t, 4), "y": round(y, 2)})
    br.close()
(OUT / "frames.json").write_text(json.dumps(log))
mp4 = OUT / "water-steel-study-2026-11-22.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(FR / "f%04d.png"),
                "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                "-profile:v", "high", "-movflags", "+faststart", str(mp4)], check=True)
print("wrote", mp4, n, "frames")

# Jev explainer (15s, 16:9)

Premium motion-graphics explainer for "Jev", built procedurally.

- `jev-explainer.mp4` — final film (1920x1080, 60fps, H.264 + AAC, exactly 15.0 s)
- `scene.html` — the animation: a single canvas world, `render(t)` draws any time `t` (9 shots)
- `render.js` — Playwright frame renderer piped into ffmpeg
- `audio.py` — Japanese voiceover (Open JTalk), 132 BPM music and synced SFX

## Rebuild

```sh
# fonts (Noto Sans JP 400/500/700/900, Inter 500/700/800) as TTF in ./fonts
pip install pyopenjtalk-plus scipy numpy
NODE_PATH=$(npm root -g) node render.js video video.mp4 60
python3 audio.py audio.wav
ffmpeg -i video.mp4 -i audio.wav -c:v copy -c:a aac -b:a 256k -shortest jev-explainer.mp4
```

All percentages shown are illustrative fictional examples (説明用の架空例), not measured Jev performance.

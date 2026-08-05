# ピーボンバー バースデーアニメーション 生成ツール

`pea-bomber.html` で配信している約11秒のヒーローアニメーション
(`assets/video/pea-bomber.mp4`) を再生成するためのスクリプトです。

## 構成

| ファイル | 役割 |
| --- | --- |
| `render.py` | 5枚のイラストから270フレーム(24fps / 1080x1920)を描き出す。カメラワーク、集中線、インパクトフレーム、火の粉、擬音・セリフのタイポグラフィを合成する。 |
| `music.py` | オリジナル劇伴「PLUS BOMBER!」(Dマイナー / 160BPM)と効果音を合成し `bgm.wav` を書き出す。カット点 0.0 / 1.5 / 3.0 / 4.5 / 8.25 / 9.75 秒にアクセントを同期。 |

BGMはご指定の楽曲が著作権で保護されているため、同系統の
ヒーローバトル調オリジナル楽曲を書き下ろしています。

## 必要なもの

```
pip install pillow numpy imageio-ffmpeg
```

日本語字幕の描画に IPAGothic (`/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf`)
を使用します。

## 手順

素材イラストを `src/` に以下の名前で配置します。

```
src/01_flight.png     炎の鞭で夜空を飛ぶ登場カット
src/02_bomb.png       黄色い液体を撃ち出して爆弾に着火するカット
src/03_explosion.png  大爆発でヴィランを撃破するカット
src/04_thumbsup.png   サムズアップのアップカット
src/05_leave.png      ジェットで夜空へ飛び去るカット
```

```sh
python3 render.py                      # -> frames/f0000.jpg ... f0269.jpg
python3 music.py                       # -> bgm.wav
ffmpeg -y -framerate 24 -i frames/f%04d.jpg -i bgm.wav \
  -map 0:v -map 1:a -c:v libx264 -preset veryslow -crf 21 \
  -pix_fmt yuv420p -profile:v high -level 4.0 \
  -c:a aac -b:a 192k -shortest -movflags +faststart pea-bomber.mp4
```

## カット割り

| フレーム | 秒 | 内容 |
| --- | --- | --- |
| 0-35 | 0.00-1.50 | 炎の鞭を振るって降下、ヴィランを発見 |
| 36-71 | 1.50-3.00 | 黄色い液体を撃ち込み爆弾に着火 |
| 72-107 | 3.00-4.50 | 大爆発、ヴィラン撃破 |
| 108-197 | 4.50-8.25 | 「俺はピーボンバー！！ よう氷！ ハッピーバースデー！！ これからもよろしくな！」 |
| 198-233 | 8.25-9.75 | むずむず、「やべえ！ もれそう！」 |
| 234-269 | 9.75-11.25 | 夜空へ飛び去る、エンドカード |

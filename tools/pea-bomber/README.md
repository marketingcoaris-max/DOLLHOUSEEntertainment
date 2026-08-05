# ピーボンバー バースデーアニメーション 生成ツール

`pea-bomber.html` で配信している 13.5秒・24fps のヒーローアニメーション
(`assets/video/pea-bomber.mp4`) を再生成するためのスクリプトです。
画面にテキストは一切入れず、セリフはボイスで聞かせる構成になっています。

## 構成

| ファイル | 役割 |
| --- | --- |
| `anim.py` | アニメーション基盤。バイリニアのワープエンジン（キャラクターのパペット的な動きと口パク）、セル調のエフェクト作画（炎・爆発・煙・瓦礫）、カメラワークと「線のボイル」を提供する。 |
| `render2.py` | 324フレーム(24fps / 1080x1920)のカット構成と演出。`voice_timing.json` を読んで口の開閉をボイスに同期させる。 |
| `voice.py` | pyopenjtalk でセリフを合成し、ピッチとテンポを上げて元気な青年の声に加工する。あわせて口パク用の `voice_timing.json` を書き出す。 |
| `music2.py` | オリジナル劇伴「PLUS BOMBER!!（Battle Ver.）」と効果音を合成し `bgm2.wav` を書き出す。 |
| `mixdown.py` | BGMとボイスを混ぜて `final_audio.wav` を作る。セリフの帯域だけBGMを削る処理つき。 |

## 必要なもの

```
pip install pillow numpy pyopenjtalk imageio-ffmpeg
```

`pyopenjtalk` は初回実行時に辞書を自動ダウンロードします。

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
python3 voice.py                       # -> voice.wav, voice_timing.json
python3 music2.py                      # -> bgm2.wav
python3 mixdown.py                     # -> final_audio.wav
python3 render2.py                     # -> frames2/f0000.jpg ... f0323.jpg
ffmpeg -y -framerate 24 -i frames2/f%04d.jpg -i final_audio.wav \
  -map 0:v -map 1:a -c:v libx264 -preset veryslow -crf 21 \
  -pix_fmt yuv420p -profile:v high -level 4.0 \
  -c:a aac -b:a 192k -shortest -movflags +faststart pea-bomber.mp4
```

`voice.py` を先に流すのが前提です。セリフの長さが変わると
`render2.py` のカット割りもずらす必要があります。
特定フレームだけ確認したいときは `python3 render2.py 150 151 152` のように
フレーム番号を渡せます。

## カット割り（160BPM / 1小節1.5秒）

| フレーム | 秒 | 内容 |
| --- | --- | --- |
| 0-35 | 0.0-1.5 | ホイップパンで登場、炎の鞭を振るう |
| 36-71 | 1.5-3.0 | 黄色い液体を撃ち込み爆弾に着火（2回の誘爆） |
| 72-107 | 3.0-4.5 | 大爆発。2コマのインパクトフレームから爆炎・瓦礫・衝撃波 |
| 108-143 | 4.5-6.0 | 「俺はピーボンバー！」 |
| 144-169 | 6.0-7.1 | 「よう氷！」 |
| 170-203 | 7.1-8.5 | 「ハッピーバースデー！」 |
| 204-246 | 8.5-10.3 | 「これからもよろしくな！」 |
| 247-287 | 10.3-12.0 | むずむず、「やべえ！ もれそう！」 |
| 288-323 | 12.0-13.5 | ジェットで夜空へ飛び去る |

## 注意

- BGMはご指定の楽曲が著作権で保護されているため、同系統の少年バトル調
  オリジナル楽曲を書き下ろしています。
- 「氷」は `こおり` と読ませています。別の読みにする場合は `voice.py` の
  セリフを読み仮名（例：`ヒョウ`）に書き換えてください。

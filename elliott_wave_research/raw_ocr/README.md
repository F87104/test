# OCR 一次テキスト

[F87104/sai](https://github.com/F87104/sai) リポジトリにアップロードされた PDF を、Tesseract OCR（`-l jpn`）でテキスト化したもの。1 行目あたりの位置情報はなく、`===== Page NN =====` のヘッダで各ページの開始を区切っている。

## ファイル

| ファイル | 元 PDF | ページ数 |
| --- | --- | --- |
| `elliott_all.txt` | `エリオット波動.pdf` | 50 |
| `ch1_all.txt` | `1章.pdf` | 30 |
| `method_all.txt` | `手法.pdf` | 23 |
| `dow_all.txt` | `ダウ理論.pdf` | 24 |

## OCR の精度について

- 漢字熟語は概ね読めているが、固有名詞や数値で誤認識が散見される。
  - 例: 「78.6」が「78.9」、「環境認識」が「境認謗」、「分析」が「分折」、「割」が「圧」等
- 図の中の文字や図番号、図そのものの形は取れていない（パターン形状は元 PDF を参照）
- 最終的な引用や数値検証は **必ず元 PDF を当たること**

## 再生成手順

```bash
# 1. Poppler と Tesseract 日本語版を入れる
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-jpn

# 2. PDF をダウンロード（例: エリオット波動.pdf）
curl -sL -o elliott.pdf \
  "https://raw.githubusercontent.com/F87104/sai/main/%E3%82%A8%E3%83%AA%E3%82%AA%E3%83%83%E3%83%88%E6%B3%A2%E5%8B%95.pdf"

# 3. ページ画像化
mkdir pages
pdftoppm -r 200 elliott.pdf pages/p -png

# 4. OCR
for f in pages/p-*.png; do
  tesseract "$f" "${f%.png}" -l jpn
done

# 5. 連結
for i in $(ls pages/p-*.txt | sort); do
  page="${i##*/p-}"; page="${page%.txt}"
  echo "===== Page $page ====="
  cat "$i"
done > elliott_all.txt
```

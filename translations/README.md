# Translations Tools README

`translations` 配下の翻訳ツール運用ガイドです。

## 概要

このディレクトリの主目的は、以下の翻訳ワークフローを実行することです。

1. addon コードから翻訳キーを抽出 (`extract-pot`)
2. 各言語の `.po` にキーをマージ (`merge-po`)
3. AI 翻訳用キャッシュ準備 (`ai-prepare`)
4. AI で `.po` を更新 (`ai-translate`)
5. 実行時用 Python 辞書へコンパイル (`compile-dict`)

通常は `localize_pipeline.ps1` を実行すれば一連の処理が終わります。

---

## 前提

- Python 3.10+?（推奨）
- 実行位置: 基本は `translations` ディレクトリ
- 依存パッケージ: `translations/requirements.txt`
- AI 機能を使う場合は `.env` が必要（`.env.sample` を元に作成）

セットアップ例:

```powershell
Set-Location ".\translations"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.sample .env
```

`.env` 記載例:

```dotenv
GEMINI_API_KEY="your-gemini-api-key"
GEMINI_CACHE_ID=""
```
- Gemini AI Studio にて API キーを発行し、`GEMINI_API_KEY` にセットしてください。AI利用すると従量課金が発生します。
- GEMINI_CACHE_ID は空のままでいいす。本ツールを実行中に自動更新されます。

---

## 実行方法

`translations` 直下で実行:

```powershell
.\localize_pipeline.ps1
```

AI ステップだけ dry-run したい場合:

```powershell
.\localize_pipeline.ps1 --ai-dry-run
```

---

## ヘルプ表示

全体ヘルプ:

```powershell
python -m translator --help
```

各コマンドヘルプ:

```powershell
python -m translator extract-pot --help
python -m translator merge-po --help
python -m translator ai-prepare --help
python -m translator ai-translate --help
python -m translator compile-dict --help
```

---

## 個別コマンドの実行例

### extract-pot

addon ソースから `messages.pot` を生成します。

```powershell
python -m translator extract-pot -d "../CM3D2 Converter" -o "./locale/messages.pot"
```

### merge-po

`messages.pot` を既存 `*.po` に反映します。

```powershell
python -m translator merge-po -s "./locale/messages.pot" -t "./locale/en_US.po"
```

### ai-prepare

AI 翻訳前にコンテクストキャッシュを準備します。  

```powershell
python -m translator ai-prepare -d "../CM3D2 Converter"
```

dry-run:

```powershell
python -m translator ai-prepare -d "../CM3D2 Converter" --dry-run
```

### ai-translate

指定 PO を AI で翻訳更新します。

```powershell
python -m translator ai-translate -p "./locale/en_US.po"
```

dry-run:

```powershell
python -m translator ai-translate -p "./locale/en_US.po" --dry-run
```

API 呼び出し回数を制限して試験実行:

```powershell
python -m translator ai-translate -p "./locale/en_US.po" --max-api-calls 1
```

### compile-dict

`locale` 内 PO を実行時 Python 辞書にコンパイルします。

```powershell
python -m translator compile-dict -l "./locale" -o "../CM3D2 Converter/translations/locales.py"
```

---

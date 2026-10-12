# Blender-CM3D2-Converter

3Dアダルトゲーム「[カスタムメイド3D2](http://kisskiss.tv/cm3d2/)」「[カスタムオーダーメイド3D2](http://com3d2.jp/)」で使用されるモデルファイル形式(.model)を  
フリー3D統合環境である「[Blender](https://www.blender.org/)」で扱うためのアドオンです。  
ある程度Blenderの基本操作をできる人を対象にしています。  
初めての人は[Blenderのチュートリアル](https://www.google.co.jp/search?q=Blender+%E3%83%81%E3%83%A5%E3%83%BC%E3%83%88%E3%83%AA%E3%82%A2%E3%83%AB)などから始めましょう。  

**注意点**
* 本フォークのモジュールはBlender-3.3以下では動作しません。
* 推奨Blenderバージョンは5.2です。
* 機能のうちいくつかはBlenderバージョン制約により使用できない場合があります。
* Blender-2.7x上で旧Blender-CM3D2-Converterを用いて取り込み・作成したデータをそのまま新しいBlenderバージョンで開いても正常に移行されません。  

**変更点ダイジェスト**

https://github.com/user-attachments/assets/f36620f8-447e-470b-8334-394dc85ae7b4

## 目次
* [インストール](#インストール)
  * [Blender4.2以降](#blender42以降)
  * [Blender4.2以前](#blender42以前)
* [規約](#規約)
* [ライセンス](#ライセンス)
  * [Third-party Licenses](#third-party-licenses)

## インストール

Blender4.2以降で利用可能な`Extensions`としてインストールすることを推奨します。
また、`Extensions`での更新管理に移行したため、オリジナルの自動更新機能は廃止しました。  
4.2以下でもアドオンとしてインストール可能ですが、その場合はReleaseページでの添付パッケージは2種類あり、`*-addon.zip`のほうをダウンロードしてください。

### Blender4.2以降

![how-to-install-extension](/docs/img/how-to-install-extension.png)

- **初回インストール方法**
  - Blenderを起動し「プリファレンス」→「エクステンション」に移動
  - 「リポジトリ」→「＋」→「リモートリポジトリを追加」を選択
  - 「URL」に下記を転記して「作成」を押下
    ```text
    https://mmt3d.github.io/blender-extensions/index.json
    ```
  - 検索フォームに`cm`などと入力すれば`CM3D2 Converter`が見つかるので「インストール」を押下
- **更新方法**
  - このエクステンションパネルで最新版アップデートの確認と更新ができます

### Blender4.2以前

![how-to-install-addon](/docs/img/how-to-install-addon.png)

- **インストール方法**
  - [Release](https://github.com/mmt3d/Blender-CM3D2-Converter/releases/latest)より最新のcm3d2_converter-*-addon.zip をダウンロード
  - Blenderを起動し「プリファレンス」→「アドオン」に移動
  - 「インストール」または 「v」→「ディスクからインストール」を選択
  - ダウンロードしたファイルを指定して「インストール」
- **更新方法**
  - 「ヘルプ」→ 「最新版チェック」で最新版があるか確認
  - 上記インストール操作をしてください

### Everything 連携 (高速テクスチャ検索用)

大量のファイルがあるフォルダ(`C:\KISS\COM3D2\MOD`など)をテクスチャ探索パスに指定しているとモデルインポート時などにテクスチャ探索遅延によりインポート処理時間が異常にかかる場合があります。  
高速ファイル検索ソフト`Everything`がインストールされている場合、これと連携することで常に高速化された検索が可能になります。  
また、制作時などテクスチャファイルを追加する場合、従来必要だったテクスチャキャッシュ再構成の必要もなくなります。

**導入方法**

1. `Everything(64bit版)`をインストールし起動してください。(※1.4.1で動作確認済み)
  - 公式: https://www.voidtools.com/
  - 窓の社: https://forest.watch.impress.co.jp/library/software/everything/
2. Everything本体設定では、テクスチャ探索パスを含むドライブのインデックスを作成するなどしておいてください。
3. 「プリファレンス」→「アドオン」→「CM3D2 Converter」→「texファイル検索」→「Everythingと連携する」を有効にしてください。  
  ![everything-settings](/docs/img/everything-settings.png)

## 規約

[公式のMOD規約](http://kisskiss.tv/kiss/diary.php?no=558)を厳守して下さい。


## ライセンス

- 本ソフトウェアは`Apache License 2.0`です。
- また、下記に含まれる外部モジュールやSDKを同梱しています。

### Third-party Licenses

This addon bundles the following third-party libraries and components:

**1. Python Libraries (MIT License)**
- pythonnet
- cffi
- clr_loader
- pycparser
- py_dds (https://github.com/robertkist/py_dds) not PyPI package

These libraries are redistributed under the terms of the **MIT License**.  
To ensure stable operation inside Blender’s embedded Python environment—where `pip install` is not always available or reliable—the addon includes pre-built wheels and Python modules directly.  

**2. Everything SDK / DLL (voidtools)**
- Everything SDK components (for high-speed file search)

Everything and the Everything SDK are provided free for personal and commercial use by voidtools.

The full license texts and copyright notices for all of these third-party components are provided in:  
`THIRD_PARTY_LICENSES` 

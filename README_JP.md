# barcodekit

[English](README.md)

`barcodekit` は、ローカルの
[`barcode-rest`](https://github.com/Moge800/barcode-rest) をワンショットCLIモードで
呼び出し、PythonからバーコードPNG画像を生成するライブラリです。

上流実行ファイルの名前に `rest` と付いていますが、**barcodekitはRESTサーバーを
起動せず、HTTPも使用しません**。各生成処理で実行するのは、次のコマンドだけです。

```text
barcode-rest generate <symbology> --text <text> --output -
```

標準出力からPNGバイト列を読み取り、そのままPythonへ返します。

## クイックスタート

環境に合ったplatform wheelをインストールしてから使用します。

```python
from barcodekit import code128, datamatrix, qr

datamatrix("ABC123", size=256).save("dm.png")
qr("https://example.com", size=512, level="Q").save("qr.png")
code128("ABC-123456", label=True).save("c128.png")
```

明示的にエンジンオブジェクトを作成しても、同じメソッドを利用できます。

```python
from barcodekit import BarcodeKit

kit = BarcodeKit(timeout=10)
image = kit.datamatrix("ABC123", size=256)

raw_png = image.to_bytes()
image.save("dm.png")
```

`datamatrix`、`qr`、`aztec` では、`size` と `module` を同時に指定できません。
モジュールサイズを直接指定する場合は、`size=None` を設定してください。

```python
datamatrix("ABC123", size=None, module=8)
```

## 実行ファイルの解決順序

`barcodekit` は画像生成時に、次の順序で実行ファイルを探します。

1. `BarcodeKit(executable=...)` に渡されたファイルパス
2. 環境変数 `BARCODEKIT_BINARY` のファイルパス
3. インストール済みplatform wheelに同梱された実行ファイル

wheelをビルドしなくても、開発用バイナリを明示的に指定できます。

```python
kit = BarcodeKit(executable=r"C:\tools\barcode-rest.exe")
kit.datamatrix("ABC123").save("dm.png")
```

環境変数でも指定できます。

```powershell
$env:BARCODEKIT_BINARY = "C:\tools\barcode-rest.exe"
uv run python example.py
```

```bash
BARCODEKIT_BINARY=/opt/barcode-rest uv run python example.py
```

指定する値はファイルパスである必要があります。barcodekitは `PATH` を検索しません。

## バイナリ同梱wheel

各リリースwheelには、対象環境に合う `barcode-rest` 実行ファイルを1つだけ同梱する
想定です。異なるOSやCPUアーキテクチャ向けの実行ファイルを、1つのwheelへまとめて
同梱することはありません。

同梱バイナリの対応環境：

- Windows amd64
- glibc 2.34以降を使用するLinux amd64（Ubuntu 22.04以降を含む）
- glibcを使用するLinux arm64（64bit Ubuntuおよび64bit Raspberry Pi OSを含む）

非対応環境：

- macOS
- Windows arm64
- 32bit Linuxおよび32bit Raspberry Pi OS
- Alpine LinuxなどのmuslベースのLinuxディストリビューション

バイナリを含まないsource distributionは、リリース対象にしません。上記の対応OSと
CPUアーキテクチャでは、ソースcheckoutでも `BARCODEKIT_BINARY` または
`BarcodeKit(executable=...)` を指定して開発できます。

リリースビルドでは現在、
[`barcode-rest` v0.2.0](https://github.com/Moge800/barcode-rest/releases/tag/v0.2.0)
を固定して使用します。期待するSHA-256は `checksums/v0.2.0.sha256` にcommitします。

## 対応シンボル

2次元コード：

- Data Matrix（`datamatrix`）
- QR Code（`qr`）
- Aztec（`aztec`）
- PDF417（`pdf417`）

1次元バーコード：

- Code 128（`code128`）
- Code 39（`code39`）
- Code 93（`code93`）
- Codabar（`codabar`）
- Interleaved 2 of 5（`itf`）
- Standard 2 of 5（`code25`）
- EAN-13 / JAN（`ean13`）
- EAN-8（`ean8`）

`barcodekit` は実行ファイルを起動する前に、対応オプション、数値範囲、テキスト長、
基本文字種、チェックディジットを検証します。生成するシンボルによって決まる
エンコード制約は、`barcode-rest` が検証します。

## セキュリティとプライバシー

- 実行時に実行ファイルやその他のデータをダウンロードしません。
- サーバーを起動しません。
- REST APIおよびHTTPを使用しません。
- wrapperから外部ネットワークへ接続しません。
- バーコード本文は、ローカルの `barcode-rest` 実行ファイルだけに渡します。
- wrapperはバーコード本文をログへ出力しません。
- wrapperの例外にコマンドを表示する場合、`--text` の次の値を `<redacted>` に
  置き換えます。標準エラー出力に含まれる一致テキストも同様に置き換えます。

上流CLIのインターフェース上、バーコード本文はローカルプロセスのコマンドライン
引数として渡す必要があります。そのため、ローカルプロセスの引数を閲覧できる権限を
持つユーザーやツールから、一時的に本文が見える可能性があります。

## uvを使用した開発

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src/barcodekit
uv build
```

単体テストでは `subprocess.run` をmockするため、Go実行ファイルは不要です。
`BARCODEKIT_BINARY` が設定されている場合、任意の統合テストで実際のData Matrix画像を
生成し、PNG出力を確認します。

## ライセンス

`barcodekit` はMIT Licenseです。platform wheelには
[THIRD_PARTY_NOTICES.md](https://github.com/Moge800/barcodekit/blob/v0.1.1/THIRD_PARTY_NOTICES.md)
に記載した通知とライセンス文も同梱します。

# barcodekitのリリース

[English](RELEASING.md)

この文書はpackage保守者向けです。インストール方法、対応platform、APIの使用方法は
`README_JP.md` に記載します。

## 前提条件

- 開発・ビルド環境には `uv` を使用します。
- 上流 `barcode-rest` のバージョンを `.github/workflows/release.yml` で固定します。
- 信頼するrelease assetのSHA-256を
  `checksums/<barcode-rest-version>.sha256` にcommitします。
- 初回リリース前に、GitHubの `pypi` environmentとPyPI Trusted Publisherを
  設定します。

実際の実行ファイルはこのリポジトリへcommitしません。リリースjobが、固定した
上流 `barcode-rest` のGitHub Releaseからassetをダウンロードします。

## ローカル検証

リリースを作成する前に、ローカルで一式を実行します。

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src/barcodekit
uv build
```

## platform wheelの準備

ローカルでwheelを確認する場合は、ビルド前に信頼できるバイナリを1つだけpackageへ
コピーします。

```bash
uv run python scripts/prepare_binary.py \
  --binary ./dist/barcode-rest.exe \
  --target windows-amd64 \
  --sha256 <trusted-sha256> \
  --expected-version <pinned-version>

uv run python scripts/prepare_binary.py \
  --binary ./dist/barcode-rest-linux-amd64 \
  --target linux-amd64 \
  --sha256 <trusted-sha256> \
  --expected-version <pinned-version>

uv run python scripts/prepare_binary.py \
  --binary ./dist/barcode-rest-linux-arm64 \
  --target linux-arm64 \
  --sha256 <trusted-sha256> \
  --expected-version <pinned-version>
```

このスクリプトはchecksumまたはバージョンの不一致を拒否し、ネイティブ環境で
ワンショットPNG生成のスモークテストを実行します。また、別のOS向けに残っている
実行ファイルを削除し、対象platformに必要なファイル名とLinux実行権限を設定します。

リリースビルドは対象アーキテクチャ上で実行し、wheelを採用する前に以下をすべて
検証します。

1. バイナリのSHA-256がcommit済みの値と一致すること
2. `barcode-rest -version` が固定したreleaseを返すこと
3. ワンショットData Matrixコマンドが有効なPNGを返すこと
4. wheelに対象の実行ファイルが1つだけ含まれること
5. wheelに正しいplatform tagが付いていること
6. wheelに `py.typed` と必要なライセンス通知が含まれること

バイナリを挿入した後、Hatchlingが最初に生成する `py3-none-any` wheelをそのまま
uploadしてはいけません。リリースjobでplatform tagを適用し、検証してから使用します。
source distributionは公開しません。

## CIの動作

`.github/workflows/release.yml` は、GitHub-hosted runner上で次のwheelをビルドします。

- `win_amd64`
- `manylinux_2_34_x86_64`
- `manylinux_2_17_aarch64`

リリース関連ファイルを変更するpull requestでは、公開せず3種類すべてをビルドして
検証します。手動の `workflow_dispatch` も、確認用artifactの生成だけを行います。

## 公開手順

1. 公開するすべての変更がdefault branchへcommit済みであることを確認します。
2. default branchの現在HEADへ `v<major>.<minor>.<patch>` tagを作成します。
3. 対応するGitHub Releaseを公開します。
4. PyPIへの公開とGitHub Releaseへのwheel添付が成功したことを確認します。

tagをpushするだけではpackageを公開しません。

GitHub Releaseが公開されると、workflowは次の処理を行います。

1. release tagをcheckout
2. tag commitがdefault branchの現在HEADと完全に一致することを確認
3. `pyproject.toml`、`src/barcodekit/_version.py`、`uv.lock`、
   バージョン固定された通知リンクを同期
4. metadataだけの更新をfast-forwardとしてdefault branchへcommit
5. 同じ同期済みcommitから3種類すべてのwheelをビルド
6. PyPI Trusted Publishingで公開
7. PyPIへの公開成功後、wheelをGitHub Releaseへ添付

tagとdefault branchのHEADが異なる場合、workflowは何もビルドせず停止します。
Releaseを公開する前に、現在のdefault branch HEADへtagを移動または作り直してください。
default branchを直接ビルドしてこの検証を回避してはいけません。release tagに含まれない
コードを公開する原因になります。

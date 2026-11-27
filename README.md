# PhaseEQ

リリースバージョン: **v2.0.11**

文書更新日: **2026-11-27**

PhaseEQはスピーカーの測定応答から、目標特性、IIR／FIR補正、帯域分割を設計するアプリです。マルチウェイ画面では各チャンネルを合成し、位相・時間整合を調整して実機DSP用の係数を出力できます。

音楽再生機能はありません。係数の利用には外部ソフトウェア／DSPが必要です。[概要・仕様](docs/distribution/user-guide.md#overview-specifications)、[設計値の選び方](docs/distribution/user-guide.md#design-parameters)、[利用条件](docs/distribution/user-guide.md#usage-terms)を確認してください。出力形式への対応と実機動作確認は区別しています。

## FreeとPro

**PhaseEQ Free／Proの初版は v2.0.0 です。** Freeは [PhaseEQ-Free](https://github.com/tomii323/PhaseEQ-Free/releases) で公開しています。分離前の旧版は v1.21.13 で更新を終了し、[PhaseEQ-publicの旧版履歴](https://github.com/tomii323/PhaseEQ-public/releases)に残しています。

FreeとProは、IIR自動EQ、手動FIR EQ、通常のFIR設計・書き出し、出力Auto Gainを共通で利用できます。**Pro専用：FIR Gain／Phase自動EQ、Waveletグラフ、Reverse Null・クロス付近のディップ・位相／時間整合の詳細評価、Multiwayの2Way+SUB／3Way／4Way（SUB付き含む）、Multiwayの実機向けDSPパッケージ。** FreeのMultiwayはMono／StereoのFullrange、Fullrange+SUB、2Wayに対応します。

保存済みデータの引き継ぎと更新は[インストールガイド](docs/distribution/installation.md#edition-migration)を参照してください。同梱PDFには分離前の画面例があるため、版による操作の違いは[操作ガイド](docs/distribution/user-guide.md#fir-auto-eq-editions)で確認してください。

## 起動する

- macOS／Linux: `./run_PhaseEQ_mac_linux.sh`
- Windows: `run_PhaseEQ_windows.bat`

ランチャーがPhaseEQとマルチウェイを起動します。通常の起動では、依存関係が揃っていればネット接続は不要です。初回導入や更新は[インストールガイド](docs/distribution/installation.md)を参照してください。

Windows 11 ARMでは、x64エミュレーション上のx64 Pythonを使用します。検証対象はPython 3.12／3.13です。

## 設計を進める

1. 「スピーカー測定データ」で測定を登録し、「応答処理」で補正入力を準備します。
2. 「目標特性」を選び、「IIRイコライザー」「FIRイコライザー」で補正します。
3. 必要に応じて「出力帯域分割ページ」を設定します。
4. 「書き出し」でFIR ON／OFFとタップ数、FIR・IIRの合成応答を確認し、係数を保存します。

マルチウェイでは、先に構成と帯域分割を設定してPhaseEQへ送信します。PhaseEQでチャンネルごとに補正し、「マルチウェイへ送信」で返した後、合成応答を確認します。接続中のFIR条件や帯域分割はマルチウェイ側で管理します。

FIR OFFでもIIRによる設計を続けられます。FIRイコライザーの設定は保持されますが、操作できません。FIRとIIRは別のDSP段として出力されるため、両方を使う場合は実機にも両方を設定してください。

## 日本語マニュアルとドキュメント

| 文書 | 内容 |
|---|---|
| [画像付き操作マニュアル（PDF）](docs/distribution/manual/PhaseEQ_v2.0.0_画像付き操作マニュアル_日本語.pdf) | 操作手順・図解と撮影版を明記した画面例を収録（v2.0.10・改訂57） |
| [マルチウェイ簡易操作マニュアル（PDF）](docs/distribution/manual/PhaseEQ_Multiway_QuickGuide_15p_Dark_JA.pdf) | ダーク画面で設計・補正・合成確認・DSP出力を案内（15ページ） |
| [操作ガイド](docs/distribution/user-guide.md) | 現在の画面名、操作順、設定条件、グラフの読み方 |
| [出力ファイル仕様](docs/distribution/output-format.md) | FIR／IIR係数、作業保存、DSP用パッケージ |
| [インストールガイド](docs/distribution/installation.md) | 導入・更新・起動 |
| [更新履歴](docs/distribution/history.md) | v2.0.0からのFree／Proの履歴と旧版の参照先 |
| [マルチウェイ構成からマイク測定する](docs/distribution/multiway-microphone-measurement.md) | 基準ツイーターから各ウェイ・左右へ進む測定、保存、割り当てと復旧 |
| [v2.0.11 更新案内](docs/distribution/release-notes-v2.0.11.md) | 構成に沿ったマイク測定、左右別時間基準と実機未確認事項 |
| [v2.0.5 更新案内](docs/distribution/release-notes-v2.0.5.md) | C-DSP 8x12（192 kHz）のマルチウェイ専用出力 |
| [v2.0.2 更新案内](docs/distribution/release-notes-v2.0.2.md) | REW IIR／CamillaDSP対応とマルチウェイ出力修正 |
| [v2.0.1 更新案内](docs/distribution/release-notes-v2.0.1.md) | REW PEQテキストの読み込み・出力 |
| [v2.0.0 初版案内](docs/distribution/release-notes-v2.0.0.md) | Free／Proの機能差と旧版からの移行 |

リリースZIPには画像付きPDFと利用者向け文書を同梱します。テストプログラム・開発補助スクリプト・開発文書は含みません。[一般公開リポジトリ](https://github.com/tomii323/PhaseEQ-Free)から実行用ソースを取得できます。開発資産は非公開リポジトリで管理しています。

## 実行時データ

個人設定、DB、測定一時ファイル、生成物、キャッシュは`data/`以下へ保存され、通常はGitや
配布ソースへ含めません。主な対象は`data/settings.json`、`data/databases/`、`data/cache/`、
`data/snapshots/`、`data/presets/`、`data/tmp/`です。

## 主な依存関係

Streamlit、NumPy、pandas、SciPy、Altair、Matplotlib、Plotly、SoundFile、pdfplumberを使用します。

## 利用条件

Copyright (c) Tomii323. 公開Free版は個人利用向けの無償フリーウェアです。MIT／GPL等のオープンソースライセンスではありません。正式条件は[LICENSE.md](LICENSE.md)を参照してください。

- 本体の商用・業務利用は禁止します。個人的な調査・検証・デバッグ目的の改変は許可します。
- GitHub上の閲覧・Fork・Pull Requestと、それに必要な変更共有は許可します。この例外を除き、改変版・派生版の公開・提供・再配布は禁止し、オリジナル版の再配布には権利者の事前承諾が必要です。本体の販売・有償配布・再許諾・第三者製品への組み込み配布は禁止します。
- 個人利用で生成したFIR、WAV、BIN、TXT、CSV、FRD、測定結果、設定データ等は、その後の商用・業務用機器への組み込み・利用・配布を含め自由に利用できます。ただし、商用・業務目的で本体を使用して新たに生成・調整することは禁止します。
- 第三者ライブラリには各固有のライセンスを適用します。著作権・ライセンス表示の削除・変更は禁止します。本体と生成物は無保証で、法令が許す範囲で権利者は免責されます。

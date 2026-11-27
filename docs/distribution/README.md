# 利用者向けドキュメント

文書一覧更新日: **2026-11-27**／対象公開版: **PhaseEQ v2.0.10**

**Pro専用：FIR Gain／Phase自動EQ、Waveletグラフ、Reverse Null・クロス付近のディップ・位相／時間整合の詳細評価、Multiwayの2Way+SUB／3Way／4Way（SUB付き含む）、Multiwayの実機向けDSPパッケージ。** FreeのMultiwayはMono／StereoのFullrange、Fullrange+SUB、2Wayに対応します。 IIR自動EQ、手動FIR EQ、FIR書き出し、出力時のAuto GainはFreeでも使えます。

| やりたいこと | 読む文書 |
|---|---|
| 本アプリの役割と対応範囲を確認する | [概要・仕様](user-guide.md#overview-specifications) |
| FIR／IIR・タップ数などを選ぶ | [設計パラメーターの決め方](user-guide.md#design-parameters) |
| 操作手順と画面例・図解を確認する | [画像付き操作マニュアル（PDF）](manual/PhaseEQ_v2.0.0_画像付き操作マニュアル_日本語.pdf) |
| マルチウェイの操作を短く確認する | [簡易操作マニュアル・ダークUI版（15ページPDF）](manual/PhaseEQ_Multiway_QuickGuide_15p_Dark_JA.pdf) |
| インストール・更新・起動する | [インストールガイド](installation.md) |
| 画面を見ながら測定・補正・マルチウェイ設計を進める | [日本語操作ガイド](user-guide.md) |
| チャンネル間でEQ設定を共有する | [Stereo Link](stereo-link.md) |
| 主目標と別に試聴位置の振幅差分を扱う | [室内音響補正（ルームEQ）](room-eq.md) |
| 保存物とDSPへ渡すファイルを選ぶ | [出力ファイル仕様](output-format.md) |
| 書き出し後の確認をする | [出力データの確認と外部機器での利用](user-guide.md#external-use) |
| 利用条件と権利表記の確認先を知る | [正式条件：LICENSE.md](../../LICENSE.md)／[要点：利用条件・著作権](user-guide.md#usage-terms) |
| バージョンごとの変更を確認する | [更新履歴](history.md)／[v2.0.10 更新案内](release-notes-v2.0.10.md) |

操作ガイドは現在の使い方、更新履歴は過去の変更を説明します。設計中の設定を戻すアプリの「履歴」機能は、操作ガイドの「設計設定の履歴」を参照してください。

公開Free版は個人利用向けの無償フリーウェアで、本体の商用・業務利用は禁止です。個人利用で生成した成果物は、その後の商用利用・配布も可能ですが、商用・業務目的で本体を使って新たに生成・調整することは禁止です。正式条件は[LICENSE.md](../../LICENSE.md)を参照してください。

PDFの対応版は表紙に記載しています。配布ZIPにはテスト・開発補助スクリプト・開発文書を含めません。実行用ソースは[一般公開リポジトリ](https://github.com/tomii323/PhaseEQ-Free)で提供します。

年末例会の測定・再生手順は[配布資料（3ページPDF）](manual/PhaseEQ_YearEndDemo_Handout_JA.pdf)を参照してください。UMIK-2・REW、マイク位置、補正生成と再測定、当日の復旧手順をまとめています。

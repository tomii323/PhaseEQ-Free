# PhaseEQ Free／Proの更新履歴

PhaseEQ Free／Proの初版は **v2.0.0** です。現在の操作は[操作ガイド](user-guide.md)を参照してください。

## 現在の仕様へ移るときの主な違い

- 単独編集とマルチウェイの新規プロジェクトは独立した編集状態です。旧チャンネルのEQや入力を新規プロジェクトへ混ぜません。
- 標準目標特性は2件、自動IIRはターゲット追従式です。過去の版で選べた方式やプリセットと区別してください。
- 位相整合と帯域分割の音響ターゲット設定は独立しています。LR2自動極性は帯域分割側、手動極性は直接設定です。
- FIR OFFでもIIRの設計・出力ができます。FIRとIIRは別の係数として出力します。

## バージョン別の案内

- [v2.0.8：室内音響補正の名称とREW手順](release-notes-v2.0.8.md)。補正カーブの生成・適用・再測定、日英ヘルプと更新マニュアルを案内します。

- [v2.0.7：フォントキャッシュの共通化](release-notes-v2.0.7.md)。起動時の再利用、保存先、初回生成時の通知と対処を案内します。

- [v2.0.6：ルームEQ差分の別管理](release-notes-v2.0.6.md)。振幅差分の加算／減算、ON/OFF、独立保存、測定手順を案内します。

- [v2.0.5：C-DSP 8x12の192 kHz専用出力](release-notes-v2.0.5.md)。マルチウェイのPEQ／Xover分離、段数制限、オフライン検証結果を案内します。
- [v2.0.4：miniDSP出力の独立モジュール化](release-notes-v2.0.4.md)。既存形式の維持とDevice Consoleのオフライン検証結果、読み込み時の制限を案内します。
- [v2.0.3：CamillaDSP係数形式の読み込み](release-notes-v2.0.3.md)。DiffEq／Free係数の保持、保存復元と再出力を案内します。
- [v2.0.2：REW IIR／CamillaDSP対応](release-notes-v2.0.2.md)。対応フィルターの拡張、結果CSV、マルチウェイ出力の修正を案内します。
- [v2.0.1：REW PEQテキストの読み込み・出力](release-notes-v2.0.1.md)。既存IIRを保持する追加操作を案内します。
- [v2.0.0：Free／Proの初版](release-notes-v2.0.0.md)。両版の機能差とマルチウェイの作業保存・復元を案内します。

実装上の変更は [CHANGELOG](../../CHANGELOG.md) を参照してください。

## 分離前の旧版

v1.21.13までのリリースと旧操作ガイドの更新記録は、凍結済みのPhaseEQ-publicに残しています。

- [旧版のリリース一覧](https://github.com/tomii323/PhaseEQ-public/releases)
- [旧版の更新履歴と操作ガイドの記録](https://github.com/tomii323/PhaseEQ-public/blob/v1.21.13/docs/distribution/history.md)

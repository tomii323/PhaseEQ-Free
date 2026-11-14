# PhaseEQ Free／Proの更新履歴

PhaseEQ Free／Proの初版は **v2.0.0** です。現在の操作は[操作ガイド](user-guide.md)を参照してください。

## 現在の仕様へ移るときの主な違い

- 単独編集とマルチウェイの新規プロジェクトは独立した編集状態です。旧チャンネルのEQや入力を新規プロジェクトへ混ぜません。
- 標準目標特性は2件、自動IIRはターゲット追従式です。過去の版で選べた方式やプリセットと区別してください。
- 位相整合と帯域分割の音響ターゲット設定は独立しています。LR2自動極性は帯域分割側、手動極性は直接設定です。
- FIR OFFでもIIRの設計・出力ができます。FIRとIIRは別の係数として出力します。

## バージョン別の案内

- [v2.0.0：Free／Proの初版](release-notes-v2.0.0.md)。両版の機能差とマルチウェイの作業保存・復元を案内します。

実装上の変更は [CHANGELOG](../../CHANGELOG.md) を参照してください。

## 分離前の旧版

v1.21.13までのリリースと旧操作ガイドの更新記録は、凍結済みのPhaseEQ-publicに残しています。

- [旧版のリリース一覧](https://github.com/tomii323/PhaseEQ-public/releases)
- [旧版の更新履歴と操作ガイドの記録](https://github.com/tomii323/PhaseEQ-public/blob/v1.21.13/docs/distribution/history.md)

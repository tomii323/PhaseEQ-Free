# 更新履歴

PhaseEQ Free／Proの変更を、初版の v2.0.0 から記録します。分離前の履歴は [PhaseEQ-publicのCHANGELOG](https://github.com/tomii323/PhaseEQ-public/blob/v1.21.13/CHANGELOG.md) に v1.21.13 まで保存されています。

## 未リリース

## v2.0.4 - 2026-11-20

- miniDSP向けのStandalone、DSP System、Canonical Multiwayのファイル生成を独立モジュールへ分離する。既存の係数、段順、ファイル名と形式を維持し、C-DSP専用経路の互換importも保持する。
- 2x4 HDの48／96 kHz、PEQの10段制限と未使用段の保持をヘルプ・利用文書へ追記する。Device Console 1.2.5の両オフラインテンプレートで計6ファイル・230係数を照合した。実機への送信・音声処理は未確認である。

## v2.0.3 - 2026-11-20

- CamillaDSPのDiffEq／Biquad Free係数形式の読み込みに対応する。2次以下の係数段とFsを保持し、既存IIR一覧から保存復元・ON／OFF・再出力を行う。
- 係数の検証・正規化を独立モジュールへ分離し、Fs不一致、不正数値、不安定な極を拒否する。REW TXTの除外項目と理由を結果CSVへ記録する。

## v2.0.2 - 2026-11-20

- REW Generic TXTをShelf・HP／LP・2次All Passへ拡張し、高次HP／LPの段展開、対応項目だけの出力、全項目の結果CSVを追加する。
- REWのCamillaDSP用パラメータYAMLの読み込みに対応し、通常／極性反転付き1次APの表示を明確化する。
- CamillaDSP入出力を独立モジュールへ分離する。マルチウェイの音声形式名、Mute・未接続、チャンネル数、小数サンプルDelay、名前衝突と不正入力の検証を修正する。

## v2.0.1 - 2026-11-19

- REW Generic形式のPEQテキスト読み込みと、REW形式の`.txt`出力を追加する。既存IIRを保持してManual PEQを末尾へ追加し、PEQの順序とON／OFFを保存する。
- REW実出力の独立した空枠（None）に対応する。Qは既存仕様の0.1刻み（0.1〜5）に丸める。

## v2.0.0 - 2026-11-13

- Free版とPro版を初版として配布する。FIR Gain／Phaseの自動EQはPro専用。IIR自動EQ、手動FIR、書き出し時のAuto Gain、System Auto Gainは両版で利用できる。
- 簡易版と画像付き操作マニュアル、利用者向け文書でPro専用の手順を明示する。

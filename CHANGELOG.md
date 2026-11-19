# 更新履歴

PhaseEQ Free／Proの変更を、初版の v2.0.0 から記録します。分離前の履歴は [PhaseEQ-publicのCHANGELOG](https://github.com/tomii323/PhaseEQ-public/blob/v1.21.13/CHANGELOG.md) に v1.21.13 まで保存されています。

## 未リリース

## v2.0.1 - 2026-11-19

- REW Generic形式のPEQテキスト読み込みと、REW形式の`.txt`出力を追加する。既存IIRを保持してManual PEQを末尾へ追加し、PEQの順序とON／OFFを保存する。
- REW実出力の独立した空枠（None）に対応する。Qは既存仕様の0.1刻み（0.1〜5）に丸める。

## v2.0.0 - 2026-11-13

- Free版とPro版を初版として配布する。FIR Gain／Phaseの自動EQはPro専用。IIR自動EQ、手動FIR、書き出し時のAuto Gain、System Auto Gainは両版で利用できる。
- 簡易版と画像付き操作マニュアル、利用者向け文書でPro専用の手順を明示する。

# PhaseEQ v2.0.0 更新案内

PhaseEQ v2.0.0では、Free版とPro版をそれぞれ初版として配布します。

| 機能 | Free | Pro |
| --- | --- | --- |
| IIR自動EQ | 利用可 | 利用可 |
| 手動FIR Gain／Phase、帯域分割、FIR書き出し | 利用可 | 利用可 |
| 書き出し時のAuto Gain、MultiwayのSystem Auto Gain | 利用可 | 利用可 |
| FIR Gain／Phaseの自動EQ | — | **Pro専用** |
| MultiwayのMono／Stereo：Fullrange、Fullrange+SUB、2Way | 利用可 | 利用可 |
| Multiwayの2Way+SUB、3Way／4Way（SUB付き含む） | — | **Pro専用** |
| 基本グラフ、Multiwayの解析用Group応答・帯域別の汎用FIR出力 | 利用可 | 利用可 |
| Waveletグラフ、MultiwayのReverse Null・クロス付近のディップ・位相／時間整合の詳細評価 | — | **Pro専用** |
| Multiwayの実機DSP用パッケージ（Generic SOS／Parametersを含む） | — | **Pro専用** |

Freeで有効なFIR自動EQを含む設定を開くと、元の設定を保持し、FIR自動EQを含む結果の再計算・出力を停止します。Freeで作業を続ける場合は、自動EQをOFFにした設定コピーを作成して開いてください。

Freeでも、従来のMultiway復元用ZIPを読み込めます。Freeの「作業設定ZIPを保存」は再開に必要な作業設定を保存し、実機用係数や合成応答は含みません。Proの「作業バックアップを保存」は作業設定に加え、係数やレポートも保存します。Freeで非対応のMultiway構成を開くと、設定を保持して再計算・結果表示・出力を停止します。Free対応の構成に変更するか、Proで開いてください。

Waveletを使う内部計算は両版で継続します。Multiwayの位相・時間整合の適用と基本グラフも両版で利用できます。

簡易操作マニュアルと画像付き操作マニュアルに、Pro専用の操作と、Freeでも使える手動FIR EQの手順を記載しました。旧版の画面例には撮影時の版を記載しています。

v2.0.0以降のFree版は [PhaseEQ-Free](https://github.com/tomii323/PhaseEQ-Free/releases) で提供します。旧公開先 [PhaseEQ-public](https://github.com/tomii323/PhaseEQ-public/releases/tag/v1.21.13) は v1.21.13 で更新を終了しました。旧版をお使いの場合は、[インストールガイド](installation.md)に従い、新しいZIPを別のフォルダーに展開してデータを引き継いでください。

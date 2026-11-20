# PhaseEQ v2.0.5 更新案内

PhaseEQ v2.0.5では、ProのマルチウェイにC-DSP 8x12（Dirac Liveなし・192 kHz）の専用出力を追加しました。既存のDSP出力フローを使い、PEQとXoverを分けた係数TXTと、出力ごとの設定値をZIPへ保存します。

## 使用手順

1. DSP出力先を`miniDSP`、プロファイルを`miniDSP C-DSP 8x12 (192 kHz)`にします。
2. 「このDSP用の設定へ変更」で、現在の構成を192 kHz・DSP FIR出力OFFにし、設計を再計算します。
3. 互換性確認後にZIPを保存します。各出力の`output_peq_192k.txt`を`OUTPUT → PEQ → Advanced → IMPORT`で読み込み、`PROCESS`を実行します。
4. 各出力の`output_xover_192k.txt`で`OUTPUT → Xover → Advanced`の既存テキストを全文置換し、`PROCESS`を実行します。HP／LPと位相整合APはXoverへ配置します。
5. `channel_settings.json`のGain・極性・Delayを出力側へ一度だけ設定します。ルーティングと機器への送信は手動です。

出力ごとに設定する場合は、PEQ・Xoverの他チャンネルへの`Link`を解除してください。読み込み後もPEQのバイパス状態が保持されるため、全段の係数と有効状態を確認してください。Xoverは`biquad1`〜`biquad8`を含む全文を置換してください。

## 形式と制限

- miniDSP Advanced Biquad形式を使用します。確定済みIIR EQ・補助EQはPEQ合計10段、クロスオーバーHP／LP・位相整合APはXover合計8段までです。段数は生成されたBiquadで数え、超過時は出力を停止します。
- 未使用段は通過係数で埋め、PEQ 10段・Xover 8段を毎回書き出します。Gain・極性・DelayはTXTへ含めず、独立設定として出力します。
- 192 kHz専用で、FIRを含む場合は出力を停止します。出力番号は1〜12、Gainは−72〜+12 dB、Delayは0〜25 msです。小数サンプルDelayは互換性警告と機器側の実現値を確認してください。
- C-DSP 8x12 DLには、既存の48 kHz専用プロファイルを使用してください。

詳細は[出力ファイル仕様](output-format.md#マルチウェイのc-dsp-8x12192-khz出力)を参照してください。

## 確認した範囲

隔離したPhaseEQ画面でプロファイル選択、設定変更・復元、ZIPの実ダウンロードと確定係数の一致、PEQ上限超過時の出力停止を確認しました。C-DSPアプリ1.7のオフライン環境では、2出力分のPEQ各10段・Xover各8段、計180係数が保存XMLのfloat32値と一致しました。XoverにはHP／LP・位相整合APを含め、PEQの実画面確認には通過係数を使用しました。

実機への接続・送信、実機内演算、音声測定は未実施です。実機へ適用する前に、対象プリセット、出力先、応答と有効状態を確認してください。

## 更新

作業設定を保存し、[インストールガイド](installation.md)に従って更新してください。更新後はPhaseEQを再起動してください。

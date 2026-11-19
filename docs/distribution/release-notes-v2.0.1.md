# PhaseEQ v2.0.1 更新案内

PhaseEQ v2.0.1では、REW Generic形式のPEQテキストの読み込みと、REW形式の`.txt`出力を追加しました。Free版・Pro版の両方で利用できます。

## 読み込み

1. REWでEqualiserを`Generic`にし、`Export filter settings as text`で保存します。
2. PhaseEQのIIRイコライザーのゲイン画面で「REW PEQの読み込み」を開き、`.txt`を選びます。
3. 周波数・ゲイン・Q・ON／OFFを確認し、「PEQを末尾へ追加」を押します。

既存のIIRを保持し、PK（PEQ）をManual PEQとして末尾へ追加します。空枠（None）は読み飛ばします。周波数は1 Hz〜Nyquist−1 Hz、ゲインは−30〜+20 dB、Qは0.1〜5に対応します。Qは既存仕様の0.1刻みに丸めるため、元の値と応答が変わる場合があります。未対応の種類や範囲外の値を含む場合は追加しません。

## 出力

IIRイコライザー画面、または「書き出し」のIIR EQ出力にある「REW PEQ (.txt)」を使います。手動・自動PEQの順序とON／OFFを保持します。Shelf・HP／LP・All Pass・FIR・出力ゲイン／Delay／極性は含みません。保存したテキストは同じ読み込み欄から追加できます。

REWの`.req`と`Export filter settings as formatted text`は対象外です。詳しい条件は[出力ファイル仕様](output-format.md#rew-peqテキスト)を参照してください。

## 確認した範囲

REW V5.40 Beta 134の画面で実際に保存したファイルを使い、隔離したPhaseEQで読み込み・再出力、既存PEQ／Shelfの保持、ON／OFF、Qの丸めを確認しました。外部ソフト・DSPへ渡す場合は、取込後に周波数・ゲイン・Q・ON／OFFと実現応答を確認してください。

## 更新

作業設定を保存し、[インストールガイド](installation.md)に従って更新してください。更新後はPhaseEQを再起動してください。

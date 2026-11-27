# PhaseEQ 出力ファイル仕様

- 文書更新日: 2026-11-26
- 対象公開版: PhaseEQ v2.0.12
- 文書状態: 現行仕様と15ページ簡易操作マニュアルに対応

PhaseEQの「書き出し」、マルチウェイの「保存・出力」、PhaseEQの「設定 → バックアップと復元」で保存できるファイルを説明します。操作順は[操作ガイド](user-guide.md)、過去の変更は[更新履歴](history.md)を参照してください。

**FIR Gain／Phase自動EQの再生成はPro専用です。** FIR書き出しと書き出し時のAuto Gainは両版で使えます。Freeでは、有効なFIR自動EQを含む作業セッションの元設定を保持し、その補正の再計算・出力を停止します。

各ダウンロード操作時に確定済み設定から必要な出力を準備します。別の準備ボタンは不要です。表示FFT倍率やグラフの間引き点数は出力FIR係数を変更しません。

作業セッションには帯域分割生成定義と生成条件を保持し、帯域分割IIR／Combined IIR chainのJSONおよび極性情報も収録します。新形式FIR生成定義はalgorithm v5です。全IIRと手動FIR Gain適用後に、自動ゲイン用の入力整形を行います。元測定と整形設定を保持し、整形済みの測定配列は保存しません。旧v4は手動FIR Gain適用前の整形順序、旧v1〜v3は入力整形OFFで再生成します。他PCで再生成する場合は受取側も対応版へ更新してください。旧形式v1の再生成は旧グリッドを維持しますが、現在の作業を新条件で再計算・再出力した係数は従来版と変わる場合があります。

FIRイコライザー内のHP／LPは、選んだリニアフェーズLR2／LR4またはIIR LR2／LR4の応答をFIR係数へ含めます。IIR方式を選んでも、別のIIRバイクアッド段として出力する意味ではありません。FIR出力OFFでは適用しません。IIRイコライザーのHP／LPと併用すると両方が適用されるため、同じ減衰の重複を確認してください。

マルチウェイではSystemを保存し、Freeは作業設定ZIP、Proは作業バックアップを保存します。Proで実機へ渡す場合は、DSPプロファイルと警告を確認して実機DSP用ZIPを保存します。簡易版p.14〜15を参照してください。編集上のIIR EQ → FIR EQの調整順と、DSPパッケージに記録する処理段の順序は用途が異なります。

Pro専用のC-DSP 8x12 DL向けZIPは、Pre/PostのXover係数、チャンネル別IIR PEQ、Group Target振幅のターゲットカーブ、対応表`manifest.json`と操作手順を含みます。PEQは任意で、未使用時も全10段の通過係数を出力します。48 kHz・FIR OFF・構造補償ON・全境界LR4／NTM4・音響ターゲットOFF、最大4帯域で使用します。測定登録の分岐と機器側への読込み順は[利用ガイド](user-guide.md#c-dsp-8x12-dlのdiracapf出力)を参照してください。

## ZIPに同梱する生成物の利用条件

室内音響補正（ルームEQ）は作業セッションの設定へ保存し、専用の`room_eq.json`にも独立保存できます。主ターゲットの登録・目標応答ファイルへの書き出しには差分を含めません。専用JSONは曲線、名前、ON/OFF、加算／減算を保存します。差分をONにした目標でEQを設計した場合、その結果を通常のIIR／FIR係数として出力します。差分ファイル自体を追加のDSPフィルターとして重ねないでください。詳細は[室内音響補正（ルームEQ）](room-eq.md)を参照してください。

作業セッション、DSP／FIR書き出し、マルチウェイ、測定セッション、校正済みIR／FRD、測定用音源の各出力ZIPには、直下に`生成物の利用条件.txt`を同梱します。文字コードはUTF-8（BOM付き）です。係数、波形、測定結果、設定ファイルの内容・形式は変更しません。

説明には、個人利用で生成した成果物の事後の商用利用・組み込み・改変・販売・配布が可能であること、本体を商用・業務目的で使って新たに生成・調整することは禁止であること、第三者資料の条件、無保証、条件制定日と正式な[LICENSE.md](../../LICENSE.md)への参照を記載します。この説明ファイルを生成物の再配布時にも添付する義務はありません。

全ファイルの一覧・チェックサムを持つDSP配布ZIPとチェックサムを持つDSP作業再開ZIPでは、この説明ファイルも検査対象です。係数のみを列挙するmanifestの対象は変更しません。本体の配布ZIPには、生成物用の要約ではなく`LICENSE.md`全文を同梱します。

## 出力の分類

| 出力 | 用途 | 復元用か |
|---|---|---|
| 目標応答 | 目標応答の受け渡し | いいえ |
| IIR バイクアッド | 外部DSPへのIIR実装 | いいえ |
| Generic IIR Parameters | バイクアッドを直接入力できないIIR-only DSPへの設計値転記 | いいえ |
| REW IIR (.txt) | REW Generic形式のIIR設定の受け渡し | 下記の対応形式を読み込み可能 |
| FIR coefficients / WAV | 畳み込みエンジンへのFIR実装 | いいえ |
| システム プリセット JSON | DSPシステム設定の保存・再利用 | はい |
| DSP Configuration Package ZIP | Device別の実装ファイル一式 | いいえ |
| Manifest JSON | Package内容、署名、安全判定の監査 | いいえ |
| Current settings JSON / Local snapshot | 現在設定と編集状態の復元 | はい |
| 作業セッションZIP | 作業状態と読み込み済み応答の移動・再開 | はい |
| 測定データ JSON | 測定DBの移行 | はい |
| ドライバーデータベース JSON | ドライバー諸元DBの移行 | はい |
| 測定パッケージ | 未校正統合IR、別校正データ、測定条件・時間情報の保管 | 保存済み原本からの再計算用 |

## 目標応答

目標特性の周波数、ゲイン、位相をCSV／テキスト形式で出力します。周波数はHz、ゲインはdB、位相はdegreeです。出力対象はEditorで適用済みの目標特性であり、未適用のプレビューは含めません。

## IIR バイクアッド

IIRイコライザー、出力帯域分割、両者を直列にしたCombined IIR chainを選択して出力します。出力帯域分割には直接出力のLR2／LR4・1次／2次オールパス・極性を含めます。音響ターゲットへ移した成分は直接出力から除き、LR2自動極性は帯域分割の設定、オールパスは位相・時間整合の設定に従います。手動極性は独立して直接適用します。完全な出力係数に含まれる極性を外部DSPで二重に適用しないでください。

| 形式 | 係数規約 |
|---|---|
| Generic / internal | `b0, b1, b2, a1, a2` |
| CamillaDSP | `DiffEq` |
| SigmaDSP / SigmaStudio | `B0, B1, B2, A1, A2` |
| miniDSP | 内部`a1/a2`の符号を反転した機器規約 |

量子化後の極半径が`0.9999`以上になる構成は安全判定を通過せず、正式なDSP Package出力を許可しません。表示用の理論応答ではなく、実際に出力する量子化係数で判定します。

### miniDSP Device Consoleへの読み込み

`miniDSP`のTXTはAdvanced Biquad形式です。`2x4 HD (48kHz)`では48 kHz、`2x4 HD`では96 kHzで生成してください。対象チャンネルの`PEQ`を開き、`Menu`をONにして`LOAD BIQUADS FILE`から読み込みます。読み込み後は各段がAdvanced Modeになり、周波数・Gain・Qの編集値への逆変換は行われません。

1つのPEQブロックは10段です。HP／LPやAPプリセットは複数段になる場合があるため、フィルター項目数ではなくTXTの`biquad`段数を確認してください。10段を超えるファイルはConsole側で先頭10段のみ読み込まれます。10段未満の場合は残りのEQが保持されるため、不要な段の無効化も確認してください。汎用miniDSP出力の上限は機種別の10段制限と連動しないため、出力前に対象ブロックへ収まることを確認してください。

StandaloneのIIR出力は有効なPEQ、Shelf、HP／LP、1次／反転1次／2次AP、係数形式のIIRを既存のバイクアッド列として保存します。FIR、ルーティング、別設定のゲイン・遅延はこのTXTに含みません。マルチウェイの別ファイルを同じPEQブロックへ続けて読み込むとEQ1から上書きされます。ZIP内の経路情報と設定ファイルに従って配置してください。

Device Console 1.2.5の両オフラインテンプレートで、単体EQと2つのマルチウェイ出力経路の読み込み、および保存係数のfloat32値を照合しました。実機への送信・音声処理は未確認です。実機へ適用する前に対象モデル、動作サンプルレート、使用するプリセットを確認してください。形式と読み込み動作は[miniDSP公式PEQ仕様](https://docs.minidsp.com/product-manuals/2x4-hd/dsp-reference/peq.html)を参照できます。

### マルチウェイのC-DSP 8x12（192 kHz）出力

ProのDSP出力先で`miniDSP`、プロファイルで`miniDSP C-DSP 8x12 (192 kHz)`を選びます。「このDSP用の設定へ変更」は、現在のマルチウェイ構成のFsを192 kHz、DSP FIR出力をOFFにします。PhaseEQのEQ設定やWorking Sessionは保持します。設計を再計算し、互換性確認後にDSP出力ZIPを保存します。Dirac Live付きのC-DSP 8x12 DLには、48 kHzの専用出力を使用してください。

各出力の`output_peq_192k.txt`はIIR EQ → 補助EQ、`output_xover_192k.txt`はIIRクロスオーバー（HP／LP）→ 位相整合の補償APです。PEQは合計10段、Xoverは合計8段を超える場合に出力を停止します。残りの段は通過係数で埋め、毎回PEQ 10段・Xover 8段を書き出します。出力番号は1〜12、Gainは−72〜+12 dB、Delayは0〜25 msです。小数サンプルのDelayは互換性警告と設定値を確認し、機器での実現値を確認してください。FIRを含む出力と192 kHz以外の出力は許可しません。

1. ZIP内の`setup_guide.txt`と各出力の`channel_settings.json`で出力先を確認します。
2. 不要な入力EQ・コンプレッサー等を解除し、入力ルーティングとチャンネル間のLinkを確認します。出力ごとに設定する場合は、他出力へのLinkを解除してください。
3. `OUTPUT → PEQ → Advanced → IMPORT`で、その出力の`output_peq_192k.txt`を読み込み、`PROCESS`を実行します。全10段の係数と有効状態を確認してください。読み込み後もバイパス状態が保持される場合があります。
4. `OUTPUT → Xover → Advanced`へ、その出力の`output_xover_192k.txt`の全文を貼り付け、`PROCESS`を実行します。Xoverは8段全体を一度に設定します。有効状態を確認してください。
5. JSONのGain・極性・Delayを出力側へ一度だけ設定します。TXTにはこれらの独立設定を含みません。

ルーティングや機器への送信は手動で行います。実機での演算・音声測定は未確認です。適用前に対象プリセット、出力先、機器側の応答と有効状態を確認してください。

## Generic IIR Parameters

`汎用IIRパラメーター`は、バイクアッド係数を直接入力できず、IIRフィルターの設計値を手入力するDSP向けのMarkdown文書です。サンプルレートと、各フィルターの`Apply order / Type / Frequency [Hz] / Gain [dB] / Q / Order / Enabled / Family / Origin / All-pass preset`を記録します。無効なフィルターも`Enabled: No`として残し、編集内容と並び順を失いません。

PhaseEQ 書き出しではIIRイコライザー、出力帯域分割ページ、両者を直列にしたCombined IIR chainごとに個別ダウンロードできます。作業セッションZIPでは`outputs/<Project>_<Band>_IIR_Generic-Parameters_<SampleRate>_<Timestamp>.md`として収録します。帯域がない場合はファイル名から省略します。

転記時は適用 orderの上から順に設定します。DSPごとにShelf Q、クロス family、オールパスの定義や設定可能範囲が異なります。転記前に仕様を照合し、転記後は対象DSPの実現応答を確認してください。

追加のオールパス・極性段はGeneric IIR Parameters内でもバイクアッド係数表として記録します。通常のパラメーター表だけを転記しても全段は再現できません。

## REW PEQテキスト

`IIR EQ`のGain／Phase画面と「書き出し」のIIR EQ出力にある`REW IIR (.txt)`で、手動・自動IIRを現在の順序とON／OFF状態で保存します。PEQに加えてShelf・HP／LP・2次All Passを扱います。

読み込みは`IIR EQ → REW IIRの読み込み`から行います。REWのEqualiserを`Generic`にし、`Export filter settings as text`で保存したファイルを選びます。種類・次数・周波数・ゲイン・Q・ON／OFFのプレビューを確認し、`IIRを末尾へ追加`を押します。既存IIRを保持し、Manual IIRとして追加します。All Passの編集はPhase画面で行います。`None`行は読み飛ばします。

| REWの種類 | 読み込み先・条件 |
|---|---|
| `PK` | PEQ、Q 0.1〜5 |
| `LS`／`HS` | Low／High Shelf、固定Q≈0.7071を既存の0.1刻みへ丸めます |
| `LS Q`／`HS Q`（`LSQ`／`HSQ`も可） | Low／High Shelf、Q 0.1〜1 |
| `HP`／`LP` | 2次Butterworth HP／LP |
| `HP1`／`LP1` | 1次Butterworth HP／LP |
| `HP Q`／`LP Q`（`HPQ`／`LPQ`も可） | 2次Variable-Q HP／LP、Q 0.01〜100。Qの丸めは行いません |
| `All pass`／`AP` | 手動2次All Pass、Q 0.1〜100 |

周波数は1 Hz〜Nyquist−1 Hz、ゲインは−30〜+20 dBとします。PEQ・Shelf・All PassのQは既存編集仕様の0.1刻みへ丸めるため、元の応答と差が生じる場合があります。追加後の合計は既存IIRを含め128件までです。範囲外、未対応種類、不正な行、フィルター番号重複、件数上限超過がある場合はファイル全体を追加せず設定を保持します。UTF-8（BOM付きも可）を読み込みます。

出力ではShelfを`LS Q`／`HS Q`、2次HP／LPを`HP Q`／`LP Q`として保存します。Butterworth・BesselのHP／LPは1〜4次・6次・8次、Linkwitz-Rileyは2次・4次・6次・8次を扱います。4次は2次段×2、8次は2次段×4として、既存係数計算から出力用の段を作り、合成応答を照合します。8次以上も4次以下の段を組み合わせる方針で、REW TXTでは1次／2次段を使用します。現在の編集上限は8次です。各段の周波数とQは元の係数から求め、同じFamily・周波数の4次フィルターを単純に重ねる処理は行いません。対応可能なAll Passプリセットも2次段へ展開します。再読み込み後は各段が独立したManual IIRとなり、元のFamily・プリセット・Autoの由来は復元しません。All Pass段のQも読み込み時の丸め対象です。

特殊なShelf傾斜（`LS 6dB`／`HS 6dB`／`LS 12dB`／`HS 12dB`）、1次All Pass（`AP 1`／`AP 1 inv`を含む）、Elliptic／NTM4のHP／LP、専用クロスオーバー行、Generic以外のEqualiserは対象外です。出力一覧に表現できないフィルターがある場合は、その項目を除外して書き出し可能な項目だけを出力します。複数段へ展開する項目は、全段を出力できる場合だけ含めます。OFFの項目も同じ判定を行います。FIR・出力ゲイン／Delay／極性・独立した帯域分割は含みません。

`REW IIR 出力結果 (.csv)`は、元IIR番号・種類・設定値・ON／OFF・出力Filter番号・成否・エラー理由を別ファイルに保存します。対象外の項目は出力Filter番号が空欄です。全件が対象外の場合はCSVだけを出力します。CSVを確認し、必要な項目はBiquad出力を使用してください。

REWの`.req`と`Export filter settings as formatted text`は対象外です。REW自身のフィルター保存・復元には`.req`を使います（[REW公式File Menu](https://www.roomeqwizard.com/help/help_en-GB/html/file.html)）。外部ソフト・DSPへ渡す場合は、受信側が対応する種類・段数・周波数・Qの範囲を確認し、取込後の各値・ON／OFFと実現応答を確認してください。

### CamillaDSP用YAMLの読み込み

同じ読み込み欄で、REWのCamillaDSP用に保存した`.yml`／`.yaml`を選べます。CamillaDSP本体の設定ファイルは不要です。`filters:`のパラメーター形式と係数形式を読み込み、任意の`pipeline:`がある場合はその`names`順に追加します。`pipeline`なしでは定義順を使用します。

| CamillaDSP形式 | PhaseEQでの扱い |
|---|---|
| `Biquad`: `Peaking`／`Lowshelf`／`Highshelf` | PEQ／Shelf、`q`と`gain`を指定 |
| `Biquad`: `Highpass`／`Lowpass` | 2次Variable-Q HP／LP |
| `Biquad`: `HighpassFO`／`LowpassFO` | 1次Butterworth HP／LP |
| `Biquad`: `Allpass`／`AllpassFO` | 手動2次AP／通常の1次AP |
| `BiquadCombo`: `ButterworthHighpass`／`ButterworthLowpass` | 1〜4次・6次・8次 |
| `BiquadCombo`: `LinkwitzRileyHighpass`／`LinkwitzRileyLowpass` | 2次・4次・6次・8次 |
| `DiffEq`: `a`／`b`配列 | 各配列1〜3要素。0〜2次の係数段として保持 |
| `Biquad`: `Free` | `b0`・`b1`・`b2`・`a1`・`a2`を係数段として保持 |

単一チャンネル・単一Filterステップを扱い、各定義を一度ずつ参照します。REWが出力に含めなかったOFFフィルターは復元しません。読み込む項目はすべてONになります。パラメーター形式の周波数・ゲイン・Q制限とQの丸め、既存項目との合計128件の制限は上記TXTと共通です。複数チャンネル、機器設定付きの完全な構成ファイル、パラメーター形式のNotch、LinkwitzTransform、bandwidth／slope指定などは対象外です。未対応項目、不正な参照、重複キー、YAML aliasを含む場合は全体を追加せず、既存設定を保持します。

係数形式は1段ごとに`Biquad係数`として追加し、a0=1へ正規化します。足りない1次・0次の係数は0で補います。パラメーターへの推定変換やQの丸めを行わず、Gain／Phaseの両画面に表示します。ON／OFF・複製・削除を行えます。係数は直接編集できません。3次以上のDiffEq単独定義、非有限値、a0=0、単位円上または外側に極を持つ段は拒否します。高次HP／LPは、PhaseEQが出力した2次以下の複数段をそのまま読み込みます。

係数には元のFsが必要です。読み込み前にPhaseEQのFsを出力元に合わせてください。新しいStandalone出力とマルチウェイの`filters_phaseeq_iir.yml`／`filters_crossover_iir.yml`にはFsコメントを記録し、不一致時は読み込みを拒否します。Fs情報のない既存ファイルは、読み込み時のFsを保存します。取り込み後のFs変更では有効な係数項目の処理を停止します。元のFsへ戻すか、その項目をOFFにしてください。設定JSONには係数とFsを保存します。この項目を含む設定は対応版のPhaseEQで使用してください。

再出力は`CamillaDSP`ボタンを使い、DiffEq形式へ出力します。Freeとして読み込んだ項目もDiffEqとして出力します。REW TXTでは係数項目を除外し、結果CSVへ理由を記録します。マルチウェイの分離IIR YAMLを読み込む場合は、対象経路だけを残した`filters:`を使用してください。機器・経路・ゲイン・遅延・FIRの設定を含む全体構成は読み込みません。

`AllpassFO`は通常の1次APです。極性反転付き1次APはPhase画面のプリセット`1次AP・極性反転（LR2ハイパス）`で指定します。既存の`lr2_hi`設定と同じ計算・保存形式を使用します。どちらの1次APもREW Generic TXTからは除外され、結果CSVに理由が記録されます。係数を保持して渡す場合はBiquad出力を使用してください。PhaseEQのCamillaDSP出力は従来の`DiffEq`係数形式です。

形式の原典は[REW Equaliser](https://www.roomeqwizard.com/betahelp/help/html/equaliser.html)と[CamillaDSP IIR仕様](https://github.com/HEnquist/camilladsp#iir)です。REWのCamillaDSP出力で1次APを保存できることは未確認です。標準`AllpassFO`の読み込み対応と区別します。

## FIR

FIRはテキスト係数またはWAVとして出力します。サンプルレート、タップ数、極性、正規化、対象出力は、適用済みのDSPシステム設計条件に従います。

- `出力FIRの極性反転`を有効にすると、個別FIRとPackage内FIRの両方へ反映します。
- システムまたはDeviceがFIR非対応、または対象出力がFIR bypassの場合、そのDevice Packageから該当FIR段を省略します。
- FIR Peak、係数長、サンプルレートの不整合は書き出し Gateで検査します。

書き出しグラフはFIR出力、IIR出力、FIR＋IIR出力を分けて表示します。スピーカー＋実現応答と時間波形には両方を一度ずつ適用します。FIR OFF時のFIR出力はバイパス表示で、FIRファイルを生成する意味ではありません。合成グラフによってFIR係数へIIRを畳み込むことはありません。

## システム プリセット JSON

`Download System preset`は、DSPシステム、Device、入力、Route、出力、クロス、アライメント、適用済み目標特性／IIR／FIRを再利用するためのJSONです。未適用のEditor Working Copyは最終出力条件として扱いません。

## DSP Configuration Package ZIP

`Download DSP Package ZIP`は、接続Deviceごとの設定と係数をまとめた実装用アーカイブです。現在のPackage manifestは`schema_version: 8`です。

Packageには構成に応じて次を含みます。

- Device／入力／Route／出力 チャンネル設定
- 目標特性、IIR、FIR、クロス、ゲイン、遅延、極性
- CamillaDSP、miniDSP、SigmaDSP／SigmaStudio向け設定または係数
- 設計 Signatureと生成条件
- Headroom、Peak、IIR安定性などの安全判定
- Manifest

Packageは、現在の設計 Signatureに対応するシステム応答を更新し、`設計を保存`で正式保存した後だけ出力できます。設定変更後に古い計算結果を流用することはできません。

## マルチウェイの作業再開用ZIP（Free／Pro）

Freeの「作業設定ZIPを保存」は `multiway_workspace.zip` を出力します。内容は作業再開用の `workspace.json`、`manifest.json`、`checksums.sha256`、`生成物の利用条件.txt` です。実機用係数、DSP構成ファイル、合成応答は含みません。解析用Group応答と帯域別の汎用FIR係数は両版で別に書き出せます。

Proの「作業バックアップを保存」は `multiway_dsp_package.zip` を出力します。作業再開用の設定と、設計に応じた係数・レポートを含みます。どちらの作業再開用ZIPも、旧版の復元用ZIPと同じ読込入口を使います。Freeで非対応の構成を開いた場合は、設定を保持し、再計算・結果表示・出力を停止します。

## マルチウェイ Studio DSP 書き出し v3（Pro専用）

PhaseEQ同梱マルチウェイ Studioの`DSP 書き出し v3`は、上記PhaseEQ DSPシステム Packageとは独立した後段DSP用アーカイブです。ファイル名はシステム名、モード、DSP Adapter、サンプルレート、生成日時を含みます。Adapter選択はStudioのスピーカー、PhaseEQ、クロス、位相整合、グラフ状態を変更しません。

共通構成は次のとおりです。

- チャンネル別の最終FIR、`phaseeq_iir.json`、`crossover_iir.json`、ゲイン／極性／遅延
- PhaseEQ IIR、IIRバッフル補正、IIR帯域分割、帯域分割補償オールパスを別Stage／別ファイルで保持
- `manifest.json`（`format: phaseeq-multiway-dsp-export`, `format_version: 3`）、SHA-256、ワークスペース、チャンネル設定表、検証Report
- 処理順は`Final FIR → PhaseEQ IIR → Baffle IIR → IIR crossover → crossover All-pass → Gain → Polarity → Delay`
- 画面の「タップ長とディレイ目安」にある`DSP追加Delay [samples]`と同じ積算結果を出力します。FIR起点補償・FIR理論差補償・測定補正・Way相対Delay・整合Delayの残り・共通オフセットを含み、FIR使用時は最小値を全出力から差し引きます。FIR係数自体の中心遅延`(N-1)/2`は追加しません。内訳は[利用ガイドのDelay説明](user-guide.md#composite-engine)で確認できます。
- 外部アプリで測った距離を時間基準にした場合、チャンネル別`channel_config.json`の`timing_provenance.external_distance_alignment`へ距離[m]、公称音速343.42 m/s、入力元を監査情報として記録します。距離から求めた実適用値は`delay.phase_alignment_samples`へ一度だけ含め、書き出し時に再加算しません。
- FIR OFFのチャンネルは`tap_count=null`、`final_fir=null`として扱い、FIR WAV／CSV／BIN、FIR 生成定義、FIR reportを出力しません。IIR、ゲイン、極性、遅延はFIRと独立して出力します。
- `documentation/system_summary.md`、`documentation/system_specification.md`、`documentation/system_specification.json`を同梱します。3ファイルは同じCanonical DSP Packageから生成し、保存済みマルチウェイ システムがある場合はシステム ID、管理No、システム 改訂番号、content hashを記録します。チャンネル、FIR固有センター遅延、DSP追加遅延、FIR／IIR、DSP profile、signature、検証結果も同じ型番から出力します。単独編集出力は保存済みシステムを偽装しません。
- PhaseEQ 作業セッションには`documentation/session_specification.md`と`documentation/session_specification.json`を同梱します。割り当てにシステム provenanceがある場合はそのシステム／目標特性参照を記録し、それ以外は単独編集 sessionとして明示します。

| Adapter | 主な出力 |
|---|---|
| miniDSP | チャンネル別float32 little-endian `final_fir.bin`、PhaseEQ／クロス別Advanced バイクアッド TXT、チャンネル設定 |
| CamillaDSP | float32 WAV係数、`camilladsp.yml`、PhaseEQ／クロス別Filter YAML |
| SigmaStudio | FIR float／5.23、General 2nd 次数係数 float／5.23、Block map、チャンネル設定 |
| Generic SOS | PhaseEQ IIR、Baffle IIR、IIR クロス、補償オールパスを別CSVにした標準SOS出力 |
| Generic Parameters | IIR-only機器向けPhaseEQ `type / Hz / dB / Q` CSVとクロス／オールパス JSON。FIR非対応、整数遅延前提 |

CamillaDSPのCanonical出力は`F32_LE`のStdin／Stdoutを含みます。実際の音声機器で使う場合は`devices`を対象環境に合わせ、係数フォルダーを保った状態で`camilladsp --check camilladsp.yml`を実行してください。DSP System側のYAMLはFilter／Mixer／pipelineのsnippetなので、別途`devices`設定が必要です。

Canonicalの小数サンプルDelayはCamillaDSPのAP近似を使用します。高域では理想的な時間シフトとの差が生じる場合があります。4.1.3では0.1 samples未満のsubsample Delayは無視されます。DSP System側は整数サンプルへ丸めます。形式・適用範囲は[CamillaDSPのDelay仕様](https://github.com/HEnquist/camilladsp/blob/v4.1.3/README.md#delay)と[実装上の微小遅延の条件](https://github.com/HEnquist/camilladsp/blob/v4.1.3/src/filters/basicfilters.rs)で確認できます。

Proの`作業バックアップ`（内部形式：DSP package + Resume v2）と`実機DSP用パッケージ`（内部形式：DSP 書き出し v3）は目的とVersion体系が異なります。前者は作業継続、後者は後段DSPへの投入が主目的で、相互のVersion番号を読み替えません。DSP 書き出し v3にも`configuration/workspace.json`が含まれるため、マルチウェイ Studioの区間 7「設定ファイルを読み込む／作業を再開」で読み込めます。読込前にパスとSHA-256を検証し、初期のv3で表示選択値が欠けている場合は、保存されたモノラル／ステレオのチャンネル構成からMainまたはL+Rへ安全に補完します。

## Manifest JSON

`Download Manifest JSON`はPackageと同じ生成条件を単独で確認するための監査用JSONです。Device、出力ファイル、サンプルレート、係数形式、設計 Signature、安全判定を記録します。Package本体の代替ではありません。

## 作業セッションZIP

旧称`Project ZIP`です。現行UIでは`Application > バックアップと復元`から書き出し／Importします。

含むもの:

- 現在設定と編集状態
- 読み込み済みスピーカー入力、マイク校正、目標応答の数値
- 作業再開に必要な選択状態と応答参照

含まないもの:

- 測定データ DB全体
- ドライバーデータベース全体
- DSPシステム DB全体の完全バックアップ
- 測定データ セッションの生データ音声や測定単位NPZ

別PC移行、長期保管、DB初期化前には、作業セッションZIPだけでなく測定データ JSONとドライバーデータベース JSONも保存してください。

## 測定データ セッションZIP

連続測定中の一時ファイルは作業用です。`Save Measurement`がDBへ成功すると対象セッションの一時領域は整理されます。測定パッケージ（schema 5）は統合未校正IR 1本の圧縮NPZ、calibration.json、measurement.jsonだけを含みます。生データ・各ショットIRは含めません。ライブラリの外部出力ZIPはcalibrated_ir.wav、calibrated_response.frd、calibrated_output.jsonです。FRDは校正有効帯域の校正済み応答、WAVは同条件の校正済みfloat32 IRで、ピーク正規化しません。単位・感度・Gate・時間原点と別保持の到達時刻は付属JSONを参照してください。

### 新形式の内容と既存形式との関係

| 出力/保存 | 内容 | 使用目的 |
|---|---|---|
| 測定DB | 統合未校正IRの圧縮BLOB＋別校正/recipe/metadata、校正済みFRキャッシュ | 通常のライブラリ利用 |
| 測定パッケージschema 5 | `integrated_uncalibrated_ir.npz`、`calibration.json`、`measurement.json` | 任意の移動・保管。停止・統合後に出力 |
| 校正済み出力ZIP | `calibrated_ir.wav`、`calibrated_response.frd`、`calibrated_output.json` | 外部利用。merged/ungated/gatedを選択 |
| 測定データ JSON | 原本NPZのBase64＋校正・metadata・測定レコード | 測定DB全体のバックアップ/別DB復元 |
| 作業セッションZIP | 現在の設計設定・入力応答・設計成果物 | 作業再開。測定原本DB全体のバックアップではない |

外部WAVのsample 0は円環IRの中心で、実測の到達時刻は別metadataです。波形の長さにはFFT paddingを含み得るため、長さから観測精度を推定しないでください。外部アプリでの読込結果は未検証です。読込後は、音圧と時間原点の扱いを確認してください。旧セッションZIPは互換読込を維持し、既存ファイルを自動変換しません。

## ファイル名と時刻

ダウンロード名には設計／システム名と生成時刻を含めます。時刻はファイル同士の対応確認に使い、内容の同一性は設計 SignatureとManifestで判定します。ファイル名が同じでも署名が異なる場合は同一設計として扱いません。

## 書き出し前の確認

1. 入力、目標特性、使用するFIR／IIRを確認します。
2. PhaseEQの「書き出し」でFIR・IIRそれぞれの応答と合成応答を確認します。
3. マルチウェイへ返す場合は「マルチウェイへ送信」を押し、受信後の各チャンネルと合成応答を確認します。
4. 作業を再開するための設定や作業セッションを保存します。
5. 実機で使う係数や、Proで生成するマルチウェイの実機DSP用パッケージを保存し、サンプルレート、タップ数、チャンネルの対応を確認します。

作業保存と実機用係数の出力は別の操作です。保存物の用途は本書冒頭の表で確認してください。

書き出した後は[出力データの確認と外部機器での利用](user-guide.md#external-use)を参照してください。形式への対応は全機種・全ファームウェアでの実機動作確認を意味しません。機種別の取込・接続・再生操作は、対象機器の公式説明書で確認します。PhaseEQには音楽再生機能はありません。

実画面で手順を確認する場合は、[画像付き操作マニュアル（PDF）](manual/PhaseEQ_v2.0.0_画像付き操作マニュアル_日本語.pdf)の第9章「書き出しとマルチウェイ連携」と第12章「マルチウェイ：測定済みデータからDSP出力へ」を参照してください。


### Delayの内訳と合計

DSP追加DelayはFIR起点補償・理論差補償・測定補正・Way相対Delay・整合Delayの残り・共通オフセットの合計です。`channel_config.json`の`delay.total_samples`／`total_ms`と機種別設定へ同じ合計を出力します。内訳は`adaptive_crop.delay_breakdown`に保持します。測定到達差は補正前の値で、合計への加算項目は測定補正です。FIR自体の中心遅延は係数に含まれるため、DSP追加Delayへ重ねて加えないでください。

FIR使用時は全出力の積算Delayの最小値を共通基準として差し引き、相対値をDSPへ渡します。差引量がある場合は`delay.reference_reduction_samples`へ記録します。欠落時は0です。FIR係数とチャンネル間の時間差を維持し、FIR自体の遅延は差し引きません。

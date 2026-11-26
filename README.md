# daily-fitness-paper-line

筋トレ・コンディショニングの新しい論文（海外のものを含む）を **毎朝1本、日本語で要約して LINE に届ける** ツールです。
パーソナルトレーナー・柔道整復師が、論文を探して英語で読む手間をかけずに、新しい知見に毎日触れられるようにしました。

<!-- スクショ：LINE に届いた要約の画面を docs/ に置いてここに貼る -->

## 何をするものか

毎朝 7:17（日本時間）に GitHub Actions が動き、次の流れで1通送ります。

1. **論文を探す**：PubMed（医学・スポーツ科学の論文のデータベース）で、曜日ごとのテーマの新しい論文を探す
2. **日本語で要約する**：Gemini（Google の AI）が、要旨を「結論・どんな実験か・現場での使い方（トレーニング／指導／施術）」にまとめる
3. **対応策を補う**（今日の論文に具体的なやり方が書かれていない日だけ）：PubMed で関係する別の研究（メタ分析など）を探し、その要旨にある対応策を「関連する別の研究から（参考）」として2〜3文添える
4. **LINE で送る**：公式アカウントから友だち全員に一斉送信する
5. **記録する**：送った論文を `sent.json` に残し、同じ論文を2回送らない

| 曜日 | テーマ |
|---|---|
| 月 | トレーニング（筋肥大・筋力） |
| 火 | ケガ・リハビリ |
| 水 | 栄養 |
| 木 | ボディビル |
| 金 | 減量 |
| 土 | コンディショニング・柔軟性 |
| 日 | テーマを決めず、新しい論文から |

### 工夫したところ

- **英語のままは送らない**：AI が混んでいるときは、待ってやり直し → 別のモデル → それでも駄目なら 10:17 の予備の実行でもう一度試す
- **使えない論文は送らない**：AI が「トレーニング・指導・施術のどれにも使えない」と判断した論文（病気の薬の研究など）は飛ばして次の論文にする
- **対応策は別の研究から、出どころ付きで**：遺伝子の研究などで「では、どうすればいい？」が残る日は、AI の知識で書かせず、PubMed で探した別の論文の要旨から書き、リンクを付ける（試運転でのご主人の声から。2026-11-26〜1か月試す。止めるときは `config.py` の `RELATED_STUDY = False`）
- **信頼性の高い研究を先に**：ランダム化比較試験・メタ分析などを先に探し、見つからなければ期間を広げる
- **要旨に無いことは書かせない**：数字・人数は要旨にあるものだけ。こじつけそうな用途は「この論文からは言えません」と書かせる

## 使う技術

- Python 3.12
- PubMed E-utilities API（論文の検索。無料・鍵なし）
- Gemini API（要約。無料枠）
- LINE Messaging API（一斉送信。無料プランは月200通）
- GitHub Actions（毎日の定期実行）
- requests、python-dotenv、pytest

## 事前準備

1. **LINE 公式アカウント**を作り、Messaging API を有効にする（[LINE Official Account Manager](https://manager.line.biz/)）
2. [LINE Developers](https://developers.line.biz/console/) の「Messaging API設定」で **チャネルアクセストークン（長期）** を発行する
3. 届けたい人に、公式アカウントを **友だち追加** してもらう（同じ画面の QR コード）
4. [Google AI Studio](https://aistudio.google.com/apikey) で **Gemini の鍵** を作る

## 秘密ファイルの用意の仕方

鍵はコードに書かず、手元では `.env`、GitHub では Secrets に入れます。`.env` は `.gitignore` に入っているので GitHub には載りません。

```
GEMINI_API_KEY=Gemini の鍵
LINE_CHANNEL_ACCESS_TOKEN=LINE のチャネルアクセストークン（長期）
```

GitHub Actions 用には、リポジトリの Settings → Secrets and variables → Actions に同じ名前で入れます（`gh secret set -f .env` でもまとめて入れられます）。

## 使い方

```bash
pip install -r requirements.txt

python main.py --dry-run             # LINE に送らず、送る文を画面に出す（記録もしない）
python main.py --dry-run --weekday 3 # 木曜（ボディビル）のテーマで試す（0=月 … 6=日）
python main.py                       # 本当に LINE に送る（今日もう送っていれば何もしない）
pytest                               # 単体テスト（通信しない）
python evaluate.py 2                 # まとめテスト：各曜日2本を送らずに要約し、要旨に無い数字などを自動チェック
python evaluate.py --pmids 42677907  # 番号を指定した論文だけでまとめテスト（関連する別の研究の確認など）
```

毎日の実行は `.github/workflows/daily.yml` で設定しています（7:17 と予備の 10:17）。
検索の言葉・曜日のテーマ・AI のモデルは `config.py` で変えられます。

## ファイル

| ファイル | 役割 |
|---|---|
| `main.py` | 全体の流れ |
| `pubmed.py` | 論文を探す |
| `summarize.py` | Gemini で日本語に要約 |
| `related.py` | 関連する別の研究を探して、対応策を添える |
| `message.py` | LINE の文を組み立てる |
| `line_send.py` | LINE で送る |
| `history.py` | 送った論文の記録（`sent.json`） |
| `config.py` | 設定値 |
| `evaluate.py` | まとめテスト（要約の質の確認） |
| `要件定義書.md` | 何をなぜそう作ったか |

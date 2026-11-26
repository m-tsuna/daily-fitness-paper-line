# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要
柔道整復師・パーソナルトレーナー（本人のご主人。ボディビルの大会にも出る）に、筋トレ・コンディショニングの新しい論文を毎朝1本、日本語で要約して LINE で届けるツール（講座 5-2-2「他者が使うツール②」）。ご主人は LINE を読むだけで、操作はしない。用途は「自分のトレーニング・お客さんへの指導・施術」の3つ。決めたことと理由は `要件定義書.md`、記事の材料と細かい経緯は `作業記録.md`（GitHub に載せない）。

## 使う技術
- Python 3.12（手元は Anaconda の 3.14）／requests・python-dotenv・pytest
- PubMed E-utilities（esearch → efetch の XML。鍵なし）／Gemini API（無料枠・JSON の形を指定）／LINE Messaging API の一斉送信（broadcast。ユーザー ID 不要）
- GitHub Actions の定期実行（`.github/workflows/daily.yml`）

## 動かし方（コマンド）
- `python main.py --dry-run` LINE に送らず文を表示（記録もしない）。`--weekday 0〜6` で曜日のテーマを指定
- `python main.py` 本当に送る（今日もう送っていれば何もしない）
- `pytest -q` 単体テスト（通信しない）。1つだけなら `pytest tests/test_main.py -k 予備`
- `GEMINI_MODELS=no-such-model python main.py --dry-run` AI が使えないときの動きを試す
- `HTTPS_PROXY=http://127.0.0.1:9 python main.py --dry-run` 通信できないときを試す
- `python evaluate.py --pmids 番号,番号` 指定した論文だけでまとめテスト（関連する研究の確認用）
- `python evaluate.py 2` まとめテスト（各曜日2本を送らずに要約し、自動チェック。結果は `test_data/`。頼み方を変えたら必ず流して、要旨と照らし合わせる）

## 処理の流れ（複数のファイルにまたがる所）
- `main.py`：今日送った？（`history.sent_today`）→ `pubmed.candidates()` が候補を1本ずつ渡す → `summarize.summarize()` → `summarize.is_useful()` で3つの用途とも「この論文からは言えません」なら飛ばして次（最大 `MAX_SUMMARIES` 本。タイトルが英語のまま＝`UNTRANSLATED` も飛ばす）→ やり方が書かれていなければ（`no_method`）`related.find()` で関連する別の研究を探して添える（見つからなくても送る）→ `message.build()` → `line_send.send()` → `history.add()`
- 曜日のテーマと検索の言葉は `config.TOPICS`。テーマごとの `steps` で探す期間・研究の種類で絞るかを変えられる（無ければ `SEARCH_STEPS`）
- 「今日」は日本時間で数える（Actions は UTC）。cron は 7:17（本番）と 10:17（予備）
- `sent.json` は Actions がコミットして保存する。`"skipped": true` は使えないので飛ばした論文（送ったことにはならないが、次から候補にしない）
- 終わりの番号：送れなかったら 1（Actions が赤くなる）

## コードの書き方・守るルール
- **AI が駄目でも英語のまま送らない**（本人の指摘：「翻訳なしでもらっても読めない」）。待ってやり直し → 次のモデル → それでも駄目なら番号1で終わり、予備の実行に任せる
- 要約は要旨にあることだけ。こじつけそうな用途は `summarize.NOT_APPLICABLE` と書かせる。ただし厳しすぎると全部飛ばされるので、控えめな言い方（「〜の参考になります」）は認めている
- LINE の文は1行目からタイトルの日本語訳（言い換えず直訳。見出しや日付の行は付けない。本人の希望）。並びは 結論 → どんな実験か → 結果 → 現場での使い方。結果には効果が出た条件（期間・タイミング）を必ず入れる（結論だけだと「結局いつ飲めばいい？」が残った）
- 文末はです・ます。専門用語はトレーナーが普段使う日本語に
- 通信する関数は `log` と `sleep` を引数で受け取り、テストで差し替える
- エラーは「何が起きたか → どうすればよいか」の日本語で、鍵を表示に含めない
- LINE は月200通まで。テストで本当に送るのは最小限にし、ふだんは `--dry-run`

## 進捗
- 2026-11-18：要件定義 → 実装 → テスト → GitHub 公開（m-tsuna/daily-fitness-paper-line）→ 記事投稿。11/19：タイトルを直訳に（PR #1）
- 試運転 11/19〜11/26：8日とも届いた（11/19 だけ手動）。定期実行は毎日4〜7時間遅れて 11〜15時に届くが、ご主人「このままでいい」→ 直さない。日本の論文は入れない（ご主人「いらない」）
- 11/26 振り返り（作業記録.md）：ご主人は毎日読み、11/19・11/25 が役立った。出た点 → PR #2（飛ばす判断・統計の言葉・英語のタイトル）マージ済み → 関連する別の研究を添える（PR #3、レビュー → マージ済み）。PubMed の間隔（429 対策）も入れた
- **12/27ごろ：関連する研究の1か月の振り返り**（声をかける）。Actions のログで添えた日数・見つからなかった日数を数え、ご主人に「別の研究から」を自分のトレーニング・お客さんへの説明に使ったか、ずれていた日はないかを聞く → 続けるか `config.RELATED_STUDY = False` にするかを本人が決める
- 次：11/27 朝の Actions のログを確かめる（`gh run list --workflow daily.yml -L 3`。やり方なしの日なら関連研究が付いたか）→ 振り返りの記事を新しく作る（本人が決定。11/18 の記事には追記しない）。直すときは Feature Branch（feature/xxx → PR → /code-review → 本人の OK → マージ）

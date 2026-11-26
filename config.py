"""設定値をまとめたファイル。

ここの言葉や数字を変えると、プログラムの動きが変わる。
決めた理由は 要件定義書.md の2章・4章にある。
"""

import os
from pathlib import Path

# ===== ファイルの場所 =====
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"          # 鍵のファイル（GitHub に載せない）
SENT_FILE = BASE_DIR / "sent.json"    # 送った論文の記録（同じ論文を2回送らないため）

# ===== 日付 =====
# GitHub Actions は世界の標準時（UTC）で動くので、日本時間に直して「今日」「曜日」を数える
TIMEZONE = "Asia/Tokyo"

# ===== 曜日ごとのテーマ（月曜=0 … 日曜=6） =====
# query は PubMed の検索の言葉。[tiab] は「タイトルか要旨に出てくる」という意味。OR は「または」
# steps を書いたテーマは、探す順番（期間・研究の種類で絞るか）をそのテーマだけ変える
TRAINING = '("resistance training"[tiab] OR "strength training"[tiab] OR "muscle hypertrophy"[tiab] OR "muscle strength"[tiab] OR "weight training"[tiab])'
TOPICS = {
    0: {"name": "トレーニング", "query": TRAINING},
    1: {"name": "ケガ・リハビリ", "query": '("sprain"[tiab] OR "muscle strain"[tiab] OR "low back pain"[tiab] OR "tendinopathy"[tiab] OR "sports injury"[tiab] OR "musculoskeletal injury"[tiab]) AND ("rehabilitation"[tiab] OR "exercise therapy"[tiab] OR "manual therapy"[tiab] OR "physiotherapy"[tiab]) NOT ("transcranial"[tiab] OR "telerehabilitation"[tiab])'},
    2: {"name": "栄養", "query": '("protein intake"[tiab] OR "protein supplementation"[tiab] OR "creatine"[tiab] OR "sports nutrition"[tiab] OR "dietary supplement"[tiab]) AND ("muscle"[tiab] OR "exercise"[tiab] OR "athletes"[tiab])'},
    # ボディビルは論文が少ない。直近30〜90日や「信頼性の高い研究」で絞ると、試験管の実験やステロイドの病気の報告ばかりになった
    # （2026-11-18 の試し）。トレーニング・食事・体組成の言葉と組み合わせ、1年分から関係の深い順に選ぶ（研究の種類では絞らない）
    3: {"name": "ボディビル", "query": '("bodybuilding"[tiab] OR "bodybuilder"[tiab] OR "bodybuilders"[tiab] OR "physique athletes"[tiab] OR "physique competition"[tiab] OR "contest preparation"[tiab] OR "peak week"[tiab]) AND ("training"[tiab] OR "diet"[tiab] OR "nutrition"[tiab] OR "body composition"[tiab] OR "carbohydrate"[tiab] OR "protein"[tiab] OR "hypertrophy"[tiab])',
        "steps": [(365, False)]},
    # 減量は、言葉だけだと肥満の薬（GLP-1 など）の論文ばかりになった（2026-11-18 の試し）。筋トレ・運動と組み合わせ、薬と手術は除く
    4: {"name": "減量", "query": '("weight loss"[tiab] OR "fat loss"[tiab] OR "energy restriction"[tiab] OR "caloric restriction"[tiab] OR "energy deficit"[tiab]) AND ("resistance training"[tiab] OR "resistance exercise"[tiab] OR "strength training"[tiab] OR "athletes"[tiab] OR "lean mass"[tiab] OR "fat-free mass"[tiab]) NOT ("GLP-1"[tiab] OR "semaglutide"[tiab] OR "tirzepatide"[tiab] OR "bariatric"[tiab] OR "cancer"[tiab] OR "diabetes"[tiab])',
        # 直近30日だと信頼性の高い研究が1本しか無かったので、90日まで広げて信頼性の高い研究を先に探す
        "steps": [(90, True), (30, False), (365, True), (90, False)]},
    # 「recovery」だけだと手術後の回復の論文ばかりになった（2026-11-18 の上位5本の確認）。運動のあとの回復に限る
    5: {"name": "コンディショニング・柔軟性", "query": '("stretching"[tiab] OR "foam rolling"[tiab] OR "flexibility training"[tiab] OR "post-exercise recovery"[tiab] OR "exercise-induced muscle damage"[tiab] OR "delayed onset muscle soreness"[tiab] OR "warm-up"[tiab] OR "range of motion"[tiab]) AND ("athletes"[tiab] OR "resistance training"[tiab] OR "healthy"[tiab] OR "trained"[tiab])'},
    6: {"name": "新しい論文から", "query": f'({TRAINING} OR "sports medicine"[tiab] OR "exercise physiology"[tiab] OR "bodybuilding"[tiab])'},
}

# ===== PubMed（論文のデータベース） =====
PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
PUBMED_TOOL = "daily-fitness-paper-line"   # PubMed に伝える「使っているツールの名前」（個人情報は送らない）
ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/"
# すべてのテーマに付ける条件：要旨がある・英語・動物だけの研究は除く
# 病気の治療・費用の研究は、検索の言葉が当てはまっても現場で使えないので除く（2026-11-18 の上位5本の確認で、がん・脳卒中・費用対効果が混ざった）
COMMON_FILTER = ('hasabstract AND english[la] NOT (animals[mh] NOT humans[mh])'
                 ' NOT ("cancer"[tiab] OR "tumor"[tiab] OR "stroke"[tiab] OR "critical illness"[tiab] OR "critically ill"[tiab]'
                 ' OR "cost-effectiveness"[tiab] OR "myositis"[tiab] OR "anorexia nervosa"[tiab] OR "depressive"[tiab]'
                 ' OR "NSCLC"[tiab] OR "carcinoma"[tiab] OR "lung disease"[tiab] OR "COPD"[tiab] OR "asthma"[tiab] OR "heart failure"[tiab]'
                 ' OR "kidney disease"[tiab] OR "dialysis"[tiab] OR "children"[tiab] OR "arthroplasty"[tiab])')
# 信頼性の高い研究の種類（先に探す）
STRONG_TYPES = '(randomized controlled trial[pt] OR meta-analysis[pt] OR systematic review[pt] OR clinical trial[pt])'
# 探す順番：(何日前までに載った論文か, 研究の種類で絞るか)
# 最近のものを優先し、見つからなければ期間を広げる（ボディビルは論文が少ないので、1年まで広げる）
SEARCH_STEPS = [(30, True), (30, False), (90, True), (90, False), (365, True), (365, False)]
SEARCH_MAX = 20          # 1回の検索で番号を取る本数
MAX_SUMMARIES = 3        # 「現場で使えない」論文を飛ばして、AI に要約を頼む本数の上限（AI の無料枠を使いすぎないため）
HTTP_TIMEOUT = 30        # 通信の返事を待つ秒数
PUBMED_INTERVAL = 0.4    # PubMed に続けて問い合わせるときにあける秒数（鍵なしは1秒に3回まで。2026-11-18 に連続で HTTP 429）

# 研究の種類を日本語にする表（LINE の「どんな実験か」に添える）
STUDY_TYPES_JA = {
    "Meta-Analysis": "メタ分析（たくさんの研究をまとめ直したもの）",
    "Systematic Review": "システマティックレビュー（研究を集めて整理したもの）",
    "Randomized Controlled Trial": "ランダム化比較試験（くじ引きで分けて比べた実験）",
    "Clinical Trial": "臨床試験",
    "Case Reports": "事例報告（1人〜数人の記録）",
    "Review": "総説（これまでの研究の解説）",
}

# ===== Gemini（AI） =====
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
# 上から順に試す。軽いモデルを先にした（無料枠では最新モデルが混みやすい。5-1-2② の記録）
# テストのために、環境変数 GEMINI_MODELS（カンマ区切り）で差し替えられる
GEMINI_MODELS = os.environ.get("GEMINI_MODELS", "gemini-flash-lite-latest,gemini-flash-latest").split(",")
GEMINI_RETRY_WAITS = [15, 30]   # 混雑（503）のとき、何秒待ってやり直すか
GEMINI_TIMEOUT = 120            # 1回の返事を待つ秒数

# ===== 関連する別の研究（今日の論文に具体的なやり方が書かれていない日だけ添える） =====
# 2026-11-26 から1か月試す（12/27ごろ、ご主人に聞いて続けるか決める）。止めるときは False にして push する（翌朝から元の形）
RELATED_STUDY = True
RELATED_DAYS = 365 * 5   # 何日前までに載った論文から探すか（対応策の研究は新しくなくてよいので、5年まで）
RELATED_MAX = 5          # AI に見せる候補の本数

# ===== LINE =====
# 一斉送信：公式アカウントの友だち全員に送る（友だちはご主人と確認用の本人だけ。相手の ID がいらない）
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"

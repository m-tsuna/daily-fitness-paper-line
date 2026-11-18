"""Gemini（Google の AI）に、論文の要旨を日本語で要約してもらう（通信する）。

返事は決まった形（JSON）で受け取る：タイトルの日本語訳・結論・実験の内容・現場での使い方（3つ）。
混雑（503）のときは少し待ってやり直し、駄目なら次のモデルへ。全部駄目なら None を返す
（呼ぶ側は英語のまま送らず、その回は送らない。予備の実行でもう一度試す）。
"""

import json
import time

import requests

import config

# やり直す価値のある返事：503＝混雑、500＝サーバーの一時的な不調、429＝短い時間に頼みすぎ
RETRY_STATUS = {429, 500, 503}
TIMEOUT = "時間切れ"

# 「使えない」と書くときの決まった文（無理にこじつけさせないため）
NOT_APPLICABLE = "この論文からは言えません"

PROMPT = f"""あなたは、柔道整復師でパーソナルトレーナー、自分もボディビルの大会に出ている日本人のために、
英語の論文の要旨を日本語で要約します。読む人は筋トレの知識はありますが、統計の専門家ではありません。

読みやすさ（いちばん大事）：
- 論文の言葉をそのまま訳さず、筋トレに詳しい同僚が口で説明するような、やさしい日本語にする
- 1文は40文字くらいまで。長くなるときは文を分ける
- 筋トレ・トレーナーの現場で使う用語（レジスタンストレーニング、1RM、ハムストリングス、PFC など）は、そのまま使ってよい
- 論文特有の硬い言葉は、普段の言葉にする（介入 → 取り組み、被験者 → 参加者、有意に → はっきり）
- 体の部位・靭帯・筋肉・治療法の名前は、柔道整復師が使う正しい日本語の医学用語にする。やさしく言い換えない（anterior talofibular ligament → 前距腓靭帯、calcaneofibular ligament → 踵腓靭帯、electroacupuncture → 電気鍼）
- どうしても専門用語を使うときは、すぐ後ろの（ ）で短く説明する（例：メタ分析（たくさんの実験をまとめ直した研究））
- 数字は「平均7.4kg多く伸びました」のように、何がどれだけ変わったかが分かる形にする
- 検査や点数の名前（〇〇スコアなど）は、（ ）で何を測るものかを添える
- 統計の指標（ICC・効果量・オッズ比など）は、名前より意味を書く（例：ICC 0.89 → 測る人が変わっても結果がよく一致しました（0.89。1に近いほど一致））
- 英語を無理に四字熟語や硬い言葉に訳さない。訳しにくい言葉は、やさしい日本語に元の英語を添える（例：心と体を一緒に使う運動（mind-body exercise））。要旨に無い具体例（種目名など）は足さない

守ること：
- 要旨に書いてあることだけを書く。数字・人数・期間は要旨にあるものだけを使い、無いものは書かない
- 専門用語は、トレーナーが普段使う日本語にする（例：hypertrophy → 筋肥大、1RM → 1RM（最大挙上重量））
- 「有意差」などの統計の言葉は使わず、「はっきりした差があった／差はなかった」のように書く
- 現場での使い方は、要旨の結果をもとに書く。効果が出た条件（期間・タイミングなど）があれば、それも使い方に入れる。結果を言いすぎず、そのまま当てはめられないときは「〜を考える参考になります」のように控えめに書く
- 研究の対象と違う人に当てはめるとき（健康な人の研究をケガ人に使う など）は、「健康な人の研究ですが」のように前置きする
- 要旨に無い一般的な助言（「安静にしてください」「医師に相談してください」など）は書かない
- 病気の薬・がん・動物の研究など、その用途に本当に関係ないときだけ、ほかの言葉を足さず「{NOT_APPLICABLE}」とだけ書く
- 文末は必ず「です」「ます」「ました」「でした」で終える（「〜である」「〜した」で終えない）。短い文にする

各項目：
- title_ja：内容がひと目で分かる日本語のタイトル（直訳でなくてよい。40文字以内。例「プロテインを足すと筋力はもっと伸びる？23の実験のまとめ」）
- conclusion：結論（2〜3文、120文字以内）
- results：結果。要旨の RESULTS（結果）に書いてある主な数字と、効果が出た条件（期間・飲むタイミング・対象など）を、
  「スクワットの重量が平均7.4kg多く伸びました」のように具体的な言葉で書く。条件で差が出ていれば必ず書く。
  「はっきりした差とまでは言えないが傾向があった」もの、一部の条件だけを分けて見た結果（サブグループ解析）は、「はっきり」と書かず「〜のときに主に見られました」「〜の傾向がありました」と書く。
  数字は、結論にかかわる大事なもの3つくらいまでにしぼる。結果の数字が無い論文（総説・解説など）は、主な内容を2〜3点書く（200文字以内）
- study：どんな実験か。対象（どんな人か）・人数・方法（何と何を比べたか）・期間を書く。要旨に書いていない項目は「明記されていません」「不明」などと書かず、その項目には触れない。研究を集めたものや解説（総説）なら、何件・何人の研究を集めたか、何についての解説かを書く（150文字以内）
- training：自分のトレーニングにどう使えるか（80文字以内）
- coaching：お客さんへの指導にどう使えるか（80文字以内）
- treatment：施術（柔道整復・ケガの手当てやリハビリ・痛みの評価）にどう使えるか（80文字以内）。
  ケガ・痛み・リハビリ・体の評価を調べた研究でなければ、無理に結びつけず「この論文からは言えません」と書く
  （例：健康な人の筋トレの量や筋力の伸びの研究から「ケガ予防に役立つ」「リハビリの計画に」とは書かない）
- useful：トレーニング・指導・施術の3つのうち、1つでも現場で役立つなら true、どれにも役立たないなら false

論文：
"""

FIELDS = ["title_ja", "conclusion", "study", "results", "training", "coaching", "treatment"]

SCHEMA = {
    "type": "object",
    "properties": {**{name: {"type": "string"} for name in FIELDS}, "useful": {"type": "boolean"}},
    "required": [*FIELDS, "useful"],
}

# 1回の実行の中で、一度駄目だったモデル（もう一度は試さず、時間を節約する）
unavailable = set()


def _post(api_key, model, prompt):
    """1つのモデルに1回だけ頼む。(HTTP の番号, 返事の文 または None) を返す。通信の失敗は (None, None)。"""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA},
    }
    try:
        r = requests.post(
            f"{config.GEMINI_API_URL}{model}:generateContent",
            headers={"x-goog-api-key": api_key},  # 鍵はヘッダーで送る（URL に入れない＝ログに出ない）
            json=body,
            timeout=config.GEMINI_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return TIMEOUT, None
    except requests.exceptions.RequestException:
        return None, None
    if r.status_code != 200:
        return r.status_code, None
    try:
        # 返事の形：candidates → [0] → content → parts → [最後] → text（JSON の文）
        return 200, r.json()["candidates"][0]["content"]["parts"][-1]["text"]
    except (ValueError, KeyError, IndexError):
        return 200, None


def check_summary(data):
    """返事を確かめて整える。足りない項目があれば None（英語のまま送らないため、送らない）。"""
    if not isinstance(data, dict):
        return None
    result = {name: str(data.get(name, "")).strip() for name in FIELDS}
    if not all(result.values()):
        return None
    # 役に立つかは、AI の「はい／いいえ」で受け取る（文の言い方は「言えません」「当てはまりません」などと揺れるため）
    result["useful"] = data.get("useful") is not False
    return result


def is_useful(summary):
    """3つの用途のどれかに使えるか（AI が「どれにも役立たない」と答えたら、送っても役に立たない）。"""
    return summary.get("useful", True)


def summarize(api_key, paper, log=print, sleep=time.sleep):
    """論文を日本語で要約して返す。全部のモデルで駄目なら None。

    log：途中経過を出す関数（GitHub Actions の記録に残る）
    sleep：待つ関数（テストでは待たないものに差し替える）
    """
    prompt = PROMPT + f"タイトル：{paper['title']}\n研究の種類：{', '.join(paper['types'])}\n要旨：\n{paper['abstract']}"
    for model in config.GEMINI_MODELS:
        model = model.strip()
        if not model or model in unavailable:
            continue
        for attempt in range(len(config.GEMINI_RETRY_WAITS) + 1):
            status, text = _post(api_key, model, prompt)
            if text is not None:
                try:
                    result = check_summary(json.loads(text))
                except ValueError:
                    result = None
                if result:
                    log(f"  Gemini（{model}）で要約できました")
                    return result
                log(f"  Gemini（{model}）の返事に足りない項目がありました")
                break  # 次のモデルへ
            if status in RETRY_STATUS and attempt < len(config.GEMINI_RETRY_WAITS):
                wait = config.GEMINI_RETRY_WAITS[attempt]
                log(f"  Gemini（{model}）が混んでいます（HTTP {status}）。{wait}秒待ってやり直します")
                sleep(wait)
                continue
            why = TIMEOUT if status == TIMEOUT else (f"HTTP {status}" if status else "通信の失敗")
            log(f"  Gemini（{model}）を使えませんでした（{why}）")
            unavailable.add(model)
            break  # 次のモデルへ
    return None

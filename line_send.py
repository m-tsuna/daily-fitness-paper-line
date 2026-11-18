"""LINE に1通送る（通信する）。

使う API：LINE Messaging API の一斉送信（POST /v2/bot/message/broadcast）
公式アカウントの友だち全員に届く。相手のユーザー ID はいらない。
無料プランは月200通まで（友だち1人に1通で1通と数える）。送った中身は API では読み返せない。
"""

import requests

import config


class LineError(Exception):
    """LINE に送れなかったときのエラー（利用者に見せる日本語のメッセージを持つ）。"""


# LINE の返事の番号を、「何が起きたか → どうすればよいか」の日本語に直す表
STATUS = {
    400: "送る文の形が正しくありません → 作った人に連絡してください",
    401: "LINE のトークンが正しくありません → LINE Developers で「チャネルアクセストークン（長期）」を確かめ、.env（GitHub では Secrets）の LINE_CHANNEL_ACCESS_TOKEN に貼り直してください",
    403: "このトークンでは送る許可がありません → Messaging API のチャネルのトークンか確かめてください",
    429: "今月の無料の送信数（200通）を使い切ったか、送る回数が多すぎます → 来月まで待つか、LINE Official Account Manager で送信数を確かめてください",
}

MAX_LENGTH = 5000  # LINE の1通の文字数の上限


def send(token, text):
    """文を1通、友だち全員に送る。送れなかったら LineError。"""
    try:
        r = requests.post(
            config.LINE_BROADCAST_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"type": "text", "text": text[:MAX_LENGTH]}]},
            timeout=config.HTTP_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        # e の中身には送り先の情報が入ることがあるので、種類の名前だけ出す
        raise LineError(f"LINE につながりませんでした（{type(e).__name__}） → インターネットの接続を確かめて、もう一度動かしてください")
    if r.status_code != 200:
        raise LineError(STATUS.get(r.status_code, f"LINE に送れませんでした（HTTP {r.status_code}） → 少し時間をおいて、もう一度動かしてください"))

"""LINE で送る文を組み立てる（通信しない）。"""

import config


def study_type_ja(types):
    """PubMed の研究の種類から、日本語の名前を1つ選ぶ（表の上にあるほど優先）。無ければ空。"""
    for name, ja in config.STUDY_TYPES_JA.items():
        if name in types:
            return ja
    return ""


def build(paper, summary, related=None):
    """論文の情報と要約から、LINE の文を作る。

    related：関連する別の研究（related.find の返り値）。あれば「現場での使い方」の後ろに、別の見出しで添える
    （今日の論文の中身と混ざらないように、「別の研究から」とはっきり分ける）
    """
    kind = study_type_ja(paper["types"])
    source = "・".join(x for x in [paper["journal"], paper["year"]] if x)
    lines = [
        f"【{summary['title_ja']}】",
        f"（{paper['title']}）",
        "",
        "■ 結論",
        summary["conclusion"],
        "",
        "■ どんな実験か",
    ]
    if kind:
        lines.append(f"研究の種類：{kind}")
    lines += [
        summary["study"],
        "",
        "■ 結果",
        summary["results"],
        "",
        "■ 現場での使い方",
        f"・トレーニング：{summary['training']}",
        f"・指導：{summary['coaching']}",
        f"・施術：{summary['treatment']}",
        "",
    ]
    if related:
        lines += [
            "■ 関連する別の研究から（参考）",
            related["text"],
            f"元の論文：{config.ARTICLE_URL}{related['pmid']}/",
            "",
        ]
    if source:
        lines.append(f"掲載：{source}")
    lines.append(f"元の論文：{config.ARTICLE_URL}{paper['pmid']}/")
    return "\n".join(lines)

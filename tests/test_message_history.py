"""message.py と history.py の単体テスト（通信しない）。"""
import history
import message

PAPER = {"pmid": "123", "title": "Original", "abstract": "", "journal": "Sports", "year": "2026",
         "types": ["Journal Article", "Randomized Controlled Trial"]}
SUMMARY = {"title_ja": "日本語の題", "conclusion": "結論", "study": "20人", "results": "7kg", "training": "a", "coaching": "b", "treatment": "c"}


def test_文はタイトルの日本語訳から始まり_リンクで終わる():
    text = message.build(PAPER, SUMMARY)
    lines = text.split("\n")
    assert lines[0] == "【日本語の題】"
    assert "研究の種類：ランダム化比較試験" in text
    assert "■ 結果\n7kg" in text
    assert "・施術：c" in text and "掲載：Sports・2026" in text
    assert lines[-1] == "元の論文：https://pubmed.ncbi.nlm.nih.gov/123/"


def test_記録_同じ日は送らない_飛ばした論文は送ったことにしない(tmp_path):
    path = tmp_path / "sent.json"
    records = history.load(path)
    assert records == []
    history.add(path, records, "2026-11-19", "栄養", PAPER, skipped=True)
    assert not history.sent_today(history.load(path), "2026-11-19")
    history.add(path, records, "2026-11-19", "栄養", dict(PAPER, pmid="456"))
    loaded = history.load(path)
    assert history.sent_today(loaded, "2026-11-19")
    assert not history.sent_today(loaded, "2026-11-20")
    assert history.sent_pmids(loaded) == {"123", "456"}

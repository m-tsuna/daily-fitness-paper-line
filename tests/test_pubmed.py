"""pubmed.py の単体テスト（通信しない）。"""
import config
import pubmed

XML = """<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>111</PMID><Article>
<Journal><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue><Title>Sports</Title></Journal>
<ArticleTitle>Effects of <i>creatine</i> on strength</ArticleTitle>
<Abstract><AbstractText Label="METHODS">Twenty men trained.</AbstractText><AbstractText Label="RESULTS">Strength rose.</AbstractText></Abstract>
<PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


def test_要旨を見出しごとにつなげ_斜体のタグも文字にする():
    [a] = pubmed.parse_articles(XML)
    assert a["pmid"] == "111"
    assert a["title"] == "Effects of creatine on strength"
    assert a["abstract"] == "METHODS: Twenty men trained.\nRESULTS: Strength rose."
    assert a["journal"] == "Sports" and a["year"] == "2026"
    assert a["types"] == ["Randomized Controlled Trial"]


def test_信頼性で絞るときだけ研究の種類の条件が付く():
    topic = {"query": "X"}
    assert config.STRONG_TYPES in pubmed.build_term(topic, True)
    assert config.STRONG_TYPES not in pubmed.build_term(topic, False)
    assert config.COMMON_FILTER in pubmed.build_term(topic, False)


def _paper(pmid, length=400):
    return {"pmid": pmid, "title": "t", "abstract": "a" * length, "journal": "", "year": "", "types": []}


def test_送った論文と短い要旨を飛ばし_見つからなければ期間を広げる(monkeypatch):
    calls = []

    def fake_search(term, days):
        calls.append(days)
        return ["1", "2", "3"] if days == 30 else ["4"]

    def fake_fetch(ids):
        return [_paper(i, 100 if i == "2" else 400) for i in ids]

    monkeypatch.setattr(pubmed, "search", fake_search)
    monkeypatch.setattr(pubmed, "fetch", fake_fetch)
    topic = {"query": "X", "steps": [(30, True), (90, True)]}
    got = [p["pmid"] for p in pubmed.candidates(topic, {"1"}, log=lambda *_: None)]
    assert got == ["3", "4"]   # 1は送った、2は要旨が短い
    assert calls == [30, 90]


def test_すべての曜日にテーマがある():
    assert sorted(config.TOPICS) == list(range(7))

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PUBLIC = [
    ROOT / "README.md",
    ROOT / "blog/index.html",
    ROOT / "environments/glyph/README.md",
]


def test_public_claims_avoid_retired_language() -> None:
    text = "\n".join(path.read_text() for path in PUBLIC)
    retired = [
        "fixing it with a dense partial-credit reward",
        "3-seed replication",
        "independent seeds",
        "every band CI includes zero",
        "every CI includes zero",
        "all-fail groups were ~10–20%",
        "1 confirmed violation among 12",
    ]
    for phrase in retired:
        assert phrase not in text, phrase


def test_public_claims_include_current_qualifiers() -> None:
    readme = (ROOT / "README.md").read_text()
    blog = (ROOT / "blog/index.html").read_text()
    hub = (ROOT / "environments/glyph/README.md").read_text()
    assert "p_family ≈ 0.15" in readme
    assert "every positive CI includes zero" in readme
    assert "1/7 dense groups and 5/8 compiler groups" in readme
    assert "family-cluster\n    sensitivity p ≈ 0.15" in blog
    assert "no quantitative\n    claim" in blog
    assert "1/7 dense groups and 5/8\n    compiler groups" in blog
    assert "52,696" in hub
    assert "Bubblewrap" in readme and "Bubblewrap" in hub

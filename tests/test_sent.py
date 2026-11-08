from pmail import sent


def test_draft_flag_means_not_sent():
    assert sent.status([b"\\Draft", b"\\Seen"]) == "draft"
    assert sent.status(("\\Draft",)) == "draft"


def test_no_draft_flag_means_sent():
    assert sent.status([b"\\Seen", b"\\Recent"]) == "sent"
    assert sent.status([]) == "sent"

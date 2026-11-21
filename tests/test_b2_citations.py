from agent.citations import extract_citation_ids, validate_citations


def test_valid_citations_are_distinct_and_in_order():
    text = "Try this [TKT-00412][TKT-03187]. Then do this [TKT-00412]."
    ids = ["TKT-00412", "TKT-03187"]
    assert extract_citation_ids(text) == ids
    assert validate_citations(text, ids, set(ids)) == []


def test_unknown_ids_in_text_and_reported_ids_are_detected():
    problems = validate_citations(
        "Try this [TKT-00001].", ["TKT-00002"], {"TKT-00412"},
    )
    assert problems == [
        "Unknown ticket IDs: TKT-00001, TKT-00002.",
        "Reported ticket IDs differ from the draft citations.",
    ]


def test_grounded_reply_requires_a_citation_and_holding_reply_does_not():
    text = "Thank you for the details. Our support team can review this."
    assert validate_citations(text, [], set()) == ["Draft has no bracketed ticket citation."]
    assert validate_citations(text, [], set(), status="INSUFFICIENT_EVIDENCE") == []


def test_a_larger_percentage_does_not_support_the_draft_amount():
    problems = validate_citations(
        "We can offer a 50% refund [TKT-00412].",
        ["TKT-00412"], {"TKT-00412"},
        precedent_answers=["Case 50 discussed a 150% threshold."],
    )
    assert problems == ["Figure is unsupported by precedent answers: 50%."]


def test_currency_and_percent_amounts_match_across_reply_languages():
    assert validate_citations(
        "Die Gebühr beträgt 9,50 Euro und der Rabatt beträgt 15 Prozent [TKT-00412].",
        ["TKT-00412"], {"TKT-00412"},
        precedent_answers=["A €9.50 fee applies with a 15% discount."],
    ) == []
    assert validate_citations(
        "The fee is €9.50 [TKT-00412].", ["TKT-00412"], {"TKT-00412"},
        precedent_answers=["The fee is $9.50."],
    ) == ["Figure is unsupported by precedent answers: €9.50."]

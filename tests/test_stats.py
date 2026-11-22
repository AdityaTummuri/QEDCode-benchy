from benchy.reports.stats import mcnemar_exact, paired, summarize_condition, wilson


def test_wilson_known_values():
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and round(hi, 3) == 0.278
    lo, hi = wilson(10, 10)
    assert round(lo, 3) == 0.722 and round(hi, 9) == 1.0
    assert wilson(0, 0) == (0.0, 1.0)


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert round(mcnemar_exact(0, 6), 4) == 0.0312  # 2 * 0.5**6
    assert mcnemar_exact(3, 3) == 1.0


def _att(task, rep, cond, resolved, **kw):
    base = dict(
        task_id=task,
        rep=rep,
        condition=cond,
        resolved=resolved,
        regression=False,
        status="done",
        seconds=1.0,
        model_calls=1,
        tokens_est=10,
        cost_usd_est=None,
    )
    return {**base, **kw}


def test_paired_counts_only_complete_pairs():
    atts = [
        _att("a", 1, "baseline", False),
        _att("a", 1, "qedcode", True),
        _att("b", 1, "baseline", True),
        _att("b", 1, "qedcode", True),
        _att("c", 1, "baseline", True),  # unpaired: ignored
    ]
    p = paired(atts)
    assert p["pairs"] == 2 and p["only_qedcode"] == 1 and p["only_baseline"] == 0
    assert p["both_resolved"] == 1 and p["difference"] == 0.5


def test_summary_counts_failures_in_the_denominator():
    atts = [
        _att("a", 1, "qedcode", True),
        _att("b", 1, "qedcode", False, status="timeout"),
        _att("c", 1, "qedcode", False, status="error", regression=True),
    ]
    s = summarize_condition(atts)
    assert s["attempts"] == 3 and s["resolved"] == 1 and s["resolution_rate"] == 0.3333
    assert s["timeouts"] == 1 and s["errors"] == 1 and s["regressions"] == 1
    assert s["cost_usd_est"] is None


def _graded(condition: str, resolved: bool, grade=None, status: str = "done") -> dict:
    return {"condition": condition, "resolved": resolved, "qed_grade": grade, "status": status}


def test_grade_honesty_counts_how_often_a_grade_was_right() -> None:
    from benchy.reports.stats import grade_honesty

    attempts = [
        _graded("qedcode", True, "A"),
        _graded("qedcode", True, "A"),
        _graded("qedcode", False, "A"),
        _graded("qedcode", False, "B"),
        _graded("qedcode", False, "C"),
        _graded("baseline", True),
    ]
    h = grade_honesty(attempts)
    assert h["A"]["graded"] == 3 and h["A"]["resolved"] == 2 and h["A"]["rate"] == 0.6667
    assert h["B"]["graded"] == 1 and h["B"]["resolved"] == 0
    assert 0 < h["A"]["ci95"][0] < h["A"]["rate"] < h["A"]["ci95"][1] <= 1


def test_silent_failures_are_wrong_changes_that_looked_done() -> None:
    from benchy.reports.stats import silent_failures

    attempts = [
        _graded("baseline", False),
        _graded("baseline", True),
        _graded("baseline", False, status="no_change"),
        _graded("qedcode", False, "B"),
        _graded("qedcode", False, "C"),
        _graded("qedcode", True, "A"),
    ]
    s = silent_failures(attempts)
    assert s["baseline"] == {"changes": 2, "wrong": 1, "silent": 1, "silent_rate": 0.5}
    assert s["qedcode"]["wrong"] == 2 and s["qedcode"]["silent"] == 1  # the C was flagged

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

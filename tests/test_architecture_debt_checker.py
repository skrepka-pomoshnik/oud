from collections import Counter

from tools.check_architecture_debt import _complexity_improvements, _complexity_regressions


def test_lower_complexity_is_an_improvement_not_a_regression() -> None:
    baseline = Counter({("module.py", "function", 10): 1})
    current = Counter({("module.py", "function", 8): 1})

    assert _complexity_regressions(current, baseline) == Counter()
    assert _complexity_improvements(current, baseline) == 1


def test_higher_or_duplicate_complexity_findings_are_regressions() -> None:
    baseline = Counter({("module.py", "function", 8): 1})
    current = Counter({("module.py", "function", 9): 1, ("module.py", "function", 8): 1})

    assert _complexity_regressions(current, baseline) == Counter(
        {
            ("module.py", "function", 9): 1,
            ("module.py", "function", 8): 1,
        },
    )

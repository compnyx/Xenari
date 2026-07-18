"""Property checks for productive grammar and hostile text boundaries."""

from hypothesis import given, settings
from hypothesis import strategies as st


@given(st.integers(min_value=0, max_value=(6**6) - 1))
@settings(max_examples=120, deadline=None)
def test_productive_base6_numbers_round_trip(xenari, value):
    rendered = xenari.speak(str(value), evidential="assumed")

    assert xenari.reverse(rendered) == str(value)


@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd", "Po", "Pd", "Zs"),
        ),
        max_size=100,
    )
)
@settings(max_examples=160, deadline=None)
def test_forward_translation_is_total_and_deterministic(xenari, source):
    first = xenari.speak(source, evidential="assumed")
    second = xenari.speak(source, evidential="assumed")

    assert isinstance(first, str)
    assert first
    assert second == first


@given(st.lists(st.sampled_from(["ra", "ka", "ta", "sa", "xo", "neq", "mex"]), max_size=24))
@settings(max_examples=120, deadline=None)
def test_candidate_linter_never_crashes_on_marker_sequences(xenari, tokens):
    report = xenari.lint_xenari_candidate(" ".join(tokens))

    assert report["schema"] == "xenari.llm_lint.v1"
    assert isinstance(report["ok"], bool)
    assert isinstance(report["errors"], list)

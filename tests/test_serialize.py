from jev_pilot.serialize import SerializerOptions, build_state
from jev_pilot.types import Option

OPTIONS = [Option(id="0", label="a 'Alpha report'"),
           Option(id="1", label="a 'Omega appendix'")]


def test_state_has_the_expected_sections():
    state = build_state(options=OPTIONS, url="https://example.test/index.html",
                        title="Index", text="Hello   world", history=["Back"])
    assert state.startswith("URL: https://example.test/index.html")
    assert "TITLE: Index" in state
    assert "VISIBLE PAGE TEXT: Hello world" in state
    assert "ACTIONS ALREADY TAKEN THIS EPISODE: Back" in state
    assert "CANDIDATE ACTIONS" in state
    assert "[0] a 'Alpha report'" in state
    assert "[1] a 'Omega appendix'" in state


def test_state_never_leaks_the_link_target():
    state = build_state(options=OPTIONS, url="https://example.test/index.html")
    assert "->" not in state
    assert ".html" not in state.replace("https://example.test/index.html", "")


def test_history_is_bounded_to_the_most_recent_items():
    history = [f"click {i}" for i in range(30)]
    state = build_state(options=OPTIONS, history=history,
                        opts=SerializerOptions(history_items=3))
    line = [l for l in state.splitlines() if l.startswith("ACTIONS ALREADY")][0]
    assert "click 27" in line and "click 28" in line and "click 29" in line
    assert "click 26" not in line


def test_no_history_reads_as_none():
    state = build_state(options=OPTIONS)
    assert "ACTIONS ALREADY TAKEN THIS EPISODE: (none)" in state


def test_truncation_is_reported_to_the_model():
    state = build_state(options=OPTIONS, matched_total=487)
    assert "2 of 487 candidates are shown" in state


def test_no_truncation_note_when_everything_fits():
    state = build_state(options=OPTIONS, matched_total=2)
    assert "are shown" not in state


def test_empty_candidate_list_is_explicit():
    state = build_state(options=[])
    assert "(none)" in state


def test_extra_lines_and_header_override():
    state = build_state(options=OPTIONS, extra_lines=["DISPLAY: 'Display is 8'"],
                        opts=SerializerOptions(header="CLICKABLE ELEMENTS"))
    assert "DISPLAY: 'Display is 8'" in state
    assert "CLICKABLE ELEMENTS (answer with one id from this list):" in state


def test_state_is_deterministic():
    args = dict(options=OPTIONS, url="https://example.test/", title="T", text="body",
                history=["a", "b"], matched_total=9)
    assert build_state(**args) == build_state(**args)


def test_text_is_clipped_with_a_visible_marker():
    state = build_state(options=OPTIONS, text="x" * 1000)
    line = [l for l in state.splitlines() if l.startswith("VISIBLE PAGE TEXT")][0]
    assert line.endswith("...")
    assert len(line) < 460

"""
Layout of a SequenceDiagram: lifelines under their headers in order, rows
descending one message at a time, activation bars spanning their rows, and
self-messages drawn as loops.
"""
import numpy as np
import pytest

from manim_software import Component
from manim_software import Message
from manim_software import SequenceDiagram


def _diagram():
    return SequenceDiagram(["browser", "gateway", "service"], spacing=2.0, row_height=0.5)


def test_lifelines_hang_under_headers_in_order():
    seq = _diagram()
    xs = [seq.get_lifeline_x(k) for k in ("browser", "gateway", "service")]
    assert xs == sorted(xs)
    assert np.allclose(np.diff(xs), 2.0)
    for header, line in zip(seq.headers, seq.lifelines):
        assert np.isclose(line.get_start()[0], header.get_center()[0])
        assert line.get_start()[1] <= header.get_bottom()[1] + 1e-6


def test_messages_descend_one_row_at_a_time():
    seq = _diagram()
    a = seq.message("browser", "gateway", "GET")
    b = seq.message("gateway", "service", "GET")
    c = seq.message("service", "gateway", "200", kind="reply")
    ys = [m.get_start()[1] for m in (a, b, c)]
    assert ys[0] > ys[1] > ys[2]
    assert np.allclose(np.diff(ys), -0.5)
    assert seq.row == 3


def test_message_runs_between_the_right_lifelines():
    seq = _diagram()
    arrow = seq.message("browser", "service", "hello")
    assert np.isclose(arrow.get_start()[0], seq.get_lifeline_x("browser"))
    assert np.isclose(arrow.get_end()[0], seq.get_lifeline_x("service"))
    back = seq.message("service", "browser", "hi", kind="reply")
    assert np.isclose(back.get_start()[0], seq.get_lifeline_x("service"))
    assert back.dashed


def test_self_message_is_a_loop_beside_the_lifeline():
    seq = _diagram()
    loop = seq.message("service", "service", "validate")
    x = seq.get_lifeline_x("service")
    anchors = np.array(loop.route.get_anchors())
    assert anchors[:, 0].max() > x + 0.3
    assert np.isclose(loop.get_start()[0], x)
    assert np.isclose(loop.get_end()[0], x)


def test_activation_bar_spans_rows():
    seq = _diagram()
    seq.message("browser", "gateway")
    seq.message("gateway", "service")
    seq.message("service", "gateway", kind="reply")
    bar = seq.activate("gateway", 0, 2)
    assert np.isclose(bar.get_center()[0], seq.get_lifeline_x("gateway"))
    assert bar.get_top()[1] > seq.row_y(0) > seq.row_y(2) > bar.get_bottom()[1]


def test_rows_grow_lifelines_when_exceeded():
    seq = SequenceDiagram(["a", "b"], n_rows=2, row_height=0.5)
    before = seq.lifelines[0].get_end()[1]
    for _ in range(4):
        seq.message("a", "b")
    after = seq.lifelines[0].get_end()[1]
    assert after < before
    assert after < seq.row_y(3)


def test_participants_accept_components_and_pairs():
    comp = Component("Order Service")
    seq = SequenceDiagram([("db", "Database"), comp])
    assert seq.keys == ["db", "Order Service"]
    assert seq.get_participant("db").label.original_text == "Database"
    assert seq.get_participant(comp) is seq.headers[1]


def test_message_from_record_and_bad_kind():
    seq = _diagram()
    arrow = seq.message_from(Message("browser", "gateway", "GET /x"))
    assert arrow.label is not None
    with pytest.raises(ValueError):
        Message("a", "b", kind="carrier-pigeon")

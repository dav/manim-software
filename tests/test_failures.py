"""
The failure vocabulary without rendering: where a dropped packet dies, how
retry backoff grows, what a timer and a timeout build, and how a circuit
breaker sits on its wire and changes state.
"""
import numpy as np
import pytest
from manim import LEFT
from manim import RED
from manim import RIGHT

from manim_software import CircuitBreaker
from manim_software import Component
from manim_software import Connector
from manim_software import Countdown
from manim_software import DiagramStyle
from manim_software import Drop
from manim_software import Message
from manim_software import Packet
from manim_software import ResetBreaker
from manim_software import Retry
from manim_software import SequenceDiagram
from manim_software import SystemDiagram
from manim_software import Timeout
from manim_software import Timer
from manim_software import TripBreaker
from manim_software import message_animation


def _wire():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([6, 0, 0])
    return a, b, Connector(a, b, buff=0.0)


# Drops


def test_drop_travels_part_of_the_wire_and_dies_there():
    _, _, conn = _wire()
    full = conn.get_travel_path()
    drop = Drop(Packet("x"), conn, at=0.6)
    assert np.allclose(drop.path.get_start(), full.get_start())
    assert np.isclose(drop.path.get_arc_length(), 0.6 * full.get_arc_length(), rtol=1e-2)
    assert np.allclose(drop.point, full.point_from_proportion(0.6), atol=1e-2)


def test_drop_reverse_starts_from_the_far_end():
    _, _, conn = _wire()
    drop = Drop(Packet(), conn, at=0.5, reverse=True)
    assert np.allclose(drop.path.get_start(), conn.get_travel_path().get_end())


def test_drop_at_a_breaker_dies_where_the_breaker_is():
    _, _, conn = _wire()
    breaker = CircuitBreaker(conn, proportion=0.3)
    forward = Drop(Packet(), conn, at=breaker)
    assert np.allclose(forward.point, breaker.get_point(), atol=1e-2)
    backward = Drop(Packet(), conn, at=breaker, reverse=True)
    assert np.isclose(backward.at, 0.7)
    assert np.allclose(backward.point, breaker.get_point(), atol=1e-2)


def test_drop_rejects_a_fraction_off_the_wire():
    _, _, conn = _wire()
    for at in (0.0, 1.5, -0.2):
        with pytest.raises(ValueError):
            Drop(Packet(), conn, at=at)


# Retries


def test_retry_backoff_grows_geometrically_and_caps():
    _, _, conn = _wire()
    packet = Packet("GET")
    retry = Retry(packet, conn, attempts=4, backoff=0.5, multiplier=2.0)
    assert retry.waits == [0.5, 1.0, 2.0]
    assert len(retry.attempt_packets) == 4
    assert retry.attempt_packets[-1] is packet
    assert all(p is not packet for p in retry.attempt_packets[:-1])
    capped = Retry(Packet(), conn, attempts=4, backoff=0.5, multiplier=2.0, max_backoff=1.2)
    assert capped.waits == [0.5, 1.0, 1.2]
    assert Retry(Packet(), conn, attempts=1).waits == []
    with pytest.raises(ValueError):
        Retry(Packet(), conn, attempts=0)


def test_retry_badges_sit_by_the_sender():
    a, b, conn = _wire()
    retry = Retry(Packet(), conn, attempts=2)
    for badge in retry.badges:
        assert badge.get_bottom()[1] >= a.get_top()[1] - 1e-6
        assert abs(badge.get_center()[0] - a.get_center()[0]) < 1.0
    backward = Retry(Packet(), conn, attempts=2, reverse=True)
    assert abs(backward.badges[0].get_center()[0] - b.get_center()[0]) < 1.0


# Timers


def test_timer_fraction_clamps_and_expiry_recolours():
    timer = Timer()
    assert timer.get_fraction() == 0.0
    timer.set_fraction(1.7)
    assert timer.get_fraction() == 1.0
    timer.set_fraction(-1.0)
    assert timer.get_fraction() == 0.0
    timer.expire()
    assert timer.get_fraction() == 1.0
    assert timer.pie.get_fill_color() == DiagramStyle().error_color


def test_countdown_sweeps_the_timer_and_can_expire_it():
    timer = Timer()
    countdown = Countdown(timer, expire_color=RED, run_time=1.0)
    countdown.begin()
    countdown.interpolate(0.5)
    assert np.isclose(timer.get_fraction(), 0.5)
    countdown.finish()
    assert timer.get_fraction() == 1.0
    assert timer.face.get_stroke_color() == RED


def test_transient_countdown_is_hidden_before_and_after():
    timer = Timer()
    countdown = Countdown(timer, transient=True, run_time=1.0)
    assert timer.face.get_stroke_opacity() == 0
    countdown.begin()
    assert timer.face.get_stroke_opacity() == 1
    countdown.finish()
    assert timer.face.get_stroke_opacity() == 0


def test_timeout_builds_beside_the_waiter_and_fits_a_run_time():
    comp = Component("Svc", width=2.0, height=1.0)
    timeout = Timeout(comp, wait=1.0)
    assert timeout.timer.get_left()[0] >= comp.get_right()[0] - 1e-6
    assert timeout.note.get_left()[0] >= timeout.timer.get_right()[0] - 1e-6
    assert np.isclose(timeout.run_time, 0.2 + 1.0 + 0.4 + 0.4)
    assert np.isclose(Timeout(comp, wait=1.0, run_time=1.0).run_time, 1.0)
    kept = Timeout(comp, wait=1.0, keep=True, label="")
    assert kept.note is None
    assert len(kept.marks) == 1
    assert np.isclose(kept.run_time, 0.2 + 1.0 + 0.4)
    # Marks leave one by one, never through a group the scene has not seen
    assert [anim.mobject for anim in timeout.dismiss().animations] == [timeout.timer, timeout.note]


# Circuit breakers


def test_breaker_sits_on_the_wire_above_it():
    _, _, conn = _wire()
    breaker = CircuitBreaker(conn, proportion=0.4)
    assert np.allclose(breaker.get_point(), conn.get_point(0.4), atol=1e-6)
    assert np.allclose(breaker.housing.get_center(), breaker.get_point(), atol=1e-6)
    assert breaker.z_index > conn.route.z_index
    assert np.allclose(breaker.tangent, RIGHT)


def test_breaker_states_move_the_lever_and_recolour():
    _, _, conn = _wire()
    style = DiagramStyle()
    breaker = CircuitBreaker(conn, proportion=0.5)
    assert breaker.is_closed()
    assert np.allclose(breaker.lever.get_end(), breaker.right, atol=1e-6)
    assert breaker.lever.get_stroke_color() == style.edge_color

    breaker.set_state("open")
    assert not breaker.is_closed()
    assert breaker.lever.get_end()[1] > breaker.left[1] + 0.2
    assert breaker.lever.get_stroke_color() == style.error_color
    assert breaker.housing.get_stroke_color() == style.error_color

    breaker.set_state("half_open")
    assert 0 < breaker.lever.get_end()[1] - breaker.left[1] < breaker.size * np.sin(0.9)
    assert breaker.lever.get_stroke_color() == style.warning_color

    with pytest.raises(KeyError):
        breaker.set_state("ajar")


def test_breaker_follows_the_wire_direction():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([0, -5, 0])
    breaker = CircuitBreaker(Connector(a, b, buff=0.0), proportion=0.5)
    assert np.allclose(np.abs(breaker.tangent), [0, 1, 0], atol=1e-6)
    assert np.allclose(breaker.get_point()[0], 0.0, atol=1e-6)


def test_trip_and_reset_apply_their_state_when_run():
    _, _, conn = _wire()
    breaker = CircuitBreaker(conn)
    trip = TripBreaker(breaker)
    trip.begin()
    trip.interpolate(1.0)
    trip.finish()
    assert breaker.state == "open"
    reset = ResetBreaker(breaker)
    reset.begin()
    reset.interpolate(1.0)
    reset.finish()
    assert breaker.state == "closed"


# Sequence diagram kinds


def test_lost_message_stops_short_with_a_mark():
    seq = SequenceDiagram(["a", "b"], spacing=2.0)
    lost = seq.message("a", "b", "GET", kind="lost")
    assert np.isclose(lost.get_end()[0] - lost.get_start()[0], 0.7 * 2.0, atol=1e-2)
    assert lost.mark is not None
    assert np.allclose(lost.mark.get_center(), lost.get_end(), atol=1e-6)
    with pytest.raises(ValueError):
        Message("a", "b", kind="vanished")


def test_timeout_message_is_a_self_loop_at_the_source():
    seq = SequenceDiagram(["a", "b"], spacing=2.0)
    loop = seq.message("a", "b", kind="timeout")
    x = seq.get_lifeline_x("a")
    assert np.isclose(loop.get_start()[0], x, atol=1e-6)
    assert np.isclose(loop.get_end()[0], x, atol=1e-6)
    assert loop.label_text.original_text == "timeout"
    assert loop.route.get_stroke_color() == DiagramStyle().warning_color


def test_message_animation_uses_drop_and_timeout_in_the_system_view():
    system = SystemDiagram()
    system.add_component("a", Component("A", width=2.0, height=1.0))
    system.add_component("b", Component("B", width=2.0, height=1.0).shift(5 * RIGHT))
    system.connect("a", "b")
    lost = message_animation(Message("a", "b", "GET", kind="lost"), system)
    assert any(isinstance(anim, Drop) for anim in lost.animations)
    waited = message_animation(Message("a", "a", kind="timeout"), system)
    assert any(isinstance(anim, Timeout) for anim in waited.animations)
    reply = message_animation(Message("b", "a", "rows", kind="reply"), system)
    assert not any(isinstance(anim, (Drop, Timeout)) for anim in reply.animations)

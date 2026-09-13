"""
Wire-label placement without rendering: a clear label stays where it was,
one over a box moves off it, one under a crossing wire or on a container
frame moves aside when it can, and labels placed in turn avoid each other.
"""
import numpy as np
from manim import DOWN
from manim import LEFT
from manim import RIGHT
from manim import UP

from manim_software import Component
from manim_software import Connector
from manim_software import Container
from manim_software import SystemDiagram
from manim_software import label_candidates
from manim_software import place_labels
from manim_software.layout import _overlap_area
from manim_software.layout import _piece_rects
from manim_software.layout import _rect


def _wire(label="HTTPS", y=0.0, **kwargs):
    a = Component("A", width=2.0, height=1.0).move_to([0, y, 0])
    b = Component("B", width=2.0, height=1.0).move_to([6, y, 0])
    return a, b, Connector(a, b, label=label, buff=0.0, **kwargs)


def _clear_of(label, mob, margin=0.05):
    """No drawn part of ``mob`` under the label (its bounding box may still be, e.g. a packet's halo)."""
    rect = _rect(label, margin)
    return all(_overlap_area(rect, piece) == 0 for piece in _piece_rects(mob))


def test_candidates_start_on_the_wire_then_beside_it():
    _, _, conn = _wire()
    candidates = label_candidates(conn)
    assert candidates[0] == (0.5, None)
    assert np.allclose(candidates[1][1], UP)
    assert np.allclose(candidates[2][1], DOWN)
    assert len(candidates) == 3 * 7


def test_clear_label_stays_put():
    a, b, conn = _wire()
    chosen = place_labels([conn], obstacles=[a, b])
    assert chosen[conn] == (0.5, None)
    assert np.allclose(conn.label.get_center(), conn.get_point(0.5), atol=1e-3)


def test_label_moves_off_a_box_in_its_way():
    a, b, conn = _wire()
    blocker = Component("C", width=1.5, height=0.8).move_to([3, 0.15, 0])
    chosen = place_labels([conn], obstacles=[a, b, blocker])
    assert chosen[conn] != (0.5, None)
    assert _clear_of(conn.label, blocker)
    assert _clear_of(conn.label, a) and _clear_of(conn.label, b)


def test_label_avoids_a_crossing_wire_when_it_can():
    a, b, conn = _wire()
    top = Component("T", width=1.0, height=0.6).move_to([3, 2.5, 0])
    bottom = Component("U", width=1.0, height=0.6).move_to([3, -2.5, 0])
    crossing = Connector(top, bottom, buff=0.0)
    place_labels([conn, crossing], obstacles=[a, b, top, bottom])
    rect = _rect(conn.label, 0.05)
    xs = [crossing.get_travel_path().point_from_proportion(t)[0] for t in np.linspace(0, 1, 40)]
    assert all(not (rect[0] <= x <= rect[2]) for x in xs) or rect[3] < -0.1 or rect[1] > 0.1


def test_label_keeps_off_a_container_frame():
    a, b, conn = _wire()
    box = Container(b, buff=0.5)          # its left edge cuts across the wire's middle region
    frame_x = box.frame.get_left()[0]
    # Nudge so the default spot straddles the frame edge
    shift = frame_x - conn.get_point(0.5)[0]
    for mob in (a, b):
        mob.shift(-shift * RIGHT)
    conn.reroute()
    box.refit()
    chosen = place_labels([conn], obstacles=[a, b], frames=[box.frame])
    rect = _rect(conn.label, 0.05)
    frame = _rect(box.frame)
    assert not (rect[0] < frame[0] < rect[2]), chosen[conn]


def test_labels_placed_in_turn_avoid_each_other():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([6, 0, 0])
    request = Connector(a, b, offset=-0.15, label="request", buff=0.0)
    reply = Connector(a, b, offset=0.15, label="reply", buff=0.0, tip="start", dashed=True)
    place_labels([request, reply], obstacles=[a, b])
    assert _overlap_area(_rect(request.label, 0.05), _rect(reply.label)) == 0


def test_system_resolve_labels_uses_its_registry():
    system = SystemDiagram()
    a = system.add_component("a", Component("A", width=2.0, height=1.0))
    b = system.add_component("b", Component("B", width=2.0, height=1.0).shift(6 * RIGHT))
    c = system.add_component("c", Component("Blocker", width=1.6, height=0.8).shift(3 * RIGHT + 0.1 * UP))
    conn = system.connect("a", "b", label="HTTPS")
    assert system.resolve_labels() is system
    assert _clear_of(conn.label, c)
    assert conn.label.get_center()[0] > a.get_right()[0] and conn.label.get_center()[0] < b.get_left()[0]


def test_move_label_switches_between_on_wire_and_beside():
    _, _, conn = _wire()
    conn.move_label(0.3, UP)
    point = conn.get_point(0.3)
    assert conn.label.get_bottom()[1] > point[1]
    assert np.isclose(conn.label.get_center()[0], point[0], atol=1e-3)
    assert len(conn.label) == 1                      # no background patch beside the wire
    conn.move_label(0.5, None)
    assert np.allclose(conn.label.get_center(), conn.get_point(0.5), atol=1e-3)
    assert len(conn.label) == 2                      # background patch is back
    assert conn.label_text.get_stroke_width(background=True) == 0


def test_resolve_labels_takes_extra_obstacles():
    from manim_software import Packet
    system = SystemDiagram()
    system.add_component("a", Component("A", width=2.0, height=1.0))
    system.add_component("b", Component("B", width=2.0, height=1.0).shift(6 * RIGHT))
    conn = system.connect("a", "b", label="gRPC")
    parked = Packet("GET /orders").move_to(conn.get_point(0.5))
    system.resolve_labels(obstacles=[parked])
    assert _clear_of(conn.label, parked)

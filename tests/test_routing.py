"""
Geometry of the layer that can be checked without rendering: where ports
sit on a component, the corners an orthogonal route turns, how corners get
rounded, and where a tipped route ends.
"""
import numpy as np
import pytest
from manim import DOWN, LEFT, RIGHT, UP

from manim_software import Component
from manim_software import Connector
from manim_software import Route
from manim_software.connectors import _orthogonal_waypoints
from manim_software.connectors import _round_open_corners
from manim_software.connectors import length_alpha_to_curve_alpha


def _axis_aligned(points):
    for a, b in zip(points, points[1:]):
        d = b - a
        assert np.isclose(d[0], 0) or np.isclose(d[1], 0), f"segment {a}->{b} is not axis aligned"


def test_ports_lie_on_box_edges():
    comp = Component("Svc", width=2.0, height=1.0)
    comp.move_to([1.0, 2.0, 0.0])
    assert np.allclose(comp.get_port(RIGHT), [2.0, 2.0, 0.0])
    assert np.allclose(comp.get_port(LEFT), [0.0, 2.0, 0.0])
    assert np.allclose(comp.get_port(UP), [1.0, 2.5, 0.0])
    assert np.allclose(comp.get_port(DOWN), [1.0, 1.5, 0.0])
    # offset slides along the edge, not off it
    assert np.allclose(comp.get_port(RIGHT, offset=0.5), [2.0, 2.25, 0.0])
    assert np.allclose(comp.get_port(UP, offset=-1.0), [0.0, 2.5, 0.0])


def test_port_toward_picks_dominant_axis():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([5, 0.5, 0])
    assert np.allclose(a.get_port_toward(b), a.get_port(RIGHT))
    assert np.allclose(b.get_port_toward(a), b.get_port(LEFT))
    c = Component("C", width=2.0, height=1.0).move_to([0.2, 4, 0])
    assert np.allclose(a.get_port_toward(c), a.get_port(UP))


def test_orthogonal_waypoints_facing_horizontal_ports():
    pts = _orthogonal_waypoints([0, 0, 0], RIGHT, [4, 2, 0], LEFT, stub=0.5)
    assert np.allclose(pts[0], [0, 0, 0])
    assert np.allclose(pts[-1], [4, 2, 0])
    _axis_aligned(pts)
    assert len(pts) == 4
    assert np.isclose(pts[1][0], 2.0) and np.isclose(pts[2][0], 2.0)
    for a, b in zip(pts, pts[1:]):
        assert np.linalg.norm(b - a) > 1e-6


def test_orthogonal_waypoints_collinear_collapse_to_a_line():
    pts = _orthogonal_waypoints([0, 0, 0], RIGHT, [4, 0, 0], LEFT)
    assert len(pts) == 2


def test_orthogonal_waypoints_mixed_ports_turn_one_corner():
    pts = _orthogonal_waypoints([0, 0, 0], RIGHT, [3, 3, 0], DOWN, stub=0.4)
    _axis_aligned(pts)
    assert len(pts) == 3
    assert np.allclose(pts[1], [3, 0, 0])
    pts = _orthogonal_waypoints([0, 0, 0], UP, [3, 3, 0], LEFT, stub=0.4)
    assert np.allclose(pts[1], [0, 3, 0])


def test_round_open_corners_keeps_endpoints_and_shortens_path():
    corners = [[0, 0, 0], [2, 0, 0], [2, 2, 0]]
    path = _round_open_corners(corners, radius=0.3)
    assert np.allclose(path.get_start(), corners[0])
    assert np.allclose(path.get_end(), corners[-1])
    sharp = _round_open_corners(corners, radius=0.0)
    assert path.get_arc_length() < sharp.get_arc_length()
    assert np.isclose(sharp.get_arc_length(), 4.0, atol=1e-3)


def test_round_open_corners_clamps_radius_to_short_segments():
    corners = [[0, 0, 0], [0.2, 0, 0], [0.2, 0.2, 0], [5, 0.2, 0]]
    path = _round_open_corners(corners, radius=10.0)
    assert np.allclose(path.get_start(), corners[0])
    assert np.allclose(path.get_end(), corners[-1])
    assert np.isfinite(path.points).all()


def test_length_alpha_maps_arc_length_to_curve_count():
    path = _round_open_corners([[0, 0, 0], [4, 0, 0], [4, 1, 0]], radius=0.0)
    # Two curves of length 4 and 1: the midpoint by length is 40% into curve 0
    assert np.isclose(length_alpha_to_curve_alpha(path, 0.5), 0.5 * (2.5 / 4))
    assert length_alpha_to_curve_alpha(path, 0.0) == 0.0
    assert length_alpha_to_curve_alpha(path, 1.0) == 1.0


def test_route_tip_ends_at_original_endpoint():
    route = Route([[0, 0, 0], [3, 0, 0]], tip_length=0.25)
    route.add_tip()
    assert np.allclose(route.get_end(), [3, 0, 0])
    # The stroke stops at the tip's base, one tip length short
    assert np.isclose(route.points[-1][0], 3 - 0.25, atol=1e-2)


def test_route_tip_on_polyline_trims_by_arc_length():
    route = Route([[0, 0, 0], [2, 0, 0], [2, 3, 0]], corner_radius=0.2, tip_length=0.25)
    route.add_tip()
    assert np.allclose(route.get_end(), [2, 3, 0])
    last = route.points[-1]
    assert np.isclose(last[0], 2.0, atol=1e-6)
    assert np.isclose(last[1], 3 - 0.25, atol=2e-2)


def test_connector_between_components_starts_and_ends_at_ports():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([5, 0, 0])
    conn = Connector(a, b, buff=0.0)
    assert np.allclose(conn.get_start(), a.get_port(RIGHT))
    assert np.allclose(conn.get_end(), b.get_port(LEFT))
    reverse = conn.get_travel_path(reverse=True)
    assert np.allclose(reverse.get_start(), conn.get_travel_path().get_end())


def test_connector_orthogonal_route_is_axis_aligned():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([5, 3, 0])
    conn = Connector(a, b, route="orthogonal", corner_radius=0.0, buff=0.0)
    _axis_aligned(np.array(conn.route.get_anchors()))


def test_connector_rejects_unknown_route():
    a = Component("A")
    b = Component("B").shift(4 * RIGHT)
    with pytest.raises(ValueError):
        Connector(a, b, route="diagonal")


def test_connector_label_sits_on_wire():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([6, 0, 0])
    conn = Connector(a, b, label="HTTPS", buff=0.0)
    assert np.allclose(conn.label.get_center(), conn.get_point(0.5), atol=1e-3)


def test_dashed_connector_hides_solid_route_but_keeps_it_for_travel():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([6, 0, 0])
    conn = Connector(a, b, dashed=True)
    assert conn.route.get_stroke_opacity() == 0
    assert len(conn.dashes.submobjects) > 2
    assert np.allclose(conn.get_point(0.0), conn.get_start())


def test_reroute_follows_moved_endpoint():
    a = Component("A", width=2.0, height=1.0).move_to([0, 0, 0])
    b = Component("B", width=2.0, height=1.0).move_to([5, 0, 0])
    conn = Connector(a, b, buff=0.0)
    b.shift(2 * UP)
    conn.reroute()
    assert np.allclose(conn.get_end(), b.get_port(LEFT))


def test_connector_accepts_a_plain_mobject_as_an_endpoint():
    """
    manim's Mobject.__getattr__ fabricates an attribute for any name, so
    hasattr(mob, "get_port") is True for every mobject. Probing the instance
    sent every endpoint down the Component branch and raised
    "getter() takes 1 positional argument but 3 were given" for anything else.
    """
    from manim import RoundedRectangle

    from manim_software import Component, Connector

    component = Component("A")
    plain = RoundedRectangle(width=2.0, height=1.0).shift(4 * RIGHT)

    connector = Connector(component, plain)
    assert len(connector.route.points) > 0

    # The plain end must land on its bounding box, not at its centre.
    assert connector.route.get_end()[0] < plain.get_center()[0]

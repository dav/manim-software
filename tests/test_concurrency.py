"""
Fan-out, fan-in and queues without rendering: one packet copy per wire, the
merged reply where the replies meet, queue depth, colours and geometry, and
what Enqueue and Dequeue do to a queue when they run.
"""
import numpy as np
import pytest
from manim import DOWN
from manim import LEFT
from manim import RIGHT

from manim_software import Component
from manim_software import Connector
from manim_software import Dequeue
from manim_software import DiagramStyle
from manim_software import Enqueue
from manim_software import FanIn
from manim_software import FanOut
from manim_software import MessageQueue
from manim_software import Packet


def _hub():
    hub = Component("Hub", width=2.0, height=1.0).move_to([0, 0, 0])
    spokes = [Component(f"S{i}", width=2.0, height=1.0).move_to([5, 2 - 2 * i, 0]) for i in range(3)]
    conns = [Connector(hub, spoke, buff=0.0) for spoke in spokes]
    return hub, spokes, conns


def test_fan_out_sends_a_copy_along_every_wire():
    _, _, conns = _hub()
    packet = Packet("q")
    fan = FanOut(packet, conns, lag_ratio=0.1)
    assert len(fan.packets) == 3
    assert len(fan.animations) == 3
    assert len({id(p) for p in fan.packets}) == 3
    assert all(p is not packet for p in fan.packets)
    with pytest.raises(ValueError):
        FanOut(packet, [])


def test_fan_in_meets_at_the_hub_with_a_merged_reply():
    hub, _, conns = _hub()
    fan = FanIn(Packet("ok"), conns, merged="200 OK")
    assert len(fan.packets) == 3
    assert isinstance(fan.merged, Packet)
    assert np.allclose(fan.merged.get_center(), conns[0].get_travel_path(reverse=True).get_end(), atol=1e-6)
    assert np.allclose(fan.meeting_point, hub.get_port(RIGHT), atol=1e-6)
    elsewhere = FanIn([Packet(), Packet(), Packet()], conns, merged=Packet("x"), merged_at=[1, 1, 0])
    assert np.allclose(elsewhere.merged.get_center(), [1, 1, 0])
    with pytest.raises(ValueError):
        FanIn([Packet()], conns)


def test_queue_depth_clamps_and_recolours_with_load():
    style = DiagramStyle()
    queue = MessageQueue(capacity=4, warn_at=0.75)
    queue.set_depth(9)
    assert queue.depth == 4 and queue.is_full()
    assert queue.item_color() == style.error_color
    queue.set_depth(3)
    assert queue.item_color() == style.warning_color
    queue.set_depth(1)
    assert queue.item_color() == style.packet_color
    assert queue.items[0].get_fill_opacity() == 1.0
    assert queue.items[1].get_fill_opacity() == 0.0
    assert queue.count.original_text == "1/4"
    queue.dequeue(5)
    assert queue.depth == 0 and queue.is_empty()
    queue.enqueue(2)
    assert queue.depth == 2
    with pytest.raises(ValueError):
        MessageQueue(capacity=0)


def test_queue_slots_run_in_its_direction_and_wires_hug_the_slots():
    queue = MessageQueue(capacity=3, direction=RIGHT, label="jobs")
    xs = [queue.get_slot_point(i)[0] for i in range(3)]
    assert xs == sorted(xs)
    assert queue.get_head_point()[0] < queue.slots.get_left()[0]
    assert queue.get_tail_point()[0] > queue.slots.get_right()[0]
    assert np.isclose(queue.get_port(LEFT)[0], queue.slots.get_left()[0])
    assert queue.label.get_bottom()[1] >= queue.slots.get_top()[1] - 1e-6

    producer = Component("P", width=2.0, height=1.0).move_to([-5, 0, 0])
    wire = Connector(producer, queue, buff=0.0)
    assert np.allclose(wire.get_end(), queue.get_port(LEFT), atol=1e-6)

    down = MessageQueue(capacity=3, direction=DOWN)
    ys = [down.get_slot_point(i)[1] for i in range(3)]
    assert ys == sorted(ys, reverse=True)


def _run(anim, upto=1.0):
    """Step an animation the way a scene would: begin, a few frames, finish."""
    anim.begin()
    for alpha in (0.1, 0.5, 0.9):
        if alpha <= upto:
            anim.interpolate(alpha)
    if upto >= 1.0:
        anim.finish()


def test_enqueue_lands_in_the_next_slot_and_counts_as_it_lands():
    queue = MessageQueue(capacity=2)
    first = Packet()
    enqueue = Enqueue(queue, first, from_point=[-3, 0, 0])
    assert queue in enqueue.mobject.get_family()      # so the renderer redraws it
    enqueue.begin()
    enqueue.interpolate(0.1)
    assert np.allclose(enqueue.origin, [-3, 0, 0])
    assert np.allclose(enqueue.target, queue.get_slot_point(0))
    assert queue.depth == 0
    enqueue.interpolate(0.9)
    assert queue.depth == 1                            # landed before the very end
    enqueue.finish()
    assert queue.depth == 1
    assert np.allclose(first.get_center(), queue.get_slot_point(0), atol=1e-6)


def test_enqueue_decides_when_it_starts_not_when_it_is_built():
    queue = MessageQueue(capacity=2)
    late = Enqueue(queue, Packet(), from_point=[-3, 0, 0])
    late.begin()                                       # a LaggedStart begins everything up front
    queue.enqueue(1)                                   # ...then earlier arrivals land
    late.interpolate(0.1)
    assert np.allclose(late.target, queue.get_slot_point(1))
    _run(late)
    assert queue.depth == 2

    rejected = Enqueue(queue, Packet(), from_point=[-3, 0, 0])
    _run(rejected, upto=0.5)
    assert not rejected.accepted
    assert np.allclose(rejected.target, queue.get_tail_point())
    rejected.interpolate(0.9)
    rejected.finish()
    assert queue.depth == 2


def test_enqueue_from_a_component_starts_at_its_port():
    queue = MessageQueue(capacity=2).move_to([3, 0, 0])
    producer = Component("P", width=2.0, height=1.0).move_to([-3, 0, 0])
    enqueue = Enqueue(queue, Packet(), from_point=producer)
    enqueue.begin()
    enqueue.interpolate(0.1)
    assert np.allclose(enqueue.origin, producer.get_port(RIGHT), atol=1e-6)


def test_dequeue_drops_the_depth_and_ignores_an_empty_queue():
    queue = MessageQueue(capacity=3, depth=2)
    dequeue = Dequeue(queue, to=[5, 0, 0])
    assert queue in dequeue.mobject.get_family()
    dequeue.begin()
    assert queue.depth == 2                            # nothing happens until it really starts
    dequeue.interpolate(0.1)
    assert queue.depth == 1
    assert dequeue.active
    dequeue.finish()
    assert np.allclose(dequeue.packet.get_center(), [5, 0, 0], atol=1e-6)

    empty = MessageQueue(capacity=3)
    idle = Dequeue(empty)
    _run(idle)
    assert not idle.active
    assert empty.depth == 0


def test_lagged_enqueues_fill_then_reject():
    from manim import LaggedStart
    queue = MessageQueue(capacity=3)
    arrivals = LaggedStart(*(Enqueue(queue, Packet(), from_point=[-3, 0, 0], run_time=0.5) for _ in range(5)), lag_ratio=0.6)
    arrivals.begin()
    steps = int(arrivals.run_time * 30) + 1
    for i in range(1, steps + 1):
        arrivals.interpolate(min(1.0, i / steps))
    arrivals.finish()
    assert queue.depth == 3
    assert [a.accepted for a in arrivals.animations] == [True, True, True, False, False]

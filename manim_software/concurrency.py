"""
Several things at once: a request fanning out to many services and their
answers fanning back in, and queues whose depth shows load building up.

``FanOut`` and ``FanIn`` are groups of ``Send``s over copies of one packet.
``MessageQueue`` is a row of slots that fill; ``Enqueue`` and ``Dequeue``
move packets in and out and change the depth as they land, so a
``LaggedStart`` of ``Enqueue``s outpacing ``Dequeue``s is a queue under load.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from manim import DOWN
from manim import RIGHT
from manim import SMALL_BUFF
from manim import UP
from manim import Animation
from manim import AnimationGroup
from manim import Mobject
from manim import Square
from manim import VGroup
from manim import smooth
from manim.utils.space_ops import normalize

from manim_software.components import bounding_box_point
from manim_software.connectors import Connector
from manim_software.failures import _cross
from manim_software.packets import FadeInAfter
from manim_software.packets import Packet
from manim_software.packets import Send
from manim_software.packets import _family_opacities
from manim_software.packets import _set_family_opacity
from manim_software.packets import _travel_path
from manim_software.style import Z_NODE
from manim_software.style import _backstroke
from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Callable
    from typing import Self
    from typing import Sequence

    from manim.typing import ManimColor
    from manim.typing import Point3D
    from manim.typing import Vector3D

    from manim_software.style import DiagramStyle


Hop = "Connector | tuple[Connector, bool]"


def _normalize_hops(hops: Sequence, default_reverse: bool = False) -> list[tuple[Connector, bool]]:
    return [hop if isinstance(hop, tuple) else (hop, default_reverse) for hop in hops]


# Fan-out / fan-in


class FanOut(AnimationGroup):
    """
    One request becoming many: a copy of ``packet`` leaves along every
    connector (``(connector, reverse)`` pairs allowed), all together or
    staggered by ``lag_ratio``. The copies are ``self.packets``, in connector
    order, ready for a ``FanIn`` of the replies.
    """
    def __init__(
        self,
        packet: Packet,
        connectors: Sequence,
        lag_ratio: float = 0.0,
        run_time: float = 1.0,
        fade_out: bool = True,
        **send_kwargs
    ):
        hops = _normalize_hops(connectors)
        if not hops:
            raise ValueError("FanOut needs at least one connector")
        self.packets = [packet.copy() for _ in hops]
        anims = [
            Send(copy, connector, reverse=reverse, run_time=run_time, fade_out=fade_out, **send_kwargs)
            for copy, (connector, reverse) in zip(self.packets, hops)
        ]
        super().__init__(*anims, lag_ratio=lag_ratio)


class FanIn(AnimationGroup):
    """
    Many replies becoming one. ``packets`` (one per connector, or a single
    packet to copy) travel back along their connectors (``reverse`` by
    default, as replies do) and meet at the far end. ``merged`` is the
    combined result that fades in where they meet: a ``Packet``, or a label
    for a pill in the reply colour; it stays for the caller to send on.
    """
    def __init__(
        self,
        packets: Packet | Sequence[Packet],
        connectors: Sequence,
        merged: Packet | str | None = None,
        merged_at: Point3D | None = None,
        reverse: bool = True,
        lag_ratio: float = 0.0,
        run_time: float = 1.0,
        style: DiagramStyle | None = None,
        **send_kwargs
    ):
        hops = _normalize_hops(connectors, default_reverse=reverse)
        if not hops:
            raise ValueError("FanIn needs at least one connector")
        if isinstance(packets, Packet):
            packets = [packets.copy() for _ in hops]
        packets = list(packets)
        if len(packets) != len(hops):
            raise ValueError("FanIn needs one packet per connector")
        style = _resolve_style(_pick(style, getattr(packets[0], "style", None)))
        self.packets = packets
        sends = AnimationGroup(*(
            Send(p, connector, reverse=rev, run_time=run_time, fade_out=True, **send_kwargs)
            for p, (connector, rev) in zip(packets, hops)
        ), lag_ratio=lag_ratio)
        anims = [sends]
        self.merged = None
        if merged is not None:
            if isinstance(merged, str):
                merged = Packet(merged, shape="pill", color=style.reply_color, style=style)
            first, first_reverse = hops[0]
            self.meeting_point = _travel_path(first, first_reverse).get_end() if merged_at is None else np.array(merged_at, dtype=float)
            merged.move_to(self.meeting_point)
            self.merged = merged
            anims.append(FadeInAfter(merged, delay=0.8, run_time=sends.run_time))
        super().__init__(*anims)


# Queues


class MessageQueue(VGroup):
    """
    A queue whose depth is visible: ``capacity`` slots in a row, the first
    ``depth`` of them filled. Slot 0 is the head, where items leave; new items
    fill towards the tail, the far end in ``direction``. Items are the packet
    colour until the queue is ``warn_at`` full, then the warning colour, and
    the error colour when full. A counter such as ``3/8`` sits beside it.

    ``set_depth``, ``enqueue`` and ``dequeue`` change it between plays;
    ``Enqueue`` and ``Dequeue`` animate a packet in or out. Wires attach to
    the row of slots (``get_port``), so ``Connector(producer, queue)`` works.

    ``depth`` here is the queue's, replacing manim's ``Mobject.depth`` (the
    z-extent); the queue is flat, so nothing is lost. ``inflight`` counts
    ``Enqueue`` packets still on their way, so overlapping arrivals each get
    their own slot and are turned away once the queue will be full.
    """
    def __init__(
        self,
        capacity: int = 8,
        depth: int = 0,
        direction: Vector3D = RIGHT,
        slot_size: float = 0.28,
        gap: float = 0.06,
        label: str = "",
        warn_at: float = 0.75,
        show_count: bool = True,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        style = _resolve_style(style)
        self.style = style
        self.capacity = capacity
        self.direction = normalize(np.array(direction, dtype=float))
        self.warn_at = warn_at
        self.slot_size = slot_size

        self.slots = VGroup(*(Square(side_length=slot_size) for _ in range(capacity)))
        self.slots.set_stroke(style.node_stroke, width=1.5).set_fill(style.node_fill, opacity=1.0)
        self.slots.arrange(self.direction, buff=gap)
        self.items = VGroup()
        for slot in self.slots:
            item = Square(side_length=0.72 * slot_size)
            item.set_stroke(width=0).set_fill(style.packet_color, opacity=0.0)
            item.move_to(slot)
            self.items.add(item)
        self.add(self.slots, self.items)

        horizontal = abs(self.direction[0]) >= abs(self.direction[1])
        self.label = None
        if label:
            self.label = _make_text(label, font_size=style.small_font_size, style=style)
            self.label.next_to(self.slots, UP if horizontal else RIGHT, buff=SMALL_BUFF)
            self.add(self.label)
        self.count = None
        if show_count:
            self.count = _backstroke(_make_text("0/0", font_size=style.small_font_size - 4, style=style))
            self.count.next_to(self.slots, DOWN if horizontal else RIGHT, buff=SMALL_BUFF)
            if not horizontal and self.label is not None:
                self.count.next_to(self.slots, DOWN, buff=SMALL_BUFF)
            self.add(self.count)

        self._depth = 0
        self.inflight = 0     # arrivals on their way in, counted by Enqueue
        self.set_depth(depth)
        self.set_z_index(Z_NODE)

    # State
    @property
    def depth(self) -> int:
        return self._depth

    @depth.setter
    def depth(self, value: int) -> None:
        self.set_depth(value)

    def load(self) -> float:
        return self.depth / self.capacity

    def is_full(self) -> bool:
        return self.depth >= self.capacity

    def is_empty(self) -> bool:
        return self.depth == 0

    def item_color(self, depth: int | None = None) -> ManimColor:
        depth = _pick(depth, self.depth)
        if depth >= self.capacity:
            return self.style.error_color
        if depth / self.capacity >= self.warn_at:
            return self.style.warning_color
        return self.style.packet_color

    def set_depth(self, depth: int) -> Self:
        depth = int(np.clip(depth, 0, self.capacity))
        color = self.item_color(depth)
        for i, item in enumerate(self.items):
            item.set_fill(color, opacity=1.0 if i < depth else 0.0)
        if self.count is not None:
            # Mutated in place rather than swapped: manim's Cairo renderer
            # decides what to draw once per play, so a new object would not
            # show until the next one.
            new = _backstroke(_make_text(f"{depth}/{self.capacity}", font_size=self.count.font_size, style=self.style))
            new.move_to(self.count)
            self.count.become(new)
            self.count.original_text = new.original_text
            self.count.text = new.text
        self._depth = depth
        return self

    def enqueue(self, n: int = 1) -> Self:
        return self.set_depth(self.depth + n)

    def dequeue(self, n: int = 1) -> Self:
        return self.set_depth(self.depth - n)

    # Geometry
    def get_slot_point(self, index: int) -> Point3D:
        return self.slots[index].get_center()

    def get_head_point(self) -> Point3D:
        """Just outside the head, where dequeued items appear."""
        return self.slots.get_critical_point(-self.direction) - 0.6 * self.slot_size * self.direction

    def get_tail_point(self) -> Point3D:
        """Just outside the tail, where arriving items are turned away when the queue is full."""
        return self.slots.get_critical_point(self.direction) + 0.6 * self.slot_size * self.direction

    def get_port(self, direction: Vector3D, offset: float = 0.0) -> Point3D:
        return bounding_box_point(self.slots, direction)

    def get_port_toward(self, other: Mobject | Point3D, offset: float = 0.0) -> Point3D:
        target = other.get_center() if isinstance(other, Mobject) else np.array(other, dtype=float)
        vect = target - self.slots.get_center()
        direction = RIGHT * np.sign(vect[0]) if abs(vect[0]) >= abs(vect[1]) else UP * np.sign(vect[1])
        return self.get_port(direction, offset)


def _point_of(where, toward: Mobject) -> np.ndarray:
    if isinstance(where, Mobject):
        if hasattr(where, "get_port_toward"):
            return np.array(where.get_port_toward(toward), dtype=float)
        return np.array(where.get_center(), dtype=float)
    return np.array(where, dtype=float)


class _QueueMove(Animation):
    """
    Shared machinery for ``Enqueue`` and ``Dequeue``.

    Two facts about manim shape this class. Manim's renderer paints every
    scene mobject that no running animation owns once per ``play``, so the
    queue must be part of the animation's mobject for its depth to change on
    screen. And an ``AnimationGroup`` (so ``LaggedStart`` too) calls ``begin``
    on all its children up front, so what the queue looks like when a child
    really starts can only be read from its first ``interpolate`` calls: the
    decision is re-made while ``alpha`` is still tiny and frozen after.
    """
    SETTLE = 0.02   # alpha below which the start is still being decided
    LAND = 0.85     # alpha at which the packet counts as in (or out of) the queue

    def __init__(self, queue: MessageQueue, packet: Packet, *extra: Mobject, remove_packet: bool, **kwargs):
        self.queue = queue
        self.packet = packet
        self.remove_packet = remove_packet
        self.full_opacities = _family_opacities(packet)
        _set_family_opacity(packet, 0.0, self.full_opacities)
        super().__init__(VGroup(packet, *extra, queue), **kwargs)

    def begin(self) -> None:
        self._release()
        self.frozen = False
        self.applied = False
        super().begin()

    def _decide(self) -> None:
        raise NotImplementedError

    def _reserve(self) -> None:
        """Called once, when the start is settled."""

    def _release(self) -> None:
        """Undo ``_reserve`` if the animation is begun again before it landed."""

    def interpolate_mobject(self, alpha: float) -> None:
        if not self.frozen:
            self._decide()
            if alpha > self.SETTLE:
                self.frozen = True
                self._reserve()
        if alpha <= 0:
            _set_family_opacity(self.packet, 0.0, self.full_opacities)
            return
        self._move(alpha)

    def _move(self, alpha: float) -> None:
        raise NotImplementedError

    def clean_up_from_scene(self, scene) -> None:
        super().clean_up_from_scene(scene)
        if self.remove_packet:
            scene.remove(self.packet)


class Enqueue(_QueueMove):
    """
    A packet slides into the queue and becomes its next item; the depth
    changes as it lands. From ``from_point`` (a point or a mobject; by default
    wherever the packet is when the animation starts). When the queue is full
    the packet is turned away at the tail instead, dying with an X, and the
    depth does not change. Which happens is decided as the animation starts,
    so a lagged run of these fills a queue and then rejects.
    """
    def __init__(
        self,
        queue: MessageQueue,
        packet: Packet,
        from_point: Mobject | Point3D | None = None,
        run_time: float = 0.6,
        rate_func: Callable[[float], float] = smooth,
        **kwargs
    ):
        self.from_point = from_point
        self.cross = _cross(queue.get_tail_point(), queue.style.error_color, size=0.1)
        self.cross_base = self.cross.copy()
        self.cross.set_stroke(opacity=0.0)
        self.accepted = True
        super().__init__(queue, packet, self.cross, remove_packet=True, run_time=run_time, rate_func=rate_func, **kwargs)

    def _decide(self) -> None:
        if self.from_point is not None:
            self.packet.move_to(_point_of(self.from_point, self.queue))
        self.origin = np.array(self.packet.get_center(), dtype=float)
        # Packets already on their way have claimed the slots before this one
        slot = self.queue.depth + self.queue.inflight
        self.accepted = slot < self.queue.capacity
        self.target = np.array(
            self.queue.get_slot_point(slot) if self.accepted else self.queue.get_tail_point(),
            dtype=float,
        )

    def _reserve(self) -> None:
        self.reserved = self.accepted
        if self.reserved:
            self.queue.inflight += 1

    def _release(self) -> None:
        if getattr(self, "reserved", False):
            self.queue.inflight -= 1
            self.reserved = False

    def _move(self, alpha: float) -> None:
        t = self.rate_func(alpha)
        self.packet.move_to(self.origin + t * (self.target - self.origin))
        fade = 0.3
        factor = 1.0 if alpha < 1 - fade else max(0.0, (1 - alpha) / fade)
        _set_family_opacity(self.packet, factor, self.full_opacities)
        if self.accepted:
            if alpha >= self.LAND and not self.applied:
                self._release()
                self.queue.enqueue(1)
                self.applied = True
        elif alpha > 0.7:
            u = (alpha - 0.7) / 0.3
            self.cross.become(self.cross_base).scale(0.6 + 0.6 * smooth(u))
            self.cross.set_stroke(opacity=min(1.0, u / 0.4) * (1 - smooth(max(0.0, (u - 0.6) / 0.4))))
        else:
            self.cross.set_stroke(opacity=0.0)

    def clean_up_from_scene(self, scene) -> None:
        super().clean_up_from_scene(scene)
        scene.remove(self.cross)


class Dequeue(_QueueMove):
    """
    The item at the head leaves: the depth drops as the animation starts and
    a packet (given, or a dot in the packet colour) slides out of the head to
    ``to`` (a point, a mobject, or nothing, in which case it fades just
    outside). On an empty queue nothing happens.
    """
    def __init__(
        self,
        queue: MessageQueue,
        packet: Packet | None = None,
        to: Mobject | Point3D | None = None,
        run_time: float = 0.6,
        fade_out: bool = True,
        rate_func: Callable[[float], float] = smooth,
        **kwargs
    ):
        self.to = to
        self.fade_out = fade_out
        self.active = False
        packet = packet if packet is not None else Packet(color=queue.style.packet_color, style=queue.style)
        super().__init__(queue, packet, remove_packet=fade_out, run_time=run_time, rate_func=rate_func, **kwargs)

    def _decide(self) -> None:
        self.active = not self.queue.is_empty()
        self.origin = np.array(self.queue.get_head_point(), dtype=float)
        if self.to is None:
            self.target = self.origin - 0.9 * self.queue.direction
        else:
            self.target = _point_of(self.to, self.queue)
        self.packet.move_to(self.origin)

    def _move(self, alpha: float) -> None:
        if not self.active:
            _set_family_opacity(self.packet, 0.0, self.full_opacities)
            return
        if not self.applied:
            self.queue.dequeue(1)
            self.applied = True
        t = self.rate_func(alpha)
        self.packet.move_to(self.origin + t * (self.target - self.origin))
        factor = min(1.0, alpha / 0.15)
        if self.fade_out and alpha > 0.7:
            factor = min(factor, (1 - alpha) / 0.3)
        _set_family_opacity(self.packet, factor, self.full_opacities)

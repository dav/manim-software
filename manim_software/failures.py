"""
The vocabulary of things going wrong on a wire: a packet that never arrives,
a timer that runs out, a retry with growing backoff, and a circuit breaker
that opens after too many failures.

Everything composes with ``Packet`` and ``Send``. ``Drop`` is a ``Send`` that
dies part way; ``Retry`` is a few ``Drop``s and a ``Send`` with a ``Countdown``
between them; ``CircuitBreaker`` sits on a connector, and
``Drop(packet, connector, at=breaker)`` rejects a packet where it stands.

As in ``packets``, anything that appears mid-animation is kept invisible until
its own ``begin``, because manim adds every queued mobject up front. Things are
also faded out one by one rather than through a fresh group: manim removes only
what it finds in the scene, and a group made on the spot is not there.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from manim import DL
from manim import DOWN
from manim import DR
from manim import LEFT
from manim import PI
from manim import RIGHT
from manim import SMALL_BUFF
from manim import TAU
from manim import UL
from manim import UP
from manim import UR
from manim import Animation
from manim import AnimationGroup
from manim import Circle
from manim import Dot
from manim import FadeOut
from manim import Line
from manim import Mobject
from manim import RoundedRectangle
from manim import Sector
from manim import Succession
from manim import VGroup
from manim import VMobject
from manim import linear
from manim import smooth
from manim.utils.space_ops import normalize
from manim.utils.space_ops import rotate_vector

from manim_software.connectors import Connector
from manim_software.connectors import length_alpha_to_curve_alpha
from manim_software.packets import FadeInAfter
from manim_software.packets import Packet
from manim_software.packets import Send
from manim_software.packets import _ArrivalFlash
from manim_software.packets import _MoveAlongRoute
from manim_software.packets import _WireFlash
from manim_software.packets import _family_opacities
from manim_software.packets import _packet_color
from manim_software.packets import _set_family_opacity
from manim_software.packets import _travel_path
from manim_software.style import Z_ANNOTATION
from manim_software.style import Z_EDGE
from manim_software.style import Z_EDGE_LABEL
from manim_software.style import Z_PACKET
from manim_software.style import _backstroke
from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Callable
    from typing import Self

    from manim.typing import ManimColor
    from manim.typing import Point3D
    from manim.typing import Vector3D

    from manim_software.style import DiagramStyle


# Marks


def _cross(point: Point3D, color: ManimColor, size: float = 0.14, stroke_width: float = 4.0) -> VGroup:
    """An X centred on ``point``: where something died."""
    point = np.array(point, dtype=float)
    cross = VGroup(
        Line(point + size * UL, point + size * DR),
        Line(point + size * UR, point + size * DL),
    )
    cross.set_stroke(color, width=stroke_width)
    cross.set_z_index(Z_PACKET + 1)
    return cross


class _Blip(Animation):
    """
    A mark that pops in after ``delay`` (a fraction of the run time), swells a
    little and is gone by the end. Invisible before it begins and after.
    """
    def __init__(self, mobject: Mobject, delay: float = 0.7, **kwargs):
        self.delay = delay
        self.full_opacities = _family_opacities(mobject)
        self.base = mobject.copy()
        _set_family_opacity(mobject, 0.0, self.full_opacities)
        super().__init__(mobject, remover=True, **kwargs)

    def interpolate_mobject(self, alpha: float) -> None:
        if alpha <= self.delay:
            _set_family_opacity(self.mobject, 0.0, self.full_opacities)
            return
        t = (alpha - self.delay) / (1 - self.delay)
        opacity = min(1.0, t / 0.3) * (1.0 - smooth(max(0.0, (t - 0.5) / 0.5)))
        scale = 0.6 + 0.6 * smooth(min(1.0, t / 0.4))
        self.mobject.become(self.base)
        self.mobject.scale(scale)
        _set_family_opacity(self.mobject, opacity, self.full_opacities)

    def finish(self) -> None:
        super().finish()
        _set_family_opacity(self.mobject, 0.0, self.full_opacities)


# Timers


class Timer(VGroup):
    """
    A small clock face: a ring, a pie that fills as time passes, and an
    optional label beneath. ``set_fraction`` moves the pie by hand;
    ``Countdown`` animates it; ``expire`` fills it in the error colour.
    """
    def __init__(
        self,
        label: str = "",
        radius: float = 0.22,
        color: ManimColor | None = None,
        fraction: float = 0.0,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.radius = radius
        self.timer_color = _pick(color, style.warning_color)
        self.face = Circle(radius=radius)
        self.face.set_stroke(self.timer_color, width=2.0).set_fill(style.node_fill, opacity=0.95)
        self.pie = self._make_pie(1e-3)
        self.add(self.face, self.pie)
        self.label = None
        if label:
            self.label = _backstroke(_make_text(label, font_size=style.small_font_size - 4, style=style))
            self.label.next_to(self.face, DOWN, buff=0.5 * SMALL_BUFF)
            self.add(self.label)
        self.fraction = 0.0
        self.set_fraction(fraction)
        self.set_z_index(Z_ANNOTATION)

    def _make_pie(self, fraction: float) -> Sector:
        pie = Sector(
            radius=0.72 * self.radius,
            start_angle=PI / 2,
            angle=-TAU * max(fraction, 1e-3),
            arc_center=self.face.get_center(),
        )
        pie.set_fill(self.timer_color, opacity=1.0).set_stroke(width=0)
        return pie

    def set_fraction(self, fraction: float) -> Self:
        fraction = float(np.clip(fraction, 0.0, 1.0))
        opacity = self.pie.get_fill_opacity()
        self.pie.become(self._make_pie(fraction))
        self.pie.set_fill(opacity=opacity)
        self.fraction = fraction
        return self

    def get_fraction(self) -> float:
        return self.fraction

    def set_timer_color(self, color: ManimColor) -> Self:
        self.timer_color = color
        self.face.set_stroke(color)
        self.pie.set_fill(color)
        return self

    def expire(self) -> Self:
        """Full, in the error colour: time ran out."""
        self.set_fraction(1.0)
        return self.set_timer_color(self.style.error_color)


class Countdown(Animation):
    """
    Sweep a ``Timer`` from ``start`` to ``end`` over the run time, linearly by
    default so it reads as a clock. ``expire_color`` recolours it when it
    completes; ``transient`` shows it only while it runs.
    """
    def __init__(
        self,
        timer: Timer,
        start: float = 0.0,
        end: float = 1.0,
        expire_color: ManimColor | None = None,
        transient: bool = False,
        rate_func: Callable[[float], float] = linear,
        **kwargs
    ):
        self.start_fraction = start
        self.end_fraction = end
        self.expire_color = expire_color
        self.transient = transient
        self.full_opacities = _family_opacities(timer)
        if transient:
            _set_family_opacity(timer, 0.0, self.full_opacities)
        super().__init__(timer, rate_func=rate_func, **kwargs)

    def begin(self) -> None:
        if self.transient:
            _set_family_opacity(self.mobject, 1.0, self.full_opacities)
        self.mobject.set_fraction(self.start_fraction)
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        t = self.rate_func(alpha)
        self.mobject.set_fraction(self.start_fraction + t * (self.end_fraction - self.start_fraction))
        if alpha >= 1.0 and self.expire_color is not None:
            self.mobject.set_timer_color(self.expire_color)

    def finish(self) -> None:
        super().finish()
        if self.transient:
            _set_family_opacity(self.mobject, 0.0, self.full_opacities)


class Timeout(Succession):
    """
    Waiting for an answer that never comes. A ``Timer`` appears beside
    ``waiter`` (a component, or anything with a bounding box), runs out over
    ``wait`` seconds, turns the error colour with a flash, and a note
    (``label``) pops up beside it. Everything then fades unless ``keep`` is
    set, in which case ``self.marks`` (timer and note) stays for the caller to
    remove.

    ``run_time`` stretches or squeezes the whole thing to fit a slot. With
    ``keep``, ``dismiss()`` is the animation that removes the marks later.
    """
    def __init__(
        self,
        waiter: Mobject,
        wait: float = 1.5,
        label: str = "timeout",
        direction: Vector3D = UR,
        buff: float = SMALL_BUFF,
        keep: bool = False,
        radius: float = 0.22,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        style = _resolve_style(_pick(style, getattr(waiter, "style", None)))
        self.style = style
        direction = np.array(direction, dtype=float)
        self.timer = Timer(radius=radius, color=style.warning_color, style=style)
        self.timer.next_to(waiter, direction, buff=buff)
        self.note = None
        marks = [self.timer]
        if label:
            self.note = _backstroke(_make_text(label, font_size=style.small_font_size, color=style.error_color, style=style))
            side = RIGHT if direction[0] >= 0 else LEFT
            self.note.next_to(self.timer, side, buff=SMALL_BUFF)
            self.note.set_z_index(Z_ANNOTATION)
            marks.append(self.note)
        self.marks = VGroup(*marks)

        anims = [
            FadeInAfter(self.timer, delay=0.0, run_time=0.2),
            Countdown(self.timer, expire_color=style.error_color, run_time=wait),
        ]
        expiry = [_ArrivalFlash(
            self.timer.get_center(), color=style.error_color,
            delay=0.0, num_lines=10, line_length=0.14, flash_radius=radius + 0.05, run_time=0.4,
        )]
        if self.note is not None:
            expiry.append(FadeInAfter(self.note, delay=0.0, run_time=0.3))
        anims.append(AnimationGroup(*expiry))
        if not keep:
            anims.append(self.dismiss(run_time=0.4))
        super().__init__(*anims, **kwargs)

    def dismiss(self, run_time: float = 0.4) -> AnimationGroup:
        """Fade the timer and note away (each on its own, so both leave the scene)."""
        return AnimationGroup(*(FadeOut(mark, run_time=run_time) for mark in self.marks), run_time=run_time)


# Dropped packets


def _partial_path(full: VMobject, start: float, end: float) -> VMobject:
    """The stretch of ``full`` between two arc-length fractions."""
    path = VMobject()
    path.set_points(full.points.copy())
    path.match_style(full)
    path.pointwise_become_partial(
        full,
        length_alpha_to_curve_alpha(full, start),
        length_alpha_to_curve_alpha(full, end),
    )
    return path


class Drop(AnimationGroup):
    """
    A packet that never arrives. It travels ``at`` of the way along the
    connector (a fraction, or a ``CircuitBreaker`` sitting on the wire), then
    fades out with a burst and an X in the error colour where it died.
    ``reverse`` runs the wire the other way, as for ``Reply``.
    """
    def __init__(
        self,
        packet: Packet,
        connector: Connector | VMobject,
        at: float | CircuitBreaker = 0.6,
        reverse: bool = False,
        run_time: float = 1.0,
        rate_func: Callable[[float], float] = smooth,
        trail: bool = True,
        trail_time_width: float = 0.35,
        burst: bool = True,
        fade_in: bool = True,
        color: ManimColor | None = None,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        style = _resolve_style(_pick(style, getattr(packet, "style", None)))
        self.packet = packet
        full = _travel_path(connector, reverse)
        self.at = _resolve_drop_point(at, reverse)
        self.path = _partial_path(full, 0.0, self.at)
        self.point = self.path.get_end()
        burst_color = _pick(color, style.error_color)
        anims = [
            _MoveAlongRoute(
                packet, self.path,
                fade_in=fade_in, fade_out=True, fade_fraction=0.2,
                run_time=run_time, rate_func=rate_func, remover=True,
            )
        ]
        if trail:
            trail_mob = self.path.copy()
            width = self.path.get_stroke_width() or 3.0
            trail_mob.set_stroke(_packet_color(packet), width=2.0 * width, opacity=1.0)
            trail_mob.set_z_index(Z_EDGE)
            anims.append(_WireFlash(trail_mob, time_width=trail_time_width, run_time=run_time, rate_func=rate_func))
        if burst:
            flash = _ArrivalFlash(
                self.point, color=burst_color, delay=0.75,
                num_lines=8, line_length=0.16, run_time=run_time,
            )
            flash.lines.set_z_index(Z_PACKET)
            anims.append(flash)
            anims.append(_Blip(_cross(self.point, burst_color), delay=0.75, run_time=run_time))
        super().__init__(*anims, run_time=run_time, **kwargs)


def _resolve_drop_point(at, reverse: bool) -> float:
    if isinstance(at, CircuitBreaker):
        return 1.0 - at.proportion if reverse else at.proportion
    at = float(at)
    if not 0.0 < at <= 1.0:
        raise ValueError("at must be a fraction of the wire in (0, 1]")
    return at


class Retry(Succession):
    """
    Try, fail, wait, try again. Each failed attempt is a ``Drop`` of a copy of
    ``packet``; between attempts a ``Timer`` counts down the backoff, which
    starts at ``backoff`` seconds and grows by ``multiplier`` each time (capped
    at ``max_backoff``). The last attempt is a ``Send`` when ``succeed`` is
    true and one more ``Drop`` otherwise. A badge by the sender counts the
    attempts.

    ``self.waits`` are the backoff durations; ``self.attempt_packets`` the
    packets used, the original last.
    """
    def __init__(
        self,
        packet: Packet,
        connector: Connector,
        attempts: int = 3,
        succeed: bool = True,
        drop_at: float = 0.6,
        hop_time: float = 0.8,
        backoff: float = 0.5,
        multiplier: float = 2.0,
        max_backoff: float | None = None,
        reverse: bool = False,
        badge: bool = True,
        badge_direction: Vector3D = UP,
        trail: bool = True,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        style = _resolve_style(_pick(style, getattr(packet, "style", None)))
        self.style = style
        self.packet = packet
        self.waits = [
            min(backoff * multiplier ** i, max_backoff) if max_backoff is not None else backoff * multiplier ** i
            for i in range(attempts - 1)
        ]
        self.attempt_packets = [packet.copy() for _ in range(attempts - 1)] + [packet]

        full = _travel_path(connector, reverse)
        sender = None
        if isinstance(connector, Connector):
            sender = connector.end_mob if reverse else connector.start_mob
        anchor = sender if isinstance(sender, Mobject) else full.get_start()

        self.badges = []
        self.timers = []
        small = style.small_font_size
        for i in range(attempts):
            text = f"attempt {i + 1}/{attempts}" if attempts > 1 else "attempt 1"
            label = _backstroke(_make_text(text, font_size=small, style=style))
            label.next_to(anchor, badge_direction, buff=SMALL_BUFF)
            label.set_z_index(Z_ANNOTATION)
            self.badges.append(label)
        for wait in self.waits:
            timer = Timer(label=f"{wait:.1f}s", radius=0.2, style=style)
            timer.next_to(self.badges[0], RIGHT, buff=SMALL_BUFF)
            self.timers.append(timer)

        anims = []
        for i, attempt_packet in enumerate(self.attempt_packets):
            last = i == attempts - 1
            step = []
            if badge:
                step.append(FadeInAfter(self.badges[i], delay=0.0, run_time=0.25))
                if i > 0:
                    step.append(FadeOut(self.badges[i - 1], run_time=0.25))
            if last and succeed:
                step.append(Send(attempt_packet, connector, reverse=reverse, run_time=hop_time, trail=trail, fade_out=True))
            else:
                step.append(Drop(attempt_packet, connector, at=drop_at, reverse=reverse, run_time=hop_time, trail=trail, style=style))
            anims.append(AnimationGroup(*step))
            if not last:
                anims.append(Countdown(self.timers[i], transient=True, run_time=self.waits[i]))
        if badge:
            anims.append(FadeOut(self.badges[-1], run_time=0.3))
        super().__init__(*anims, **kwargs)


# Circuit breakers


class CircuitBreaker(VGroup):
    """
    A switch drawn on a wire, ``proportion`` of the way along ``connector``.

    ``closed``: the lever bridges the contacts and traffic flows. ``open``:
    the lever is lifted and everything glows the error colour;
    ``Drop(packet, connector, at=breaker)`` shows a request rejected there.
    ``half_open``: the lever is half lifted in the warning colour, letting one
    probe through. ``set_state`` only moves the lever and recolours, so
    ``breaker.animate.set_state("open")`` blends; ``TripBreaker`` and
    ``ResetBreaker`` add a flash.

    Only the wire's geometry at that point is remembered, not the connector,
    so manim's copies stay cheap; rebuild the breaker if the wire is rerouted.
    """
    STATES = ("closed", "open", "half_open")
    LEVER_ANGLES = {"closed": 0.0, "half_open": 0.45, "open": 0.9}

    def __init__(
        self,
        connector: Connector | VMobject,
        proportion: float = 0.5,
        size: float = 0.5,
        state: str = "closed",
        label: str | None = None,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(_pick(style, getattr(connector, "style", None)))
        self.style = style
        self.proportion = float(proportion)
        self.size = size
        path = connector.get_travel_path() if hasattr(connector, "get_travel_path") else connector
        eps = 0.01
        centre = path.point_from_proportion(self.proportion)
        before = path.point_from_proportion(max(0.0, self.proportion - eps))
        after = path.point_from_proportion(min(1.0, self.proportion + eps))
        self.tangent = normalize(after - before)
        self.normal = np.array([-self.tangent[1], self.tangent[0], 0.0])
        self.center_point = centre
        half = 0.5 * size
        self.left = centre - half * self.tangent
        self.right = centre + half * self.tangent

        self.housing = RoundedRectangle(corner_radius=0.06, width=size + 0.3, height=0.36)
        self.housing.set_fill(style.node_fill, opacity=1.0).set_stroke(style.node_stroke, width=1.5)
        self.housing.rotate(float(np.arctan2(self.tangent[1], self.tangent[0])))
        self.housing.move_to(centre)
        self.contacts = VGroup(Dot(self.left, radius=0.05), Dot(self.right, radius=0.05))
        self.lever = Line(self.left, self.right, stroke_width=4.0)
        self.add(self.housing, self.contacts, self.lever)
        self.label = None
        if label:
            self.label = _backstroke(_make_text(label, font_size=style.small_font_size - 4, style=style))
            self.label.next_to(self.housing, DOWN, buff=0.5 * SMALL_BUFF)
            self.add(self.label)
        self.state = state
        self.set_state(state)
        self.set_z_index(Z_EDGE_LABEL)

    def _state_color(self, name: str) -> ManimColor:
        return {
            "closed": self.style.edge_color,
            "open": self.style.error_color,
            "half_open": self.style.warning_color,
        }[name]

    def set_state(self, name: str) -> Self:
        if name not in self.STATES:
            raise KeyError(f"Unknown breaker state '{name}'; expected one of {self.STATES}")
        angle = self.LEVER_ANGLES[name]
        arm = rotate_vector(self.right - self.left, angle)
        self.lever.put_start_and_end_on(self.left, self.left + arm)
        color = self._state_color(name)
        self.lever.set_stroke(color)
        self.contacts.set_color(color)
        self.housing.set_stroke(self.style.node_stroke if name == "closed" else color)
        self.state = name
        return self

    def is_closed(self) -> bool:
        return self.state == "closed"

    def get_point(self) -> Point3D:
        """Where the breaker sits on the wire."""
        return self.center_point


class TripBreaker(AnimationGroup):
    """The breaker snaps open: a flash at the contacts as the lever lifts."""
    def __init__(self, breaker: CircuitBreaker, run_time: float = 0.6, **kwargs):
        flash = _ArrivalFlash(
            breaker.get_point(), color=breaker.style.error_color,
            delay=0.0, num_lines=10, line_length=0.14, flash_radius=0.3, run_time=run_time,
        )
        flash.lines.set_z_index(Z_PACKET)
        super().__init__(
            breaker.animate(run_time=run_time).set_state("open"),
            flash,
            run_time=run_time,
            **kwargs
        )


class ResetBreaker(AnimationGroup):
    """The breaker closes again, with a flash in the done colour."""
    def __init__(self, breaker: CircuitBreaker, run_time: float = 0.6, **kwargs):
        flash = _ArrivalFlash(
            breaker.get_point(), color=breaker.style.done_color,
            delay=0.0, num_lines=10, line_length=0.12, flash_radius=0.3, run_time=run_time,
        )
        flash.lines.set_z_index(Z_PACKET)
        super().__init__(
            breaker.animate(run_time=run_time).set_state("closed"),
            flash,
            run_time=run_time,
            **kwargs
        )

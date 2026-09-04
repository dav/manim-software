"""
Ways to point at things: captions pinned to the screen, a spotlight that
dims everything but one component, and callouts with a leader line.
"""
from __future__ import annotations

import weakref
from typing import TYPE_CHECKING

import numpy as np

from manim import DOWN
from manim import MED_LARGE_BUFF
from manim import MED_SMALL_BUFF
from manim import SMALL_BUFF
from manim import UR
from manim import AnimationGroup
from manim import BackgroundRectangle
from manim import Circumscribe
from manim import LaggedStart
from manim import Line
from manim import Mobject
from manim import Restore
from manim import RoundedRectangle
from manim import Transform
from manim import VGroup
from manim import VMobject
from manim.utils.space_ops import normalize

from manim_software.style import Z_ANNOTATION
from manim_software.style import Z_CAPTION
from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Iterable
    from typing import Self

    from manim import Animation
    from manim import Scene
    from manim.typing import ManimColor
    from manim.typing import Vector3D

    from manim_software.style import DiagramStyle


class Caption(VGroup):
    """
    A line of narration at a screen edge, above everything else.

    In a ``ThreeDScene`` call ``caption.pin(scene)`` instead of ``scene.add``:
    it registers the caption as fixed in frame so camera moves leave it
    where it is, and ``set_text`` keeps it registered.
    """
    def __init__(
        self,
        text: str,
        position: Vector3D = DOWN,
        font_size: int | None = None,
        buff: float = MED_LARGE_BUFF,
        background: bool = True,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.position = np.array(position, dtype=float)
        self.buff = buff
        self.font_size = _pick(font_size, style.label_font_size)
        self.background = background
        # A weak reference: manim deep-copies mobjects for every animation,
        # and a scene cannot be copied
        self._scene_ref = None
        self.text = self._build(text)
        self.add(self.text)
        self._place()
        self.set_z_index(Z_CAPTION)

    def _build(self, text: str) -> VGroup:
        text_mob = _make_text(text, font_size=self.font_size, style=self.style)
        if self.background:
            return VGroup(BackgroundRectangle(text_mob, buff=MED_SMALL_BUFF, fill_opacity=0.85), text_mob)
        return VGroup(text_mob)

    def _place(self) -> None:
        if np.any(self.position):
            self.to_edge(self.position, buff=self.buff)
        else:
            self.center()

    @property
    def scene(self) -> Scene | None:
        return self._scene_ref() if self._scene_ref is not None else None

    def pin(self, scene: Scene) -> Self:
        """Add to ``scene``, fixed in frame when the scene's camera can move in 3D."""
        self._scene_ref = weakref.ref(scene)
        if hasattr(scene, "add_fixed_in_frame_mobjects"):
            scene.add_fixed_in_frame_mobjects(self)
        else:
            scene.add(self)
        return self

    def set_text(self, text: str) -> Self:
        self.text.become(self._build(text))
        self._place()
        if self.scene is not None and hasattr(self.scene, "add_fixed_in_frame_mobjects"):
            # become() may have created new glyph mobjects the camera does not know
            self.scene.camera.add_fixed_in_frame_mobjects(self)
        return self


def _dimmed_copy(mobject: Mobject, factor: float) -> Mobject:
    """
    A copy with every opacity scaled by ``factor``. Manim's ``set_opacity``
    would give unfilled paths (wires) a fill instead.
    """
    copy = mobject.copy()
    for sm in copy.get_family():
        if isinstance(sm, VMobject):
            sm.set_fill(opacity=factor * sm.get_fill_opacity(), family=False)
            sm.set_stroke(opacity=factor * sm.get_stroke_opacity(), family=False)
            sm.set_stroke(opacity=factor * sm.get_stroke_opacity(background=True), background=True, family=False)
    return copy


def _members_excluding(root: Mobject, target: Mobject) -> list[Mobject]:
    """
    The largest pieces of ``root``'s family that do not contain ``target``:
    what to dim when spotlighting ``target`` inside ``root``.
    """
    if root is target:
        return []
    if target not in root.get_family():
        return [root]
    result = []
    for sub in root.submobjects:
        result.extend(_members_excluding(sub, target))
    return result


class Spotlight(AnimationGroup):
    """
    Dim everything in ``others`` that is not ``target`` and flash around the
    target. The dimmed mobjects save their state first, so ``Unspotlight``
    can restore them.
    """
    def __init__(
        self,
        target: Mobject,
        others: Mobject | Iterable[Mobject],
        dim_opacity: float = 0.25,
        flash: bool = True,
        color: ManimColor | None = None,
        buff: float = SMALL_BUFF,
        run_time: float = 1.0,
        **kwargs
    ):
        style = _resolve_style(getattr(target, "style", None))
        roots = [others] if isinstance(others, Mobject) else list(others)
        self.dimmed: list[Mobject] = []
        for root in roots:
            self.dimmed.extend(_members_excluding(root, target))
        anims: list[Animation] = []
        for mob in self.dimmed:
            mob.save_state()
            anims.append(Transform(mob, _dimmed_copy(mob, dim_opacity)))
        if flash:
            anims.append(Circumscribe(target, color=_pick(color, style.active_color), buff=buff, run_time=run_time))
        super().__init__(*anims, run_time=run_time, **kwargs)


class Unspotlight(LaggedStart):
    """Restore what a ``Spotlight`` dimmed (pass the spotlight, or the mobjects)."""
    def __init__(self, *spotlight_or_mobjects, lag_ratio: float = 0.02, run_time: float = 1.0, **kwargs):
        mobs: list[Mobject] = []
        for item in spotlight_or_mobjects:
            if isinstance(item, Spotlight):
                mobs.extend(item.dimmed)
            else:
                mobs.append(item)
        super().__init__(*(Restore(mob) for mob in mobs), lag_ratio=lag_ratio, run_time=run_time, **kwargs)


class Callout(VGroup):
    """A small note beside a target with a leader line pointing at it."""
    def __init__(
        self,
        target: Mobject,
        text: str,
        direction: Vector3D = UR,
        distance: float = 0.8,
        buff: float = SMALL_BUFF,
        font_size: int | None = None,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.target = target
        self.direction = np.array(direction, dtype=float)
        self.distance = distance
        self.buff = buff
        text_mob = _make_text(text, font_size=_pick(font_size, style.small_font_size), style=style)
        body = RoundedRectangle(
            corner_radius=0.12,
            width=text_mob.width + 2 * MED_SMALL_BUFF,
            height=text_mob.height + 2 * MED_SMALL_BUFF,
        )
        body.set_fill(style.node_fill, opacity=0.95)
        body.set_stroke(style.active_color, 1.5)
        text_mob.move_to(body)
        self.bubble = VGroup(body, text_mob)
        self.leader = Line(stroke_color=style.active_color, stroke_width=1.5)
        self.add(self.leader, self.bubble)
        self._place()
        self.set_z_index(Z_ANNOTATION)

    def _place(self) -> None:
        unit = normalize(self.direction)
        anchor = self.target.get_critical_point(self.direction)
        self.bubble.move_to(anchor + (self.distance + 0.5 * self.bubble.height) * unit)
        self.leader.put_start_and_end_on(
            anchor + self.buff * unit,
            self.bubble.get_critical_point(-self.direction),
        )

    def attach(self) -> Self:
        self.add_updater(lambda c: c._place())
        return self

    def detach(self) -> Self:
        self.clear_updaters()
        return self

"""
The frame a video opens on.

A scene that begins with ``self.play(FadeIn(card))`` has a completely black
first frame, because a fade starts at zero opacity. That is invisible while the
video plays and very visible everywhere else: a file browser's thumbnail, a
paused player, an ``<video>`` element before anyone presses play, the preview
in a chat message. The video looks broken until it is running.

So the card is *added* rather than faded in, and anything that moves moves
after the first frame is already on disk. ``open_on`` is the whole rule:

    class Explainer(Scene):
        def construct(self):
            open_on(self, TitleCard("How binding works", "a tour of the flow"))
            ...

Text is accepted either as a string or as a prebuilt mobject, the way
``Component`` and ``Connector`` take their labels. That matters more here than
it looks: manim drops the advance of a space below roughly 20pt, so a subtitle
built at its final size can render as ``atourof theflow``. A caller that has
its own text pipeline passes mobjects and keeps its spacing.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from manim import DOWN
from manim import FadeOut
from manim import VGroup
from manim import VMobject

from manim_software.style import Z_CAPTION
from manim_software.style import _make_text
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from manim import Scene

    from manim_software.style import DiagramStyle


class TitleCard(VGroup):
    """
    A title, an optional subtitle, and an optional footer, stacked and centred.

    Each line takes a string or a prebuilt mobject. The parts stay reachable as
    ``title`` / ``subtitle`` / ``footer`` so a scene can animate them
    separately — which is what ``open_on`` does to keep the title on the first
    frame while the lines under it arrive a beat later.
    """

    def __init__(
        self,
        title: str | VMobject,
        subtitle: str | VMobject | None = None,
        footer: str | VMobject | None = None,
        title_font_size: int = 46,
        subtitle_font_size: int = 26,
        footer_font_size: int = 19,
        buff: float = 0.35,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style

        def line(value, font_size, color):
            if value is None:
                return None
            if isinstance(value, VMobject):
                return value
            return _make_text(value, font_size=font_size, style=style, color=color)

        self.title = line(title, title_font_size, style.text_color)
        self.subtitle = line(subtitle, subtitle_font_size, style.muted_color)
        self.footer = line(footer, footer_font_size, style.muted_color)

        self.lines = VGroup(*(
            part for part in (self.title, self.subtitle, self.footer)
            if part is not None
        ))
        self.lines.arrange(DOWN, buff=buff)
        self.add(self.lines)
        self.set_z_index(Z_CAPTION)

    def supporting(self) -> VGroup:
        """Everything but the title — the parts that may arrive after frame 0."""
        return VGroup(*(
            part for part in (self.subtitle, self.footer) if part is not None
        ))


def open_on(
    scene: Scene,
    card: TitleCard,
    hold: float = 1.8,
    reveal: float = 0.8,
    fade_out: float = 0.6,
) -> TitleCard:
    """
    Open ``scene`` on ``card``, with the title already drawn on frame zero.

    The card is added, never faded in, so the first frame written to the file
    is the title rather than black. ``reveal`` then brings the subtitle and
    footer up from nothing, which keeps a little motion without costing the
    poster frame; pass ``reveal=0`` for a card that is simply there.

    Returns the card, still on screen if ``fade_out`` is zero.
    """
    supporting = card.supporting()
    if reveal > 0 and len(supporting):
        # Added at zero opacity rather than left out: the card is laid out and
        # centred as a whole, so revealing the lines must not move the title.
        supporting.set_opacity(0)

    scene.add(card)

    if reveal > 0 and len(supporting):
        scene.play(supporting.animate.set_opacity(1), run_time=reveal)
    if hold > 0:
        scene.wait(hold)
    if fade_out > 0:
        scene.play(FadeOut(card), run_time=fade_out)
    return card


__all__ = ["TitleCard", "open_on"]

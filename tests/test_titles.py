"""
The title card, and the one property it exists for: the first frame written to
the file already has the title on it. A scene that fades its card in from
nothing opens on black, which is what a thumbnail, a paused player and an
unplayed ``<video>`` all show.
"""
import numpy as np
import pytest

from manim import Text

from manim_software import DiagramStyle
from manim_software import TitleCard
from manim_software import open_on


class RecordingScene:
    """
    Enough of a Scene to see what ``open_on`` does, in what order.

    A real Scene needs a renderer to play anything, and the thing under test is
    the ordering, not the rendering.
    """

    def __init__(self):
        self.events = []
        self.mobjects = []

    def add(self, *mobjects):
        self.mobjects.extend(mobjects)
        self.events.append(("add", mobjects))

    def play(self, *animations, **kwargs):
        self.events.append(("play", animations))

    def wait(self, duration=1.0):
        self.events.append(("wait", duration))

    def kinds(self):
        return [kind for kind, _ in self.events]


def test_the_card_is_on_screen_before_anything_is_played():
    scene = RecordingScene()
    open_on(scene, TitleCard("A change worth explaining", "and why", "TICKET-1"))
    kinds = scene.kinds()
    assert kinds[0] == "add", f"the first thing a scene does must be add: {kinds}"
    assert "play" in kinds, "the card should still animate after frame zero"


def _opacities(mobject):
    """What actually gets painted: manim hangs a Text's colour on its glyphs."""
    return [part.get_fill_opacity() for part in mobject.family_members_with_points()]


def _colors(mobject):
    return {part.get_fill_color().to_hex().lower()
            for part in mobject.family_members_with_points()}


def test_the_title_itself_is_opaque_on_the_first_frame():
    scene = RecordingScene()
    card = open_on(scene, TitleCard("Visible", "later", "later too"))
    assert card in scene.mobjects
    # The subtitle and footer are what arrive late; the title never is.
    assert _opacities(card.title) == pytest.approx([1.0] * len(_opacities(card.title)))
    assert _opacities(card.supporting()) == pytest.approx(
        [0.0] * len(_opacities(card.supporting()))
    )


def test_a_card_with_no_reveal_is_wholly_there_from_the_start():
    scene = RecordingScene()
    card = open_on(scene, TitleCard("All at once", "every line"), reveal=0)
    assert scene.kinds()[0] == "add"
    assert _opacities(card) == pytest.approx([1.0] * len(_opacities(card)))


def test_revealing_the_supporting_lines_does_not_move_the_title():
    card = TitleCard("Steady", "shifty", "also shifty")
    before = card.title.get_center().copy()
    card.supporting().set_opacity(0)
    assert np.allclose(card.title.get_center(), before)
    card.supporting().set_opacity(1)
    assert np.allclose(card.title.get_center(), before)


def test_lines_stack_downwards_in_the_order_given():
    card = TitleCard("top", "middle", "bottom")
    ys = [part.get_center()[1] for part in (card.title, card.subtitle, card.footer)]
    assert ys[0] > ys[1] > ys[2]


def test_the_title_is_the_largest_line():
    card = TitleCard("title", "subtitle", "footer")
    heights = [card.title.height, card.subtitle.height, card.footer.height]
    assert heights[0] > heights[1]
    assert heights[1] > heights[2]


def test_supporting_lines_are_optional():
    bare = TitleCard("just a title")
    assert bare.subtitle is None and bare.footer is None
    assert len(bare.supporting()) == 0
    assert len(bare.lines) == 1

    two = TitleCard("title", "subtitle")
    assert two.footer is None
    assert len(two.supporting()) == 1


def test_a_bare_card_still_puts_its_title_on_the_first_frame():
    scene = RecordingScene()
    open_on(scene, TitleCard("nothing under me"))
    assert scene.kinds()[0] == "add"
    assert scene.kinds().count("play") == 1, "only the fade out is left to play"


def test_prebuilt_mobjects_are_used_as_given():
    """
    Callers with their own text pipeline pass mobjects, the way Component and
    Connector take labels. Manim drops the advance of a space below about 20pt,
    so a caller that lays out large and scales down must be able to hand the
    result over untouched.
    """
    subtitle = Text("laid out elsewhere", font_size=48).scale(0.5)
    card = TitleCard("title", subtitle)
    assert card.subtitle is subtitle
    assert subtitle in card.get_family()


def test_a_mobject_title_is_still_the_part_held_back_from_the_reveal():
    scene = RecordingScene()
    title = Text("mine")
    card = open_on(scene, TitleCard(title, Text("theirs")))
    assert card.title is title
    assert _opacities(title) == pytest.approx([1.0] * len(_opacities(title)))


def test_the_style_supplies_the_colours():
    style = DiagramStyle(text_color="#ff0000", muted_color="#00ff00")
    card = TitleCard("title", "subtitle", "footer", style=style)
    assert _colors(card.title) == {"#ff0000"}
    assert _colors(card.subtitle) == {"#00ff00"}
    assert _colors(card.footer) == {"#00ff00"}


def test_the_card_floats_above_a_diagram():
    from manim_software import Z_CAPTION
    assert TitleCard("over everything").z_index == Z_CAPTION


def test_hold_and_fade_can_be_turned_off_to_leave_the_card_up():
    scene = RecordingScene()
    open_on(scene, TitleCard("stays"), hold=0, reveal=0, fade_out=0)
    assert scene.kinds() == ["add"]

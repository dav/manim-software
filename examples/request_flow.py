"""
Example scenes for manim_software.

Render with, for instance:

    manim -pql examples/request_flow.py RequestFlow           # low-res preview
    manim -qh examples/request_flow.py RequestFlow            # 1080p
    manim -s -qm examples/request_flow.py SoftwareSmokeScene  # one still
"""
from manim import *
from manim_software import *


# The conversation every scene here tells: a browser asking for a page of
# orders, through a gateway and a service, with a cache miss on the way.
MESSAGES = [
    Message("browser", "gateway", "GET /orders"),
    Message("gateway", "service", "GET /orders"),
    Message("service", "cache", "get orders:42"),
    Message("cache", "service", "miss", kind="reply"),
    Message("service", "db", "SELECT ..."),
    Message("db", "service", "rows", kind="reply"),
    Message("service", "cache", "set orders:42"),
    Message("service", "gateway", "200 OK", kind="reply"),
    Message("gateway", "browser", "200 OK", kind="reply"),
]

PARTICIPANTS = [
    ("browser", "Browser"),
    ("gateway", "Gateway"),
    ("service", "Service"),
    ("cache", "Cache"),
    ("db", "Database"),
]


def build_request_system(style: DiagramStyle | None = None) -> SystemDiagram:
    """
    The system every scene here talks about: a browser calling an API gateway,
    which calls an order service backed by a cache and a database.
    """
    system = SystemDiagram(style=style)
    user = system.add_component("user", Component("User", icon="user", style=style))
    browser = system.add_component("browser", Component("Browser", icon="browser", style=style))
    gateway = system.add_component("gateway", Component("API Gateway", icon="lock", style=style))
    service = system.add_component("service", Component("Order Service", icon="server", style=style))
    cache = system.add_component("cache", Component("Cache", icon="cache", style=style))
    db = system.add_component("db", Component("Database", icon="database", style=style))

    VGroup(user, browser).arrange(DOWN, buff=MED_LARGE_BUFF)
    VGroup(cache, db).arrange(DOWN, buff=1.2)
    service.next_to(VGroup(cache, db), LEFT, buff=1.6)
    gateway.next_to(service, LEFT, buff=1.6)
    VGroup(user, browser).next_to(gateway, LEFT, buff=1.6)

    system.add_container(Container(user, browser, title="Client", style=style))
    system.add_container(Container(gateway, title="Edge", style=style))
    system.add_container(Container(service, cache, db, title="Backend", style=style))
    system.center()

    system.connect("browser", "gateway", label="HTTPS")
    system.connect("gateway", "service", label="gRPC")
    system.connect("service", "cache", route="orthogonal", label="get/set")
    system.connect("service", "db", route="orthogonal", label="SQL")
    return system


def build_sequence(**kwargs) -> SequenceDiagram:
    return SequenceDiagram(PARTICIPANTS, **kwargs)


class RequestFlow(SoftwareThreeDScene):
    """
    The full story: the system appears, a click sends a request through it,
    the same exchange is replayed as a sequence diagram, and the camera
    drops down to look at the database in three dimensions.
    """
    def construct(self):
        # 1. Title. Added, not faded in, so the file's first frame is the title
        # rather than black -- see manim_software.titles.
        open_on(self, TitleCard(
            "A request through the system",
            "browser to gateway to service, with a cache miss on the way",
        ), hold=1.5)

        # 2. The system
        system = build_request_system()
        system.scale_to_fit_width(config.frame_width - 1.5)
        components = system.get_components()
        connectors = system.get_connectors()
        containers = VGroup(*(VGroup(c.frame, c.title) for c in system.containers))
        self.play(LaggedStart(*(FadeIn(c, scale=0.9) for c in components), lag_ratio=0.15, run_time=2.0))
        self.play(LaggedStart(*(FadeIn(c) for c in containers), lag_ratio=0.2, run_time=1.5))
        self.wait(0.5)

        # 3. Wires
        self.play(LaggedStart(*(Create(c) for c in connectors), lag_ratio=0.3, run_time=2.5))
        self.add(system)   # one mobject on the scene list from here on
        self.wait(0.5)

        # 4. The click
        caption = Caption("The user opens their order history").pin(self)
        self.play(FadeIn(caption))
        self.play(Indicate(system["user"].icon, scale_factor=1.15, color=YELLOW))
        self.play(system["browser"].animate.set_state("active"))
        self.wait(0.5)

        # 5-10. The request, hop by hop
        def say(text):
            self.play(FadeOut(caption, run_time=0.25))
            caption.set_text(text)
            self.play(FadeIn(caption, run_time=0.25))

        say("The browser calls the API gateway over HTTPS")
        self.play(message_animation(MESSAGES[0], system, run_time=1.2))
        self.play(system["gateway"].animate.set_state("active"))
        token = Callout(system["gateway"], "token valid", direction=UP, distance=0.5)
        self.play(FadeIn(token))
        self.wait(0.6)

        say("The gateway forwards the call to the order service")
        self.play(FadeOut(token), message_animation(MESSAGES[1], system, run_time=1.2))
        self.play(system["service"].animate.set_state("active"))
        self.wait(0.4)

        say("The service checks the cache first")
        self.play(message_animation(MESSAGES[2], system, run_time=1.0))
        self.play(system["cache"].animate.set_state("error"))
        miss = Callout(system["cache"], "miss", direction=UP, distance=0.4)
        self.play(FadeIn(miss))
        self.play(message_animation(MESSAGES[3], system, run_time=0.8))
        self.wait(0.3)

        say("A cache miss: the service asks the database")
        self.play(FadeOut(miss), message_animation(MESSAGES[4], system, run_time=1.0))
        self.play(system["db"].animate.set_state("active"))
        self.play(message_animation(MESSAGES[5], system, run_time=1.0))
        self.play(system["db"].animate.set_state("done"))
        self.wait(0.3)

        say("...and warms the cache for next time")
        self.play(message_animation(MESSAGES[6], system, run_time=0.9))
        self.play(system["cache"].animate.set_state("done"))
        self.wait(0.3)

        say("The response travels back: 200 OK")
        reply = Packet("200 OK", shape="pill", color=TEAL)
        c_bg, _ = system.get_connector("browser", "gateway")
        c_gs, _ = system.get_connector("gateway", "service")
        self.play(SendAlong(reply, reply_hops([c_bg, c_gs]), hop_time=1.0))
        self.play(
            system["browser"].animate.set_state("done"),
            *(system[k].animate.set_state("idle") for k in ("gateway", "service", "db")),
        )
        self.wait(1.0)

        # 11. The same exchange as a sequence diagram
        say("The same conversation, as a sequence diagram")
        for key in ("browser", "cache", "db"):
            system[key].set_state("idle")
        self.play(system.animate.scale_to_fit_width(6.0).to_edge(LEFT, buff=0.3).shift(0.4 * UP), run_time=1.5)
        seq = build_sequence(spacing=1.35, header_width=1.15, header_height=0.6, row_height=0.42, n_rows=len(MESSAGES))
        seq.next_to(system, RIGHT, buff=0.4).to_edge(UP, buff=0.4)
        self.play(FadeIn(seq.headers, lag_ratio=0.1), Create(seq.lifelines, lag_ratio=0.1), run_time=1.5)
        for msg in MESSAGES:
            self.play(message_animation(msg, system, seq, run_time=0.8))
        self.play(FadeIn(seq.activate("service", 1, 7)), FadeIn(seq.activate("gateway", 0, 8)))
        self.wait(1.5)

        # 12. Down into the database
        say("Zooming in on the database")
        self.play(FadeOut(seq), system.animate.scale_to_fit_width(config.frame_width - 1.5).center(), run_time=1.5)
        db = system["db"]
        spot = Spotlight(db, system)
        self.play(spot)
        db3d = Database3D(label="orders", height=1.3, radius=0.5)
        db3d.move_to(db.get_center()).shift(0.65 * OUT)
        self.play(FadeTransform(db, db3d), run_time=1.0)
        zoom_to(self, db3d, height=6.0, run_time=2.5)
        orbit(self, 50, run_time=3.0)
        self.wait(0.5)

        # 13. Back out
        say("Every hop, every store: one request")
        reset_camera(self, added_anims=[FadeTransform(db3d, db), Unspotlight(spot)], run_time=2.0)
        self.wait(1.0)
        self.play(FadeOut(system), FadeOut(caption))
        self.wait(0.5)


class RequestSequence(Scene):
    """The sequence-diagram view on its own."""
    def construct(self):
        open_on(self, TitleCard("The same request, as a sequence"), hold=1.2)
        seq = build_sequence(spacing=2.6, row_height=0.5, n_rows=len(MESSAGES))
        seq.scale_to_fit_width(config.frame_width - 1.5)
        seq.to_edge(UP, buff=0.6)
        self.play(FadeIn(seq.headers, lag_ratio=0.1), Create(seq.lifelines, lag_ratio=0.1))
        for msg in MESSAGES:
            self.play(message_animation(msg, None, seq, run_time=0.7))
        self.play(FadeIn(seq.activate("service", 1, 7)), FadeIn(seq.activate("gateway", 0, 8)))
        self.wait(1.5)


class DatabaseZoom(SoftwareThreeDScene):
    """The 3D props on their own, on a floor grid, with the camera circling."""
    def construct(self):
        floor = NumberPlane(x_range=(-6, 6), y_range=(-4, 4), faded_line_ratio=1)
        floor.set_stroke(GREY_D, 1, opacity=0.5)
        db = Database3D(label="orders", height=1.6, radius=0.6).shift(0.8 * OUT + 1.5 * LEFT)
        server = Server3D(label="order-service", n_units=4).shift(1.5 * RIGHT)
        self.add(floor, db, server)
        self.set_camera_orientation(phi=65 * DEGREES, theta=-115 * DEGREES, zoom=8 / 7, frame_center=[0, 0, 0.5])
        orbit(self, 40, run_time=3)
        self.wait(0.5)


class SoftwareSmokeScene(Scene):
    """A static frame touching every kind of 2D mobject in the layer."""
    def construct(self):
        system = build_request_system()
        system.scale_to_fit_width(0.62 * config.frame_width)
        system.to_corner(UL, buff=0.3)
        self.add(system)
        system["service"].set_state("active")
        system["cache"].set_state("error")
        system["db"].set_state("done")
        self.add(Callout(system["db"], "primary", direction=DOWN, distance=0.25))

        seq = build_sequence(spacing=1.1, header_width=0.95, header_height=0.5, row_height=0.4, n_rows=6)
        for msg in MESSAGES[:6]:
            seq.message_from(msg)
        seq.activate("service", 1, 5)
        seq.scale_to_fit_width(0.34 * config.frame_width)
        seq.to_corner(UR, buff=0.3)
        self.add(seq)

        icons = VGroup(*(Icon(name) for name in ("queue", "cloud", "lock", "phone", "mail", "file", "nope")))
        icons.arrange(RIGHT, buff=MED_LARGE_BUFF).to_corner(DL, buff=MED_SMALL_BUFF)
        self.add(icons)

        # Every connector variant, and packets sitting on wires
        a = Component("A").scale(0.6)
        b = Component("B").scale(0.6)
        VGroup(a, b).arrange(RIGHT, buff=2.0).next_to(icons, RIGHT, buff=1.0)
        variants = VGroup(
            Connector(a, b, offset=-0.5, label="req"),
            Connector(a, b, offset=0.5, dashed=True, tip="start", label="reply"),
            Connector(a, b, route="arc", path_arc=-1.2, tip="both"),
            Connector(b, b, route="loop", start_dir=UP, label="self"),
        )
        self.add(a, b, variants)
        packet = Packet("GET /orders").move_to(system.connectors[("browser", "gateway")].get_point(0.5))
        pill = Packet("200 OK", shape="pill", color=TEAL).move_to(variants[2].get_point(0.5))
        self.add(packet, pill)
        self.add(Caption("Smoke test", position=RIGHT, buff=MED_SMALL_BUFF, font_size=20))


class PacketTest(Scene):
    """A short clip of packets travelling, for eyeballing Send and SendAlong."""
    def construct(self):
        system = build_request_system()
        system.scale_to_fit_width(config.frame_width - 1)
        self.add(system)
        c1, _ = system.get_connector("browser", "gateway")
        c2, _ = system.get_connector("gateway", "service")
        c3, _ = system.get_connector("service", "db")
        packet = Packet("GET /orders")
        self.play(SendAlong(packet, [c1, c2, c3], fade_out=False))
        system["db"].set_state("active")
        self.wait(0.3)
        rows = Packet("rows", color=TEAL)
        self.play(SendAlong(rows, reply_hops([c1, c2, c3])))
        system["db"].set_state("idle")
        self.play(system["browser"].animate.set_state("done"))
        self.wait(0.5)

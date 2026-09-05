"""
The failure and concurrency vocabulary, one short scene each:

    manim -pql examples/failure_modes.py RetryWithBackoff
    manim -pql examples/failure_modes.py TimeoutAndBreaker
    manim -pql examples/failure_modes.py FanOutFanIn
    manim -pql examples/failure_modes.py QueueUnderLoad
"""
from manim import *
from manim_software import *


def two_boxes(left, right, left_icon, right_icon, gap=5.5):
    a = Component(left, icon=left_icon)
    b = Component(right, icon=right_icon)
    VGroup(a, b).scale(1.25).arrange(RIGHT, buff=gap).shift(0.2 * UP)
    return a, b


class RetryWithBackoff(Scene):
    """Two requests lost on the wire, each retry waiting longer, the third one through."""
    def construct(self):
        browser, service = two_boxes("Browser", "Order Service", "browser", "server")
        wire = Connector(browser, service, label="HTTPS", label_kwargs=dict(direction=DOWN))
        self.add(browser, service, wire)
        caption = Caption("Retries with exponential backoff", position=DOWN)
        self.play(FadeIn(caption))

        self.play(browser.animate.set_state("active"))
        self.play(Retry(Packet("GET /orders"), wire, attempts=3, drop_at=0.55, backoff=0.6))
        self.play(service.animate.set_state("active"))
        self.play(Reply(Packet("200 OK", shape="pill", color=TEAL), wire, fade_out=True))
        self.play(browser.animate.set_state("done"), service.animate.set_state("idle"))
        self.wait(0.8)


class TimeoutAndBreaker(Scene):
    """A slow database, two timeouts, a breaker that trips, fails fast, then half-opens and resets."""
    def construct(self):
        service, db = two_boxes("Order Service", "Database", "server", "database")
        wire = Connector(service, db, label="SQL", label_kwargs=dict(direction=DOWN))
        breaker = CircuitBreaker(wire, proportion=0.68, size=0.6, label="breaker")
        self.add(service, db, wire, breaker)
        caption = Caption("Timeouts open a circuit breaker", position=DOWN)
        self.play(FadeIn(caption))

        def say(text):
            self.play(FadeOut(caption, run_time=0.25))
            caption.set_text(text)
            self.play(FadeIn(caption, run_time=0.25))

        # Two calls go through and never come back
        for _ in range(2):
            self.play(Send(Packet("SELECT ..."), wire, fade_out=True, run_time=0.9))
            self.play(db.animate.set_state("error"), Timeout(service, wait=1.0))
        say("Two timeouts trip the breaker")
        self.play(TripBreaker(breaker))
        self.wait(0.3)

        # Now calls are rejected at the breaker without waiting
        say("Open: calls fail fast at the breaker")
        for _ in range(2):
            self.play(Drop(Packet("SELECT ..."), wire, at=breaker, run_time=0.7))
        self.wait(0.3)

        # After a while, one probe is allowed through
        say("Half-open: one probe is allowed through")
        self.play(breaker.animate.set_state("half_open"), db.animate.set_state("idle"))
        self.play(Send(Packet("SELECT 1"), wire, fade_out=True, run_time=0.9))
        self.play(db.animate.set_state("active"))
        self.play(Reply(Packet("ok", color=TEAL), wire, fade_out=True, run_time=0.9))
        say("It answers, so the breaker closes")
        self.play(ResetBreaker(breaker), db.animate.set_state("done"))
        self.wait(0.8)


class FanOutFanIn(Scene):
    """One request fanned out to three services, three answers fanned back into one."""
    def construct(self):
        gateway = Component("API Gateway", icon="lock")
        services = VGroup(*(
            Component(name, icon="server") for name in ("Search", "Pricing", "Inventory")
        )).arrange(DOWN, buff=0.5)
        gateway.next_to(services, LEFT, buff=4.0)
        VGroup(gateway, services).scale(1.15).center().shift(0.2 * UP)
        wires = [Connector(gateway, svc, route="orthogonal") for svc in services]
        self.add(gateway, services, *wires)
        caption = Caption("Fan-out, then fan-in", position=DOWN)
        self.play(FadeIn(caption))

        self.play(gateway.animate.set_state("active"))
        fan_out = FanOut(Packet("GET /product/42"), wires, lag_ratio=0.15)
        self.play(fan_out)
        self.play(*(svc.animate.set_state("active") for svc in services))
        self.wait(0.4)
        fan_in = FanIn(Packet("part", color=TEAL), wires, merged="200 OK", lag_ratio=0.2)
        self.play(fan_in, *(svc.animate.set_state("done") for svc in services))
        self.play(fan_in.merged.animate.next_to(gateway, UP, buff=SMALL_BUFF))
        self.play(gateway.animate.set_state("done"))
        self.wait(0.8)


class QueueUnderLoad(Scene):
    """A producer outpacing its consumer: the queue fills, turns amber, then red, and starts rejecting."""
    def construct(self):
        producer = Component("API", icon="server")
        queue = MessageQueue(capacity=8, slot_size=0.42, gap=0.08, label="jobs")
        worker = Component("Worker", icon="server")
        VGroup(producer, queue, worker).arrange(RIGHT, buff=1.6).scale(1.15).shift(0.2 * UP)
        inbound = Connector(producer, queue, label="publish", label_kwargs=dict(direction=UP))
        outbound = Connector(queue, worker, label="consume", label_kwargs=dict(direction=UP))
        self.add(producer, queue, worker, inbound, outbound)
        caption = Caption("Queue depth under load", position=DOWN)
        self.play(FadeIn(caption))

        # Ten jobs arrive at one pace; the worker takes three at a slower one
        arrivals = LaggedStart(
            *(Enqueue(queue, Packet(), from_point=producer, run_time=0.5) for _ in range(11)),
            lag_ratio=0.55,
        )
        departures = LaggedStart(
            *(Dequeue(queue, to=worker, run_time=0.6) for _ in range(3)),
            lag_ratio=1.2,
        )
        self.play(producer.animate.set_state("active"), worker.animate.set_state("active"))
        self.play(arrivals, departures)
        self.wait(0.5)
        self.play(FadeIn(Callout(queue, "full: publishes rejected", direction=UP, distance=0.5)))
        self.wait(1.0)

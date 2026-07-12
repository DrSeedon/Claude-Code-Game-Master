"""Unit tests for the in-memory pub/sub broker.

No pytest-asyncio in this project — asyncio.Queue methods used here (get_nowait,
put_nowait, qsize, empty) are all synchronous, so plain sync tests suffice.
"""

import asyncio

from backend.live_broker import LiveBroker


def test_subscribe_returns_empty_queue():
    broker = LiveBroker()
    q = broker.subscribe("camp-a")

    assert q.empty()


def test_publish_delivers_to_subscriber():
    broker = LiveBroker()
    q = broker.subscribe("camp-a")

    broker.publish("camp-a", {"type": "text", "content": "hello"})

    event = q.get_nowait()
    assert event == {"type": "text", "content": "hello"}


def test_publish_does_not_leak_across_campaigns():
    broker = LiveBroker()
    q_a = broker.subscribe("camp-a")
    q_b = broker.subscribe("camp-b")

    broker.publish("camp-a", {"type": "text", "content": "only for a"})

    assert q_a.get_nowait()["content"] == "only for a"
    assert q_b.empty()


def test_publish_reaches_multiple_subscribers():
    broker = LiveBroker()
    q1 = broker.subscribe("camp-a")
    q2 = broker.subscribe("camp-a")

    broker.publish("camp-a", {"type": "done"})

    assert q1.get_nowait() == {"type": "done"}
    assert q2.get_nowait() == {"type": "done"}


def test_publish_to_campaign_with_no_subscribers_is_noop():
    broker = LiveBroker()

    broker.publish("ghost-campaign", {"type": "text", "content": "nobody home"})  # must not raise


def test_unsubscribe_stops_delivery():
    broker = LiveBroker()
    q = broker.subscribe("camp-a")
    broker.unsubscribe("camp-a", q)

    broker.publish("camp-a", {"type": "text", "content": "too late"})

    assert q.empty()


def test_unsubscribe_unknown_queue_is_noop():
    broker = LiveBroker()
    other_queue = asyncio.Queue()

    broker.unsubscribe("camp-a", other_queue)  # must not raise


def test_full_queue_drops_oldest():
    broker = LiveBroker()
    q = broker.subscribe("camp-a")

    # Fill beyond maxsize (256) — the oldest entries should be dropped, not raise
    for i in range(300):
        broker.publish("camp-a", {"type": "text", "content": str(i)})

    assert q.qsize() <= 256
    first = q.get_nowait()
    assert int(first["content"]) > 0  # earliest items were dropped

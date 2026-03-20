# SPDX-License-Identifier: MIT
# Copyright (c) 2026 cutient

"""Benchmark: aiodeque.deque vs collections.deque vs asyncio.Queue."""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections import deque as stdlib_deque

from aiodeque import deque

ITEMS = 500_000
MAXSIZE = 1_000

# -- fake data generators (generic event stream) ------------------------------

_ENTITY_IDS = [f"entity-{i:04d}" for i in range(20)]
_CHANNEL_IDS = [f"0x{uuid.uuid4().hex}" for _ in range(10)]
_DIRECTIONS = ("IN", "OUT")


def _ts() -> str:
    return str(int(time.time() * 1000))


def _value() -> str:
    return f"{random.randint(1, 99) / 100:.2f}"


def _quantity() -> str:
    return f"{random.randint(1, 50000)}.{random.randint(0, 99)}"


def _hash() -> str:
    return uuid.uuid4().hex


def gen_snapshot() -> dict:
    entity_id = random.choice(_ENTITY_IDS)
    return {
        "event_type": "snapshot",
        "timestamp": _ts(),
        "channel": random.choice(_CHANNEL_IDS),
        "entity_id": entity_id,
        "highs": [
            {"value": _value(), "quantity": _quantity()}
            for _ in range(random.randint(5, 20))
        ],
        "lows": [
            {"value": _value(), "quantity": _quantity()}
            for _ in range(random.randint(5, 20))
        ],
        "last_value": _value(),
        "resolution": "0.01",
        "hash": _hash(),
        "recv_timestamp": time.time(),
        "sha256hash": _hash(),
    }


def gen_update() -> dict:
    n = random.randint(1, 5)
    return {
        "event_type": "update",
        "timestamp": _ts(),
        "channel": random.choice(_CHANNEL_IDS),
        "changes": [
            {
                "entity_id": random.choice(_ENTITY_IDS),
                "value": _value(),
                "quantity": _quantity(),
                "direction": random.choice(_DIRECTIONS),
                "hash": _hash(),
                "high": _value(),
                "low": _value(),
            }
            for _ in range(n)
        ],
        "recv_timestamp": time.time(),
        "sha256hash": _hash(),
    }


def gen_summary() -> dict:
    lo = random.randint(1, 49)
    hi = lo + random.randint(1, 10)
    return {
        "event_type": "summary",
        "timestamp": _ts(),
        "channel": random.choice(_CHANNEL_IDS),
        "entity_id": random.choice(_ENTITY_IDS),
        "high": f"{hi / 100:.2f}",
        "low": f"{lo / 100:.2f}",
        "range": f"{(hi - lo) / 100:.2f}",
        "recv_timestamp": time.time(),
        "sha256hash": _hash(),
    }


def gen_tick() -> dict:
    return {
        "event_type": "tick",
        "timestamp": _ts(),
        "channel": random.choice(_CHANNEL_IDS),
        "entity_id": random.choice(_ENTITY_IDS),
        "value": _value(),
        "quantity": _quantity(),
        "direction": random.choice(_DIRECTIONS),
        "priority": str(random.choice([0, 1, 2])),
        "ref_hash": f"0x{_hash()}",
        "recv_timestamp": time.time(),
        "sha256hash": _hash(),
    }


# Weighted distribution: updates and ticks are most frequent
_GENERATORS = [
    (gen_update, 40),
    (gen_tick, 30),
    (gen_summary, 20),
    (gen_snapshot, 10),
]
_GEN_FNS, _GEN_WEIGHTS = zip(*_GENERATORS)


def gen_message() -> dict:
    return random.choices(_GEN_FNS, weights=_GEN_WEIGHTS, k=1)[0]()


def pregenerate(n: int) -> list[dict]:
    """Pre-generate messages so generation cost doesn't pollute benchmarks."""
    return [gen_message() for _ in range(n)]


# -- helpers -------------------------------------------------------------------

SENTINEL = {"event_type": "__sentinel__"}


def _header(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def _report(name: str, items: int, elapsed: float) -> float:
    mps = items / elapsed
    print(f"  {name:.<50s} {mps:>12,.0f} msg/s")
    return elapsed


def _compare(name_a: str, t_a: float, name_b: str, t_b: float) -> None:
    ratio = t_b / t_a
    if ratio >= 1:
        print(f"\n  => {name_a} is {ratio:.2f}x faster than {name_b}")
    else:
        print(f"\n  => {name_a} is {1 / ratio:.2f}x slower than {name_b}")


# -- scenarios -----------------------------------------------------------------


async def bench_sync_overhead(msgs: list[dict]) -> None:
    _header(f"sync append  |  {ITEMS:,} items, maxlen={MAXSIZE}")

    ad: deque[dict] = deque(maxlen=MAXSIZE)
    t0 = time.perf_counter()
    for m in msgs:
        ad.append(m)
    t_aio = time.perf_counter() - t0
    _report("aiodeque.deque.append", ITEMS, t_aio)

    sd: stdlib_deque[dict] = stdlib_deque(maxlen=MAXSIZE)
    t0 = time.perf_counter()
    for m in msgs:
        sd.append(m)
    t_std = time.perf_counter() - t0
    _report("collections.deque.append", ITEMS, t_std)

    _compare("aiodeque", t_aio, "collections.deque", t_std)


async def bench_sync_nowait(msgs: list[dict]) -> None:
    _header(f"sync append+popleft  |  {ITEMS:,} items, maxlen={MAXSIZE}")

    ad: deque[dict] = deque(maxlen=MAXSIZE)
    t0 = time.perf_counter()
    for m in msgs:
        ad.append(m)
        if len(ad) > 1:
            ad.popleft()
    t_ad = time.perf_counter() - t0
    _report("aiodeque append+popleft", ITEMS, t_ad)

    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=MAXSIZE)
    t0 = time.perf_counter()
    for m in msgs:
        if q.full():
            q.get_nowait()
        q.put_nowait(m)
    t_q = time.perf_counter() - t0
    _report("asyncio.Queue put_nowait+get_nowait", ITEMS, t_q)

    _compare("aiodeque", t_ad, "asyncio.Queue", t_q)


async def bench_async_put_get(msgs: list[dict]) -> None:
    _header(f"async append+popleft  |  {ITEMS:,} items, maxlen={MAXSIZE}")

    ad: deque[dict] = deque(maxlen=MAXSIZE)

    async def _ad_producer() -> None:
        for m in msgs:
            await ad.aappend(m)

    async def _ad_consumer() -> None:
        for _ in range(len(msgs)):
            await ad.apopleft()

    t0 = time.perf_counter()
    await asyncio.gather(_ad_producer(), _ad_consumer())
    t_ad = time.perf_counter() - t0
    _report("aiodeque aappend+apopleft", ITEMS, t_ad)

    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=MAXSIZE)

    async def _q_producer() -> None:
        for m in msgs:
            await q.put(m)

    async def _q_consumer() -> None:
        for _ in range(len(msgs)):
            await q.get()

    t0 = time.perf_counter()
    await asyncio.gather(_q_producer(), _q_consumer())
    t_q = time.perf_counter() - t0
    _report("asyncio.Queue put+get", ITEMS, t_q)

    _compare("aiodeque", t_ad, "asyncio.Queue", t_q)


async def bench_sync_overhead_unbounded(msgs: list[dict]) -> None:
    _header(f"sync append (unbounded)  |  {ITEMS:,} items")

    ad: deque[dict] = deque()
    t0 = time.perf_counter()
    for m in msgs:
        ad.append(m)
    t_aio = time.perf_counter() - t0
    _report("aiodeque.deque.append", ITEMS, t_aio)

    sd: stdlib_deque[dict] = stdlib_deque()
    t0 = time.perf_counter()
    for m in msgs:
        sd.append(m)
    t_std = time.perf_counter() - t0
    _report("collections.deque.append", ITEMS, t_std)

    _compare("aiodeque", t_aio, "collections.deque", t_std)


async def bench_sync_nowait_unbounded(msgs: list[dict]) -> None:
    _header(f"sync append+popleft (unbounded)  |  {ITEMS:,} items")

    ad: deque[dict] = deque()
    t0 = time.perf_counter()
    for m in msgs:
        ad.append(m)
    for _ in range(len(msgs)):
        ad.popleft()
    t_ad = time.perf_counter() - t0
    _report("aiodeque append+popleft", ITEMS, t_ad)

    q: asyncio.Queue[dict] = asyncio.Queue()
    t0 = time.perf_counter()
    for m in msgs:
        q.put_nowait(m)
    for _ in range(len(msgs)):
        q.get_nowait()
    t_q = time.perf_counter() - t0
    _report("asyncio.Queue put_nowait+get_nowait", ITEMS, t_q)

    _compare("aiodeque", t_ad, "asyncio.Queue", t_q)


async def bench_async_put_get_unbounded(msgs: list[dict]) -> None:
    _header(f"async append+popleft (unbounded)  |  {ITEMS:,} items")

    ad: deque[dict] = deque()

    async def _ad_producer() -> None:
        for m in msgs:
            await ad.aappend(m)

    async def _ad_consumer() -> None:
        for _ in range(len(msgs)):
            await ad.apopleft()

    t0 = time.perf_counter()
    await asyncio.gather(_ad_producer(), _ad_consumer())
    t_ad = time.perf_counter() - t0
    _report("aiodeque aappend+apopleft", ITEMS, t_ad)

    q: asyncio.Queue[dict] = asyncio.Queue()

    async def _q_producer() -> None:
        for m in msgs:
            await q.put(m)

    async def _q_consumer() -> None:
        for _ in range(len(msgs)):
            await q.get()

    t0 = time.perf_counter()
    await asyncio.gather(_q_producer(), _q_consumer())
    t_q = time.perf_counter() - t0
    _report("asyncio.Queue put+get", ITEMS, t_q)

    _compare("aiodeque", t_ad, "asyncio.Queue", t_q)


# -- main ----------------------------------------------------------------------


async def main() -> None:
    print(f"Pre-generating {ITEMS:,} event stream messages...")
    msgs = pregenerate(ITEMS)
    print("Done.\n")

    await bench_sync_overhead(msgs)
    await bench_sync_nowait(msgs)
    await bench_async_put_get(msgs)

    await bench_sync_overhead_unbounded(msgs)
    await bench_sync_nowait_unbounded(msgs)
    await bench_async_put_get_unbounded(msgs)


if __name__ == "__main__":
    random.seed(42)
    asyncio.run(main())

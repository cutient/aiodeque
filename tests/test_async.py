# SPDX-License-Identifier: MIT
# Copyright (c) 2026 cutient

"""Tests for async methods on aiodeque.deque — full edge-case coverage."""

from __future__ import annotations

import asyncio

import pytest

from aiodeque import deque

TIMEOUT = 2.0  # global safety timeout for tests


# =========================================================================
#  apop
# =========================================================================


class TestApop:
    async def test_nonempty_returns_rightmost(self):
        d = deque([1, 2, 3])
        assert await d.apop() == 3
        assert list(d) == [1, 2]

    async def test_single_element(self):
        d = deque([42])
        assert await d.apop() == 42
        assert len(d) == 0

    async def test_drain_all(self):
        d = deque([1, 2, 3])
        items = [await d.apop(), await d.apop(), await d.apop()]
        assert items == [3, 2, 1]
        assert len(d) == 0

    async def test_waits_when_empty(self):
        d: deque[int] = deque()
        result: list[int] = []

        async def consumer():
            result.append(await d.apop())

        async def producer():
            await asyncio.sleep(0.01)
            await d.aappend(42)

        await asyncio.gather(consumer(), producer())
        assert result == [42]

    async def test_cancellation(self):
        d: deque[int] = deque()
        task = asyncio.create_task(d.apop())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_cancellation_no_leak(self):
        """Cancelled waiter doesn't leave stale futures."""
        d: deque[int] = deque()
        task = asyncio.create_task(d.apop())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # getters queue should be empty or None
        assert d._getters is None or len(d._getters) == 0

    async def test_timeout(self):
        d: deque[int] = deque()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(d.apop(), timeout=0.02)

    async def test_timeout_no_leak(self):
        d: deque[int] = deque()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(d.apop(), timeout=0.02)
        assert d._getters is None or len(d._getters) == 0

    async def test_wakes_putters(self):
        """apop on a full deque should wake a blocked aappend."""
        d = deque([1, 2, 3], maxlen=3)
        appended = False

        async def appender():
            nonlocal appended
            await d.aappend(4)
            appended = True

        task = asyncio.create_task(appender())
        await asyncio.sleep(0.01)
        assert not appended

        val = await d.apop()
        assert val == 3
        await asyncio.sleep(0.01)
        assert appended
        assert 4 in d
        await task

    async def test_with_maxlen(self):
        d = deque([10, 20, 30], maxlen=5)
        assert await d.apop() == 30
        assert d.maxlen == 5


# =========================================================================
#  apopleft
# =========================================================================


class TestApopleft:
    async def test_nonempty_returns_leftmost(self):
        d = deque([1, 2, 3])
        assert await d.apopleft() == 1
        assert list(d) == [2, 3]

    async def test_single_element(self):
        d = deque([42])
        assert await d.apopleft() == 42
        assert len(d) == 0

    async def test_drain_all(self):
        d = deque([1, 2, 3])
        items = [await d.apopleft(), await d.apopleft(), await d.apopleft()]
        assert items == [1, 2, 3]

    async def test_waits_when_empty(self):
        d: deque[int] = deque()
        result: list[int] = []

        async def consumer():
            result.append(await d.apopleft())

        async def producer():
            await asyncio.sleep(0.01)
            await d.aappend(99)

        await asyncio.gather(consumer(), producer())
        assert result == [99]

    async def test_cancellation(self):
        d: deque[int] = deque()
        task = asyncio.create_task(d.apopleft())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_timeout(self):
        d: deque[int] = deque()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(d.apopleft(), timeout=0.02)

    async def test_cancellation_no_leak(self):
        """Cancelled waiter doesn't leave stale futures."""
        d: deque[int] = deque()
        task = asyncio.create_task(d.apopleft())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert d._getters is None or len(d._getters) == 0

    async def test_wakes_putters(self):
        d = deque([1, 2, 3], maxlen=3)
        appended = False

        async def appender():
            nonlocal appended
            await d.aappendleft(0)
            appended = True

        task = asyncio.create_task(appender())
        await asyncio.sleep(0.01)
        assert not appended

        await d.apopleft()
        await asyncio.sleep(0.01)
        assert appended
        await task


# =========================================================================
#  Getter FIFO ordering
# =========================================================================


class TestGetterFIFO:
    async def test_multiple_apopleft_waiters_fifo(self):
        d: deque[int] = deque()
        results: list[tuple[int, int]] = []

        async def consumer(idx: int):
            val = await d.apopleft()
            results.append((idx, val))

        tasks = [asyncio.create_task(consumer(i)) for i in range(3)]
        await asyncio.sleep(0.01)

        for v in [10, 20, 30]:
            await d.aappend(v)
            await asyncio.sleep(0.001)

        await asyncio.gather(*tasks)
        assert results == [(0, 10), (1, 20), (2, 30)]

    async def test_multiple_apop_waiters_fifo(self):
        d: deque[int] = deque()
        results: list[tuple[int, int]] = []

        async def consumer(idx: int):
            val = await d.apop()
            results.append((idx, val))

        tasks = [asyncio.create_task(consumer(i)) for i in range(3)]
        await asyncio.sleep(0.01)

        for v in [10, 20, 30]:
            await d.aappend(v)
            await asyncio.sleep(0.001)

        await asyncio.gather(*tasks)
        assert results == [(0, 10), (1, 20), (2, 30)]

    async def test_cancel_middle_waiter(self):
        """Cancelling middle waiter doesn't break others."""
        d: deque[int] = deque()
        results: list[int] = []

        async def consumer():
            results.append(await d.apopleft())

        t1 = asyncio.create_task(consumer())
        t2 = asyncio.create_task(consumer())
        t3 = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)

        t2.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t2

        await d.aappend(10)
        await d.aappend(20)
        await asyncio.sleep(0.01)

        await asyncio.gather(t1, t3)
        assert results == [10, 20]


# =========================================================================
#  aappend
# =========================================================================


class TestAappend:
    async def test_unbounded_never_blocks(self):
        d: deque[int] = deque()
        for i in range(100):
            await d.aappend(i)
        assert len(d) == 100

    async def test_waits_when_full(self):
        d = deque([1, 2, 3], maxlen=3)
        appended = False

        async def appender():
            nonlocal appended
            await d.aappend(4)
            appended = True

        task = asyncio.create_task(appender())
        await asyncio.sleep(0.01)
        assert not appended

        await d.apopleft()
        await asyncio.sleep(0.01)
        assert appended
        assert list(d) == [2, 3, 4]
        await task

    async def test_cancellation_preserves_contents(self):
        d = deque([1, 2, 3], maxlen=3)
        task = asyncio.create_task(d.aappend(4))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert list(d) == [1, 2, 3]

    async def test_timeout_when_full(self):
        d = deque([1, 2, 3], maxlen=3)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(d.aappend(4), timeout=0.02)
        assert list(d) == [1, 2, 3]

    async def test_cancellation_no_leak(self):
        """Cancelled putter doesn't leave stale futures."""
        d = deque([1, 2, 3], maxlen=3)
        task = asyncio.create_task(d.aappend(4))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert d._putters is None or len(d._putters) == 0

    async def test_wakes_getter(self):
        """aappend should wake a waiting apopleft."""
        d: deque[int] = deque()
        result: list[int] = []

        task = asyncio.create_task(self._consume_one(d, result))
        await asyncio.sleep(0.01)
        assert result == []

        await d.aappend(42)
        await asyncio.sleep(0.01)
        assert result == [42]
        await task

    async def test_maxlen_one(self):
        d: deque[int] = deque(maxlen=1)
        await d.aappend(1)
        assert list(d) == [1]

        appended = False

        async def appender():
            nonlocal appended
            await d.aappend(2)
            appended = True

        task = asyncio.create_task(appender())
        await asyncio.sleep(0.01)
        assert not appended

        val = await d.apopleft()
        assert val == 1
        await asyncio.sleep(0.01)
        assert appended
        assert list(d) == [2]
        await task

    @staticmethod
    async def _consume_one(d: deque[int], out: list[int]):
        out.append(await d.apopleft())


# =========================================================================
#  aappendleft
# =========================================================================


class TestAappendleft:
    async def test_unbounded(self):
        d: deque[int] = deque()
        await d.aappendleft(1)
        await d.aappendleft(2)
        assert list(d) == [2, 1]

    async def test_waits_when_full(self):
        d = deque([1, 2, 3], maxlen=3)
        appended = False

        async def appender():
            nonlocal appended
            await d.aappendleft(0)
            appended = True

        task = asyncio.create_task(appender())
        await asyncio.sleep(0.01)
        assert not appended

        await d.apop()
        await asyncio.sleep(0.01)
        assert appended
        assert list(d) == [0, 1, 2]
        await task

    async def test_cancellation(self):
        d = deque([1, 2, 3], maxlen=3)
        task = asyncio.create_task(d.aappendleft(0))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert list(d) == [1, 2, 3]

    async def test_timeout(self):
        d = deque([1, 2, 3], maxlen=3)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(d.aappendleft(0), timeout=0.02)

    async def test_cancellation_no_leak(self):
        """Cancelled putter doesn't leave stale futures."""
        d = deque([1, 2, 3], maxlen=3)
        task = asyncio.create_task(d.aappendleft(0))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert d._putters is None or len(d._putters) == 0

    async def test_wakes_apop(self):
        """aappendleft should wake a waiting apop."""
        d: deque[int] = deque()
        result: list[int] = []

        async def consumer():
            result.append(await d.apop())

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)
        assert result == []

        await d.aappendleft(42)
        await asyncio.sleep(0.01)
        assert result == [42]
        await task


# =========================================================================
#  Putter FIFO ordering
# =========================================================================


class TestPutterFIFO:
    async def test_multiple_aappend_waiters_fifo(self):
        d = deque([0], maxlen=1)
        order: list[int] = []

        async def appender(val: int):
            await d.aappend(val)
            order.append(val)

        tasks = [asyncio.create_task(appender(i)) for i in range(1, 4)]
        await asyncio.sleep(0.01)

        for _ in range(3):
            await d.apopleft()
            await asyncio.sleep(0.001)

        await asyncio.gather(*tasks)
        assert order == [1, 2, 3]

    async def test_cancel_middle_putter(self):
        d = deque([0], maxlen=1)
        order: list[int] = []

        async def appender(val: int):
            await d.aappend(val)
            order.append(val)

        t1 = asyncio.create_task(appender(1))
        t2 = asyncio.create_task(appender(2))
        t3 = asyncio.create_task(appender(3))
        await asyncio.sleep(0.01)

        t2.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t2

        # drain t1 and t3
        await d.apopleft()
        await asyncio.sleep(0.001)
        await d.apopleft()
        await asyncio.sleep(0.001)

        await asyncio.gather(t1, t3)
        assert order == [1, 3]


# =========================================================================
#  aextend
# =========================================================================


class TestAextend:
    async def test_basic(self):
        d: deque[int] = deque()
        await d.aextend([1, 2, 3])
        assert list(d) == [1, 2, 3]

    async def test_empty_iterable(self):
        d: deque[int] = deque([1])
        await d.aextend([])
        assert list(d) == [1]

    async def test_generator(self):
        d: deque[int] = deque()
        await d.aextend(x for x in range(3))
        assert list(d) == [0, 1, 2]

    async def test_waits_per_item(self):
        d = deque([1, 2], maxlen=3)
        extended = False

        async def extender():
            nonlocal extended
            await d.aextend([3, 4])
            extended = True

        task = asyncio.create_task(extender())
        await asyncio.sleep(0.01)
        assert 3 in d
        assert not extended

        await d.apopleft()
        await asyncio.sleep(0.01)
        assert extended
        await task

    async def test_tuple_input(self):
        """Tuple input hits isinstance fast path without list conversion."""
        d: deque[int] = deque()
        await d.aextend((1, 2, 3))
        assert list(d) == [1, 2, 3]

    async def test_concurrent_bounded(self):
        """Two concurrent aextend calls + consumer — no data loss."""
        d: deque[int] = deque(maxlen=2)
        consumed: list[int] = []

        async def producer_a():
            await d.aextend([1, 2, 3, 4, 5])

        async def producer_b():
            await d.aextend([10, 20, 30, 40, 50])

        async def consumer():
            for _ in range(10):
                consumed.append(await d.apopleft())

        await asyncio.gather(producer_a(), producer_b(), consumer())
        assert sorted(consumed) == [1, 2, 3, 4, 5, 10, 20, 30, 40, 50]

    async def test_cancellation_midway(self):
        """Cancel during multi-item extend — items added so far remain."""
        d: deque[int] = deque(maxlen=2)
        await d.aappend(0)  # [0], 1 slot free

        async def extender():
            await d.aextend([1, 2, 3])  # 1 fits, 2 blocks

        task = asyncio.create_task(extender())
        await asyncio.sleep(0.01)
        # item 1 should be in, waiting on item 2
        assert list(d) == [0, 1]

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert list(d) == [0, 1]  # partial progress preserved


# =========================================================================
#  aextendleft
# =========================================================================


class TestAextendleft:
    async def test_basic(self):
        d: deque[int] = deque([4])
        await d.aextendleft([3, 2, 1])
        assert list(d) == [1, 2, 3, 4]

    async def test_empty_iterable(self):
        d: deque[int] = deque([1])
        await d.aextendleft([])
        assert list(d) == [1]

    async def test_generator(self):
        d: deque[int] = deque()
        await d.aextendleft(x for x in range(3))
        assert list(d) == [2, 1, 0]

    async def test_waits_per_item(self):
        d = deque([1, 2], maxlen=3)
        extended = False

        async def extender():
            nonlocal extended
            await d.aextendleft([3, 4])
            extended = True

        task = asyncio.create_task(extender())
        await asyncio.sleep(0.01)
        assert 3 in d
        assert not extended

        await d.apop()
        await asyncio.sleep(0.01)
        assert extended
        await task

    async def test_cancellation_midway(self):
        d: deque[int] = deque(maxlen=2)
        await d.aappend(0)

        async def extender():
            await d.aextendleft([1, 2, 3])

        task = asyncio.create_task(extender())
        await asyncio.sleep(0.01)
        assert 1 in d

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(d) == 2


# =========================================================================
#  ainsert
# =========================================================================


class TestAinsert:
    async def test_unbounded(self):
        d = deque([1, 3])
        await d.ainsert(1, 2)
        assert list(d) == [1, 2, 3]

    async def test_at_beginning(self):
        d = deque([2, 3])
        await d.ainsert(0, 1)
        assert list(d) == [1, 2, 3]

    async def test_at_end(self):
        d = deque([1, 2])
        await d.ainsert(100, 3)
        assert list(d) == [1, 2, 3]

    async def test_negative_index(self):
        d = deque([1, 3])
        await d.ainsert(-1, 2)
        assert list(d) == [1, 2, 3]

    async def test_empty(self):
        d: deque[int] = deque()
        await d.ainsert(0, 1)
        assert list(d) == [1]

    async def test_waits_when_full(self):
        d = deque([1, 2, 3], maxlen=3)
        inserted = False

        async def inserter():
            nonlocal inserted
            await d.ainsert(1, 99)
            inserted = True

        task = asyncio.create_task(inserter())
        await asyncio.sleep(0.01)
        assert not inserted

        await d.apop()
        await asyncio.sleep(0.01)
        assert inserted
        assert list(d) == [1, 99, 2]
        await task

    async def test_cancellation(self):
        d = deque([1, 2, 3], maxlen=3)
        task = asyncio.create_task(d.ainsert(1, 99))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert list(d) == [1, 2, 3]

    async def test_timeout(self):
        d = deque([1, 2, 3], maxlen=3)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(d.ainsert(1, 99), timeout=0.02)
        assert list(d) == [1, 2, 3]

    async def test_wakes_getter(self):
        d: deque[int] = deque()
        result: list[int] = []

        async def consumer():
            result.append(await d.apopleft())

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)
        assert result == []

        await d.ainsert(0, 42)
        await asyncio.sleep(0.01)
        assert result == [42]
        await task

    async def test_wakes_apop(self):
        """ainsert should wake a waiting apop."""
        d: deque[int] = deque()
        result: list[int] = []

        async def consumer():
            result.append(await d.apop())

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)
        assert result == []

        await d.ainsert(0, 42)
        await asyncio.sleep(0.01)
        assert result == [42]
        await task


# =========================================================================
#  Sync mutations don't wake async waiters
# =========================================================================


class TestSyncDoesNotWake:
    async def test_sync_append_doesnt_wake_getter(self):
        d: deque[int] = deque()
        woken = False

        async def waiter():
            nonlocal woken
            await d.apopleft()
            woken = True

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)

        d.append(1)  # sync — should NOT wake waiter
        await asyncio.sleep(0.02)
        assert not woken
        assert list(d) == [1]  # item still there, nobody consumed it

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_sync_popleft_doesnt_wake_putter(self):
        d = deque([1, 2, 3], maxlen=3)
        woken = False

        async def waiter():
            nonlocal woken
            await d.aappend(4)
            woken = True

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)

        d.popleft()  # sync — should NOT wake waiter
        await asyncio.sleep(0.02)
        assert not woken

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_sync_appendleft_doesnt_wake_apop(self):
        d: deque[int] = deque()
        woken = False

        async def waiter():
            nonlocal woken
            await d.apop()
            woken = True

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)

        d.appendleft(1)  # sync — should NOT wake waiter
        await asyncio.sleep(0.02)
        assert not woken
        assert list(d) == [1]

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_sync_pop_doesnt_wake_aappendleft(self):
        d = deque([1, 2, 3], maxlen=3)
        woken = False

        async def waiter():
            nonlocal woken
            await d.aappendleft(0)
            woken = True

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)

        d.pop()  # sync — should NOT wake waiter
        await asyncio.sleep(0.02)
        assert not woken

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# =========================================================================
#  Maxlen edge cases
# =========================================================================


class TestMaxlenEdges:
    async def test_maxlen_one_pingpong(self):
        """Producer and consumer ping-pong through maxlen=1 deque."""
        d: deque[int] = deque(maxlen=1)
        n = 50
        consumed: list[int] = []

        async def producer():
            for i in range(n):
                await d.aappend(i)

        async def consumer():
            for _ in range(n):
                consumed.append(await d.apopleft())

        await asyncio.gather(producer(), consumer())
        assert consumed == list(range(n))

    async def test_maxlen_none_aappend_never_blocks(self):
        d: deque[int] = deque()
        for i in range(1000):
            await d.aappend(i)
        assert len(d) == 1000

    async def test_maxlen_none_aappendleft_never_blocks(self):
        d: deque[int] = deque()
        for i in range(1000):
            await d.aappendleft(i)
        assert len(d) == 1000

    async def test_maxlen_none_ainsert_never_blocks(self):
        d: deque[int] = deque()
        for i in range(100):
            await d.ainsert(0, i)
        assert len(d) == 100

    async def test_maxlen_zero_aappend(self):
        """aappend on maxlen=0 should silently discard, not block."""
        d: deque[int] = deque(maxlen=0)
        await asyncio.wait_for(d.aappend(1), timeout=0.1)
        assert len(d) == 0

    async def test_maxlen_zero_aappendleft(self):
        d: deque[int] = deque(maxlen=0)
        await asyncio.wait_for(d.aappendleft(1), timeout=0.1)
        assert len(d) == 0

    async def test_maxlen_zero_ainsert(self):
        d: deque[int] = deque(maxlen=0)
        await asyncio.wait_for(d.ainsert(0, 1), timeout=0.1)
        assert len(d) == 0

    async def test_maxlen_zero_aextend(self):
        d: deque[int] = deque(maxlen=0)
        await asyncio.wait_for(d.aextend([1, 2, 3]), timeout=0.1)
        assert len(d) == 0


# =========================================================================
#  evict=True
# =========================================================================


class TestAappendEvict:
    async def test_evicts_leftmost_when_full(self):
        d = deque([1, 2, 3], maxlen=3)
        evicted = await d.aappend(4, evict=True)
        assert evicted == 1
        assert list(d) == [2, 3, 4]

    async def test_no_eviction_when_not_full(self):
        d: deque[int] = deque([1, 2], maxlen=3)
        evicted = await d.aappend(3, evict=True)
        assert evicted is None
        assert list(d) == [1, 2, 3]

    async def test_no_eviction_unbounded(self):
        d: deque[int] = deque([1, 2])
        evicted = await d.aappend(3, evict=True)
        assert evicted is None
        assert list(d) == [1, 2, 3]

    async def test_maxlen_zero(self):
        d: deque[int] = deque(maxlen=0)
        evicted = await d.aappend(1, evict=True)
        assert evicted is None
        assert len(d) == 0

    async def test_maxlen_one(self):
        d = deque([1], maxlen=1)
        evicted = await d.aappend(2, evict=True)
        assert evicted == 1
        assert list(d) == [2]

    async def test_never_blocks(self):
        """evict=True must not block even when the deque is full."""
        d = deque([1, 2, 3], maxlen=3)
        evicted = await asyncio.wait_for(d.aappend(4, evict=True), timeout=0.1)
        assert evicted == 1

    async def test_does_not_wake_putters(self):
        """Evicting append doesn't change deque size — putters stay asleep."""
        d = deque([1, 2, 3], maxlen=3)
        woken = False

        async def blocked_appender():
            nonlocal woken
            await d.aappend(99)
            woken = True

        task = asyncio.create_task(blocked_appender())
        await asyncio.sleep(0.01)

        await d.aappend(4, evict=True)
        await asyncio.sleep(0.02)
        assert not woken  # putter still blocked

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_repeated_eviction(self):
        d = deque([1, 2, 3], maxlen=3)
        evicted = []
        for i in range(4, 7):
            evicted.append(await d.aappend(i, evict=True))
        assert evicted == [1, 2, 3]
        assert list(d) == [4, 5, 6]

    async def test_wakes_getter_when_not_full(self):
        """When deque was empty, evict=True append still wakes getters."""
        d: deque[int] = deque(maxlen=3)
        result: list[int] = []

        async def consumer():
            result.append(await d.apopleft())

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)

        await d.aappend(42, evict=True)
        await asyncio.sleep(0.01)
        assert result == [42]
        await task


class TestAappendleftEvict:
    async def test_evicts_rightmost_when_full(self):
        d = deque([1, 2, 3], maxlen=3)
        evicted = await d.aappendleft(0, evict=True)
        assert evicted == 3
        assert list(d) == [0, 1, 2]

    async def test_no_eviction_when_not_full(self):
        d: deque[int] = deque([1, 2], maxlen=3)
        evicted = await d.aappendleft(0, evict=True)
        assert evicted is None
        assert list(d) == [0, 1, 2]

    async def test_no_eviction_unbounded(self):
        d: deque[int] = deque([1, 2])
        evicted = await d.aappendleft(0, evict=True)
        assert evicted is None
        assert list(d) == [0, 1, 2]

    async def test_maxlen_zero(self):
        d: deque[int] = deque(maxlen=0)
        evicted = await d.aappendleft(1, evict=True)
        assert evicted is None
        assert len(d) == 0

    async def test_maxlen_one(self):
        d = deque([1], maxlen=1)
        evicted = await d.aappendleft(2, evict=True)
        assert evicted == 1
        assert list(d) == [2]

    async def test_never_blocks(self):
        d = deque([1, 2, 3], maxlen=3)
        evicted = await asyncio.wait_for(d.aappendleft(0, evict=True), timeout=0.1)
        assert evicted == 3

    async def test_repeated_eviction(self):
        d = deque([1, 2, 3], maxlen=3)
        evicted = []
        for i in range(-1, -4, -1):
            evicted.append(await d.aappendleft(i, evict=True))
        assert evicted == [3, 2, 1]
        assert list(d) == [-3, -2, -1]


class TestAextendEvict:
    async def test_evicts_during_extend(self):
        d = deque([1, 2, 3], maxlen=3)
        await d.aextend([4, 5], evict=True)
        assert list(d) == [3, 4, 5]

    async def test_evicts_during_extendleft(self):
        d = deque([1, 2, 3], maxlen=3)
        await d.aextendleft([4, 5], evict=True)
        assert list(d) == [5, 4, 1]


# =========================================================================
#  Producer / consumer patterns
# =========================================================================


class TestProducerConsumer:
    async def test_bounded_channel(self):
        d: deque[int] = deque(maxlen=5)
        n = 200
        consumed: list[int] = []

        async def producer():
            for i in range(n):
                await d.aappend(i)

        async def consumer():
            for _ in range(n):
                consumed.append(await d.apopleft())

        await asyncio.gather(producer(), consumer())
        assert consumed == list(range(n))

    async def test_multiple_producers_consumers(self):
        d: deque[int] = deque(maxlen=3)
        total = 100
        consumed: list[int] = []
        lock = asyncio.Lock()

        async def producer(start: int, count: int):
            for i in range(start, start + count):
                await d.aappend(i)

        async def consumer(count: int):
            for _ in range(count):
                val = await d.apopleft()
                async with lock:
                    consumed.append(val)

        await asyncio.gather(
            producer(0, total // 2),
            producer(total // 2, total // 2),
            consumer(total // 2),
            consumer(total // 2),
        )
        assert sorted(consumed) == list(range(total))

    async def test_apop_as_lifo_channel(self):
        """Using aappend + apop gives LIFO ordering."""
        d: deque[int] = deque(maxlen=10)
        produced = []
        consumed = []

        async def producer():
            for i in range(5):
                await d.aappend(i)
                produced.append(i)
            await asyncio.sleep(0.02)  # let consumer drain

        async def consumer():
            await asyncio.sleep(0.01)  # let producer fill
            for _ in range(5):
                consumed.append(await d.apop())

        await asyncio.gather(producer(), consumer())
        # LIFO: last appended is popped first
        assert consumed == [4, 3, 2, 1, 0]

    async def test_bounded_no_data_loss(self):
        """Every produced item is consumed exactly once."""
        d: deque[int] = deque(maxlen=2)
        n = 500
        consumed: list[int] = []

        async def producer():
            for i in range(n):
                await d.aappend(i)

        async def consumer():
            for _ in range(n):
                consumed.append(await d.apopleft())

        await asyncio.gather(producer(), consumer())
        assert consumed == list(range(n))

    async def test_mixed_append_directions(self):
        """Mix aappend and aappendleft with consumers."""
        d: deque[int] = deque(maxlen=2)
        consumed: list[int] = []

        async def producer():
            await d.aappend(1)
            await d.aappendleft(2)
            await d.aappend(3)
            await d.aappendleft(4)

        async def consumer():
            for _ in range(4):
                consumed.append(await d.apopleft())

        await asyncio.gather(producer(), consumer())
        assert sorted(consumed) == [1, 2, 3, 4]


# =========================================================================
#  Concurrent cancellation stress
# =========================================================================


class TestCancellationStress:
    async def test_mass_cancel_getters(self):
        """Cancel many waiting getters, then verify deque still works."""
        d: deque[int] = deque()
        tasks = [asyncio.create_task(d.apopleft()) for _ in range(10)]
        await asyncio.sleep(0.01)

        for t in tasks:
            t.cancel()
        for t in tasks:
            with pytest.raises(asyncio.CancelledError):
                await t

        # deque should still be fully functional
        await d.aappend(1)
        assert await d.apopleft() == 1

    async def test_mass_cancel_putters(self):
        d = deque([0], maxlen=1)
        tasks = [asyncio.create_task(d.aappend(i)) for i in range(1, 11)]
        await asyncio.sleep(0.01)

        for t in tasks:
            t.cancel()
        for t in tasks:
            with pytest.raises(asyncio.CancelledError):
                await t

        assert list(d) == [0]

        # still works
        val = await d.apop()
        assert val == 0
        await d.aappend(99)
        assert list(d) == [99]

    async def test_cancel_some_keep_others(self):
        """Cancel half the getters, deliver to the rest."""
        d: deque[int] = deque()
        results: list[int] = []

        async def consumer():
            results.append(await d.apopleft())

        tasks = [asyncio.create_task(consumer()) for _ in range(6)]
        await asyncio.sleep(0.01)

        # cancel even-indexed tasks
        for i in (0, 2, 4):
            tasks[i].cancel()
        for i in (0, 2, 4):
            with pytest.raises(asyncio.CancelledError):
                await tasks[i]

        # deliver to remaining 3
        for v in [10, 20, 30]:
            await d.aappend(v)
            await asyncio.sleep(0.001)

        for i in (1, 3, 5):
            await tasks[i]

        assert sorted(results) == [10, 20, 30]


# =========================================================================
#  Exception propagation
# =========================================================================


class TestExceptionEdges:
    async def test_apop_after_exception_in_other_task(self):
        """Deque remains usable after an exception elsewhere."""
        d: deque[int] = deque()

        async def failing_producer():
            await asyncio.sleep(0.01)
            raise ValueError("boom")

        async def consumer():
            return await d.apop()

        consumer_task = asyncio.create_task(consumer())
        producer_task = asyncio.create_task(failing_producer())

        with pytest.raises(ValueError, match="boom"):
            await producer_task

        # consumer is still waiting — give it an item
        await d.aappend(42)
        result = await consumer_task
        assert result == 42

    async def test_deque_usable_after_timeout(self):
        d: deque[int] = deque(maxlen=1)
        await d.aappend(1)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(d.aappend(2), timeout=0.02)

        # still works
        assert await d.apopleft() == 1
        await d.aappend(3)
        assert await d.apopleft() == 3


# =========================================================================
#  Mixed apop and apopleft waiters on same deque
# =========================================================================


class TestMixedPopWaiters:
    async def test_apop_and_apopleft_both_waiting(self):
        d: deque[int] = deque()
        results: dict[str, int] = {}

        async def pop_right():
            results["right"] = await d.apop()

        async def pop_left():
            results["left"] = await d.apopleft()

        t1 = asyncio.create_task(pop_left())
        t2 = asyncio.create_task(pop_right())
        await asyncio.sleep(0.01)

        # both share the _getters queue — first registered (t1) wakes first
        await d.aappend(10)
        await asyncio.sleep(0.01)
        assert "left" in results
        assert results["left"] == 10

        await d.aappend(20)
        await asyncio.sleep(0.01)
        assert "right" in results
        # t2 uses apop (rightmost), but deque has one item so pop == popleft
        assert results["right"] == 20

        await asyncio.gather(t1, t2)


# =========================================================================
#  Lazy initialization
# =========================================================================


class TestLazyInit:
    async def test_getters_none_initially(self):
        d: deque[int] = deque()
        assert d._getters is None

    async def test_putters_none_initially(self):
        d: deque[int] = deque(maxlen=3)
        assert d._putters is None

    async def test_getters_created_on_first_wait(self):
        d: deque[int] = deque()
        task = asyncio.create_task(d.apopleft())
        await asyncio.sleep(0.01)
        assert d._getters is not None
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_putters_created_on_first_wait(self):
        d = deque([1], maxlen=1)
        task = asyncio.create_task(d.aappend(2))
        await asyncio.sleep(0.01)
        assert d._putters is not None
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_no_overhead_sync_only(self):
        """Sync-only usage never allocates waiter queues."""
        d = deque([1, 2, 3], maxlen=5)
        d.append(4)
        d.popleft()
        d.extend([5, 6])
        d.rotate(1)
        assert d._getters is None
        assert d._putters is None

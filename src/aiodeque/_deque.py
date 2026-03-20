# SPDX-License-Identifier: MIT
# Copyright (c) 2026 cutient

"""Drop-in ``collections.deque`` replacement with async methods."""

from __future__ import annotations

import asyncio
import copy as _copy_mod
from collections import deque as _deque
from typing import Iterable, Self, TypeVar

T = TypeVar("T")

_deque_append = _deque.append
_deque_appendleft = _deque.appendleft
_deque_pop = _deque.pop
_deque_popleft = _deque.popleft
_deque_insert = _deque.insert


def _wakeup_next(waiters: _deque[asyncio.Future[None]] | None) -> None:
    """Wake the first non-done waiter, if any."""
    while waiters:
        w = waiters.popleft()
        if not w.done():
            w.set_result(None)
            return


class deque(_deque[T]):
    """A :class:`collections.deque` subclass with ``a``-prefixed async methods.

    All synchronous methods behave identically to :class:`collections.deque`
    with some overhead.  Async methods wait when the deque is empty (pop) or
    full (append with *maxlen* set), using the same Future-based signalling
    pattern as :class:`asyncio.Queue`.

    Sync mutations do **not** wake async waiters — use async methods when you
    need coordination between producers and consumers.
    """

    __slots__ = ("_getters", "_putters")

    def __init__(self, iterable: Iterable[T] = (), maxlen: int | None = None) -> None:
        super().__init__(iterable, maxlen=maxlen)
        self._getters: _deque[asyncio.Future[None]] | None = None
        self._putters: _deque[asyncio.Future[None]] | None = None

    # -- internal helpers --------------------------------------------------

    def _get_getters(self) -> _deque[asyncio.Future[None]]:
        g = self._getters
        if g is None:
            g = self._getters = _deque()
        return g

    def _get_putters(self) -> _deque[asyncio.Future[None]]:
        p = self._putters
        if p is None:
            p = self._putters = _deque()
        return p

    # -- async pop ---------------------------------------------------------

    async def apop(self) -> T:
        """Remove and return the rightmost element, waiting if empty."""
        if not self:
            getters = self._get_getters()
            loop = asyncio.get_running_loop()
            while not self:
                fut: asyncio.Future[None] = loop.create_future()
                getters.append(fut)
                try:
                    await fut
                except BaseException:
                    fut.cancel()
                    with _suppress_value_error():
                        getters.remove(fut)
                    if self and not fut.cancelled():
                        _wakeup_next(self._getters)
                    raise
        item: T = _deque_pop(self)
        p = self._putters
        if p:
            _wakeup_next(p)
        return item

    async def apopleft(self) -> T:
        """Remove and return the leftmost element, waiting if empty."""
        if not self:
            getters = self._get_getters()
            loop = asyncio.get_running_loop()
            while not self:
                fut: asyncio.Future[None] = loop.create_future()
                getters.append(fut)
                try:
                    await fut
                except BaseException:
                    fut.cancel()
                    with _suppress_value_error():
                        getters.remove(fut)
                    if self and not fut.cancelled():
                        _wakeup_next(self._getters)
                    raise
        item: T = _deque_popleft(self)
        p = self._putters
        if p:
            _wakeup_next(p)
        return item

    # -- async append ------------------------------------------------------

    async def aappend(self, item: T) -> None:
        """Append *item* to the right, waiting if full (*maxlen* set)."""
        maxlen = self.maxlen
        if maxlen is not None and len(self) >= maxlen:
            if maxlen == 0:
                return
            putters = self._get_putters()
            loop = asyncio.get_running_loop()
            while len(self) >= maxlen:
                fut: asyncio.Future[None] = loop.create_future()
                putters.append(fut)
                try:
                    await fut
                except BaseException:
                    fut.cancel()
                    with _suppress_value_error():
                        putters.remove(fut)
                    if len(self) < maxlen and not fut.cancelled():
                        _wakeup_next(self._putters)
                    raise
        _deque_append(self, item)
        g = self._getters
        if g:
            _wakeup_next(g)

    async def aappendleft(self, item: T) -> None:
        """Append *item* to the left, waiting if full (*maxlen* set)."""
        maxlen = self.maxlen
        if maxlen is not None and len(self) >= maxlen:
            if maxlen == 0:
                return
            putters = self._get_putters()
            loop = asyncio.get_running_loop()
            while len(self) >= maxlen:
                fut: asyncio.Future[None] = loop.create_future()
                putters.append(fut)
                try:
                    await fut
                except BaseException:
                    fut.cancel()
                    with _suppress_value_error():
                        putters.remove(fut)
                    if len(self) < maxlen and not fut.cancelled():
                        _wakeup_next(self._putters)
                    raise
        _deque_appendleft(self, item)
        g = self._getters
        if g:
            _wakeup_next(g)

    # -- async extend ------------------------------------------------------

    async def aextend(self, iterable: Iterable[T]) -> None:
        """Extend the right side, waiting for space per element."""
        for item in iterable if isinstance(iterable, (list, tuple)) else list(iterable):
            await self.aappend(item)

    async def aextendleft(self, iterable: Iterable[T]) -> None:
        """Extend the left side, waiting for space per element."""
        for item in iterable if isinstance(iterable, (list, tuple)) else list(iterable):
            await self.aappendleft(item)

    # -- async insert ------------------------------------------------------

    async def ainsert(self, i: int, item: T) -> None:
        """Insert *item* at position *i*, waiting if full (*maxlen* set)."""
        maxlen = self.maxlen
        if maxlen is not None and len(self) >= maxlen:
            if maxlen == 0:
                return
            putters = self._get_putters()
            loop = asyncio.get_running_loop()
            while len(self) >= maxlen:
                fut: asyncio.Future[None] = loop.create_future()
                putters.append(fut)
                try:
                    await fut
                except BaseException:
                    fut.cancel()
                    with _suppress_value_error():
                        putters.remove(fut)
                    if len(self) < maxlen and not fut.cancelled():
                        _wakeup_next(self._putters)
                    raise
        _deque_insert(self, i, item)
        g = self._getters
        if g:
            _wakeup_next(g)

    # -- copy / pickle -----------------------------------------------------

    def copy(self) -> Self:
        """Return a shallow copy (without waiter queues)."""
        return type(self)(self, maxlen=self.maxlen)

    __copy__ = copy

    def __deepcopy__(self, memo: dict) -> Self:
        new = type(self)(maxlen=self.maxlen)
        memo[id(self)] = new
        for item in self:
            new.append(_copy_mod.deepcopy(item, memo))
        return new

    def __reduce__(self):
        return (type(self), (list(self), self.maxlen))

    def __repr__(self) -> str:
        name = type(self).__qualname__
        if self.maxlen is not None:
            return f"{name}({list(self)!r}, maxlen={self.maxlen})"
        return f"{name}({list(self)!r})"


class _suppress_value_error:
    """Tiny context manager — avoids import of contextlib."""

    __slots__ = ()

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:  # type: ignore[override]
        return exc_type is ValueError

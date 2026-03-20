# aiodeque

[![PyPI version](https://img.shields.io/pypi/v/aiodeque)](https://pypi.org/project/aiodeque/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://github.com/cutient/aiodeque/actions/workflows/ci.yml/badge.svg)](https://github.com/cutient/aiodeque/actions/workflows/ci.yml)

A drop-in `collections.deque` replacement with async methods for producer/consumer coordination.

## Why aiodeque?

`asyncio.Queue` only does FIFO. `aiodeque` gives you a **double-ended queue** with async waiting on both ends:

- Pop from **right or left**, append to **right or left**
- Waiters block when the deque is **empty** (pop) or **full** (append with `maxlen`)
- Fully compatible with `collections.deque` — all sync methods work as-is

## Requirements

- Python >= 3.11
- No runtime dependencies

## Installation

```bash
pip install aiodeque
```

```bash
uv add aiodeque
```

## Quick Start

```python
import asyncio
from aiodeque import deque

async def main():
    d: deque[int] = deque(maxlen=5)

    async def producer():
        for i in range(10):
            await d.aappend(i)

    async def consumer():
        for _ in range(10):
            item = await d.apopleft()
            print(item)

    await asyncio.gather(producer(), consumer())

asyncio.run(main())
```

## Async API

| Method | Blocks when… |
|---|---|
| `await d.apop()` | deque is empty |
| `await d.apopleft()` | deque is empty |
| `await d.aappend(item)` | deque is full (`maxlen` set) |
| `await d.aappendleft(item)` | deque is full (`maxlen` set) |
| `await d.aextend(iterable)` | deque is full for each item |
| `await d.aextendleft(iterable)` | deque is full for each item |
| `await d.ainsert(i, item)` | deque is full (`maxlen` set) |

All other `collections.deque` methods (`.append()`, `.pop()`, `.rotate()`, etc.) are inherited and work unchanged.

### Evicting mode

Pass `evict=True` to `aappend`, `aappendleft`, `aextend`, or `aextendleft` to drop the oldest element instead of waiting when the deque is full:

```python
d: deque[int] = deque([1, 2, 3], maxlen=3)
evicted = await d.aappend(4, evict=True)   # evicted == 1, d == [2, 3, 4]
evicted = await d.aappendleft(0, evict=True)  # evicted == 4, d == [0, 2, 3]
```

- `aappend(..., evict=True)` evicts from the **left** (oldest-first FIFO).
- `aappendleft(..., evict=True)` evicts from the **right**.
- Returns the evicted element, or `None` if the deque was not full.
- When the deque is not full, behaves identically to the non-evicting call.

## Behavior Notes

- **Sync mutations do not wake async waiters** — if you call `d.append()` directly, tasks waiting in `apopleft()` will not be notified. Use async methods when coordinating between producers and consumers.
- **Cancellation safe** — cancelling an `await` removes the waiter cleanly; no item is lost and the next waiter is woken up if appropriate.
- **FIFO waiter ordering** — waiters are served in the order they started waiting.
- **Lazy initialization** — internal waiter queues are only allocated on first async use; sync-only usage has no overhead.

## vs asyncio.Queue

| Feature | `asyncio.Queue` | `aiodeque` |
|---|---|---|
| FIFO get/put | Yes | Yes (`apopleft` / `aappend`) |
| Pop from right | No | Yes (`apop`) |
| Append to left | No | Yes (`aappendleft`) |
| Insert at index | No | Yes (`ainsert`) |
| Rotate / slice | No | Yes (inherited from `deque`) |
| `maxsize` / `maxlen` | Yes | Yes |
| Evicting append | No | Yes (`evict=True`) |
| `task_done` / `join` | Yes | No |
| Sync access | No | Yes (all `collections.deque` methods) |
| Type-parameterized | No | Yes (`deque[T]`) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

[MIT](LICENSE)

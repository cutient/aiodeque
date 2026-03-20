# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-20

### Added

- `aiodeque.deque`: drop-in `collections.deque` subclass with async methods
- `apop()`, `apopleft()` — wait if the deque is empty
- `aappend(item)`, `aappendleft(item)` — wait if full (when `maxlen` is set)
- `aextend(iterable)`, `aextendleft(iterable)` — append one element at a time, waiting for space
- `ainsert(i, item)` — wait if full (when `maxlen` is set)
- Cancellation-safe waiter handling with FIFO ordering
- Lazy initialization of waiter queues (no overhead for sync-only usage)
- `copy()` / `__deepcopy__()` / `__reduce__()` support (waiter queues not copied)
- `py.typed` marker (PEP 561)
- No runtime dependencies; requires Python >= 3.14

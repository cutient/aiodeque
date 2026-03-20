# SPDX-License-Identifier: MIT
# Copyright (c) 2026 cutient

"""Async-capable deque — drop-in replacement for ``collections.deque``."""

from aiodeque._deque import deque

__all__ = ["deque"]
__version__ = "0.1.1"

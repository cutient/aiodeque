# SPDX-License-Identifier: MIT
# Copyright (c) 2026 cutient

# pyright: reportArgumentType=false, reportOperatorIssue=false
"""Tests that aiodeque.deque is a full drop-in for collections.deque.

Every behaviour is cross-checked against stdlib collections.deque so that any
divergence is caught automatically.
"""

from __future__ import annotations

import copy
import pickle
from collections import deque as stdlib_deque

import pytest

from aiodeque import deque


# ---------------------------------------------------------------------------
#  Helper: run the same assertion against both implementations
# ---------------------------------------------------------------------------


def _both(fn):
    """Call *fn* with aiodeque.deque and then with stdlib deque, compare."""
    a = fn(deque)
    b = fn(stdlib_deque)
    assert list(a) == list(b)
    assert a.maxlen == b.maxlen
    return a


# =========================================================================
#  Construction
# =========================================================================


class TestConstruction:
    def test_empty(self):
        d = deque()
        assert len(d) == 0
        assert d.maxlen is None

    def test_from_list(self):
        d = deque([1, 2, 3])
        assert list(d) == [1, 2, 3]

    def test_from_tuple(self):
        d = deque((4, 5, 6))
        assert list(d) == [4, 5, 6]

    def test_from_string(self):
        d = deque("abc")
        assert list(d) == ["a", "b", "c"]

    def test_from_set(self):
        d = deque({42})
        assert list(d) == [42]

    def test_from_dict_keys(self):
        d = deque({"a": 1, "b": 2})
        assert list(d) == ["a", "b"]

    def test_from_generator(self):
        d = deque(x * 2 for x in range(4))
        assert list(d) == [0, 2, 4, 6]

    def test_from_range(self):
        d = deque(range(5))
        assert list(d) == [0, 1, 2, 3, 4]

    def test_from_another_deque(self):
        orig = deque([1, 2, 3])
        d = deque(orig)
        assert list(d) == [1, 2, 3]
        orig.append(4)
        assert 4 not in d  # independent copy

    def test_from_stdlib_deque(self):
        sd = stdlib_deque([1, 2, 3])
        d = deque(sd)
        assert list(d) == [1, 2, 3]

    def test_maxlen(self):
        d = deque(range(10), maxlen=3)
        assert list(d) == [7, 8, 9]
        assert d.maxlen == 3

    def test_maxlen_exact(self):
        d = deque([1, 2, 3], maxlen=3)
        assert list(d) == [1, 2, 3]

    def test_maxlen_larger(self):
        d = deque([1, 2], maxlen=5)
        assert list(d) == [1, 2]
        assert d.maxlen == 5

    def test_maxlen_one(self):
        d = deque([1, 2, 3], maxlen=1)
        assert list(d) == [3]

    def test_maxlen_zero(self):
        d = deque([1, 2], maxlen=0)
        assert len(d) == 0

    def test_maxlen_none_explicit(self):
        d = deque([1], maxlen=None)
        assert d.maxlen is None

    def test_negative_maxlen_raises(self):
        with pytest.raises((ValueError, OverflowError)):
            deque(maxlen=-1)

    def test_maxlen_is_readonly(self):
        d = deque(maxlen=5)
        with pytest.raises(AttributeError):
            d.maxlen = 10  # type: ignore[misc]

    def test_reinit_replaces_contents(self):
        d = deque([1, 2, 3])
        d.__init__([4, 5])  # type: ignore[misc]
        assert list(d) == [4, 5]


# =========================================================================
#  append / appendleft
# =========================================================================


class TestAppend:
    def test_append(self):
        d = deque()
        d.append(1)
        d.append(2)
        assert list(d) == [1, 2]

    def test_appendleft(self):
        d = deque()
        d.appendleft(1)
        d.appendleft(2)
        assert list(d) == [2, 1]

    def test_append_none(self):
        d = deque()
        d.append(None)
        assert list(d) == [None]

    def test_append_maxlen_evicts_left(self):
        d = deque([1, 2, 3], maxlen=3)
        d.append(4)
        assert list(d) == [2, 3, 4]

    def test_appendleft_maxlen_evicts_right(self):
        d = deque([1, 2, 3], maxlen=3)
        d.appendleft(0)
        assert list(d) == [0, 1, 2]

    def test_append_maxlen_one(self):
        d = deque([1], maxlen=1)
        d.append(2)
        assert list(d) == [2]

    def test_appendleft_maxlen_one(self):
        d = deque([1], maxlen=1)
        d.appendleft(0)
        assert list(d) == [0]

    def test_append_maxlen_zero(self):
        d = deque(maxlen=0)
        d.append(1)
        assert len(d) == 0

    def test_appendleft_maxlen_zero(self):
        d = deque(maxlen=0)
        d.appendleft(1)
        assert len(d) == 0

    def test_append_matches_stdlib(self):
        def fn(cls):
            d = cls(maxlen=3)
            for i in range(7):
                d.append(i)
            return d

        _both(fn)


# =========================================================================
#  extend / extendleft
# =========================================================================


class TestExtend:
    def test_extend(self):
        d = deque([1])
        d.extend([2, 3, 4])
        assert list(d) == [1, 2, 3, 4]

    def test_extendleft(self):
        d = deque([4])
        d.extendleft([3, 2, 1])
        assert list(d) == [1, 2, 3, 4]

    def test_extend_empty_iterable(self):
        d = deque([1, 2])
        d.extend([])
        assert list(d) == [1, 2]

    def test_extend_generator(self):
        d = deque()
        d.extend(x for x in range(3))
        assert list(d) == [0, 1, 2]

    def test_extendleft_generator(self):
        d = deque()
        d.extendleft(x for x in range(3))
        assert list(d) == [2, 1, 0]

    def test_extend_string(self):
        d = deque()
        d.extend("abc")
        assert list(d) == ["a", "b", "c"]

    def test_extend_maxlen_overflow(self):
        d = deque([1, 2, 3], maxlen=3)
        d.extend([4, 5])
        assert list(d) == [3, 4, 5]

    def test_extendleft_maxlen_overflow(self):
        d = deque([1, 2, 3], maxlen=3)
        d.extendleft([0, -1])
        assert list(d) == [-1, 0, 1]

    def test_extend_more_than_maxlen(self):
        d = deque(maxlen=3)
        d.extend(range(10))
        assert list(d) == [7, 8, 9]

    def test_extend_maxlen_zero(self):
        d = deque(maxlen=0)
        d.extend([1, 2, 3])
        assert len(d) == 0

    def test_extend_matches_stdlib(self):
        def fn(cls):
            d = cls([1], maxlen=4)
            d.extend([2, 3, 4, 5, 6])
            return d

        _both(fn)

    def test_extendleft_matches_stdlib(self):
        def fn(cls):
            d = cls([10], maxlen=4)
            d.extendleft([9, 8, 7, 6, 5])
            return d

        _both(fn)


# =========================================================================
#  insert
# =========================================================================


class TestInsert:
    def test_insert_middle(self):
        d = deque([1, 3])
        d.insert(1, 2)
        assert list(d) == [1, 2, 3]

    def test_insert_beginning(self):
        d = deque([2, 3])
        d.insert(0, 1)
        assert list(d) == [1, 2, 3]

    def test_insert_end(self):
        d = deque([1, 2])
        d.insert(100, 3)  # index > len ⇒ append
        assert list(d) == [1, 2, 3]

    def test_insert_negative_index(self):
        d = deque([1, 3])
        d.insert(-1, 2)
        assert list(d) == [1, 2, 3]

    def test_insert_empty(self):
        d = deque()
        d.insert(0, 1)
        assert list(d) == [1]

    def test_insert_full_raises(self):
        d = deque([1, 2, 3], maxlen=3)
        with pytest.raises(IndexError):
            d.insert(1, 99)

    def test_insert_matches_stdlib(self):
        def fn(cls):
            d = cls([1, 4])
            d.insert(1, 2)
            d.insert(2, 3)
            return d

        _both(fn)


# =========================================================================
#  pop / popleft
# =========================================================================


class TestPop:
    def test_pop(self):
        d = deque([1, 2, 3])
        assert d.pop() == 3
        assert list(d) == [1, 2]

    def test_popleft(self):
        d = deque([1, 2, 3])
        assert d.popleft() == 1
        assert list(d) == [2, 3]

    def test_pop_single(self):
        d = deque([42])
        assert d.pop() == 42
        assert len(d) == 0

    def test_popleft_single(self):
        d = deque([42])
        assert d.popleft() == 42
        assert len(d) == 0

    def test_pop_empty_raises(self):
        with pytest.raises(IndexError):
            deque().pop()

    def test_popleft_empty_raises(self):
        with pytest.raises(IndexError):
            deque().popleft()

    def test_pop_until_empty(self):
        d = deque([1, 2, 3])
        items = []
        while d:
            items.append(d.pop())
        assert items == [3, 2, 1]
        assert len(d) == 0

    def test_popleft_until_empty(self):
        d = deque([1, 2, 3])
        items = []
        while d:
            items.append(d.popleft())
        assert items == [1, 2, 3]


# =========================================================================
#  remove
# =========================================================================


class TestRemove:
    def test_remove_first_occurrence(self):
        d = deque([1, 2, 3, 2])
        d.remove(2)
        assert list(d) == [1, 3, 2]

    def test_remove_only_element(self):
        d = deque([1])
        d.remove(1)
        assert len(d) == 0

    def test_remove_missing_raises(self):
        with pytest.raises(ValueError):
            deque([1, 2]).remove(99)

    def test_remove_from_empty_raises(self):
        with pytest.raises(ValueError):
            deque().remove(1)

    def test_remove_none(self):
        d = deque([None, 1, None])
        d.remove(None)
        assert list(d) == [1, None]


# =========================================================================
#  clear
# =========================================================================


class TestClear:
    def test_clear(self):
        d = deque([1, 2, 3])
        d.clear()
        assert len(d) == 0

    def test_clear_empty(self):
        d = deque()
        d.clear()
        assert len(d) == 0

    def test_clear_preserves_maxlen(self):
        d = deque([1, 2], maxlen=5)
        d.clear()
        assert d.maxlen == 5
        assert len(d) == 0


# =========================================================================
#  rotate
# =========================================================================


class TestRotate:
    def test_rotate_right(self):
        d = deque([1, 2, 3, 4, 5])
        d.rotate(2)
        assert list(d) == [4, 5, 1, 2, 3]

    def test_rotate_left(self):
        d = deque([1, 2, 3, 4, 5])
        d.rotate(-2)
        assert list(d) == [3, 4, 5, 1, 2]

    def test_rotate_default(self):
        d = deque([1, 2, 3])
        d.rotate()
        assert list(d) == [3, 1, 2]

    def test_rotate_zero(self):
        d = deque([1, 2, 3])
        d.rotate(0)
        assert list(d) == [1, 2, 3]

    def test_rotate_full_circle(self):
        d = deque([1, 2, 3])
        d.rotate(3)
        assert list(d) == [1, 2, 3]

    def test_rotate_more_than_len(self):
        d = deque([1, 2, 3])
        d.rotate(5)
        # 5 % 3 == 2
        assert list(d) == [2, 3, 1]

    def test_rotate_negative_more_than_len(self):
        d = deque([1, 2, 3])
        d.rotate(-5)
        assert list(d) == [3, 1, 2]

    def test_rotate_empty(self):
        d = deque()
        d.rotate(5)  # should not raise
        assert len(d) == 0

    def test_rotate_single(self):
        d = deque([1])
        d.rotate(99)
        assert list(d) == [1]

    def test_rotate_matches_stdlib(self):
        for n in (-7, -3, -1, 0, 1, 3, 7):

            def fn(cls, n=n):
                d = cls([10, 20, 30, 40])
                d.rotate(n)
                return d

            _both(fn)


# =========================================================================
#  reverse
# =========================================================================


class TestReverse:
    def test_reverse(self):
        d = deque([1, 2, 3])
        d.reverse()
        assert list(d) == [3, 2, 1]

    def test_reverse_empty(self):
        d = deque()
        d.reverse()
        assert list(d) == []

    def test_reverse_single(self):
        d = deque([1])
        d.reverse()
        assert list(d) == [1]

    def test_reverse_is_inplace(self):
        d = deque([1, 2, 3])
        ret = d.reverse()
        assert ret is None


# =========================================================================
#  count
# =========================================================================


class TestCount:
    def test_count(self):
        d = deque([1, 2, 2, 3, 2])
        assert d.count(2) == 3

    def test_count_zero(self):
        assert deque([1, 2, 3]).count(99) == 0

    def test_count_empty(self):
        assert deque().count(1) == 0

    def test_count_none(self):
        assert deque([None, 1, None]).count(None) == 2

    def test_count_all_same(self):
        assert deque([7, 7, 7]).count(7) == 3


# =========================================================================
#  index
# =========================================================================


class TestIndex:
    def test_index_basic(self):
        d = deque([10, 20, 30, 20])
        assert d.index(20) == 1

    def test_index_with_start(self):
        d = deque([10, 20, 30, 20])
        assert d.index(20, 2) == 3

    def test_index_with_start_stop(self):
        d = deque([10, 20, 30, 20, 40])
        assert d.index(20, 0, 2) == 1

    def test_index_not_in_slice(self):
        d = deque([10, 20, 30])
        with pytest.raises(ValueError):
            d.index(30, 0, 2)

    def test_index_missing_raises(self):
        with pytest.raises(ValueError):
            deque([1, 2]).index(99)

    def test_index_empty_raises(self):
        with pytest.raises(ValueError):
            deque().index(1)

    def test_index_first_occurrence(self):
        d = deque([5, 5, 5])
        assert d.index(5) == 0

    def test_index_negative_start(self):
        """stdlib deque treats negative start as 0."""
        ref = stdlib_deque([10, 20, 30])
        d = deque([10, 20, 30])
        assert d.index(10, -5) == ref.index(10, -5)

    def test_index_stop_beyond_len(self):
        d = deque([10, 20, 30])
        assert d.index(30, 0, 100) == 2


# =========================================================================
#  __len__ / __bool__
# =========================================================================


class TestLenBool:
    def test_len_empty(self):
        assert len(deque()) == 0

    def test_len(self):
        assert len(deque([1, 2, 3])) == 3

    def test_bool_empty(self):
        assert not deque()

    def test_bool_nonempty(self):
        assert deque([1])

    def test_bool_after_clear(self):
        d = deque([1, 2])
        d.clear()
        assert not d

    def test_bool_after_pop(self):
        d = deque([1])
        d.pop()
        assert not d


# =========================================================================
#  __contains__
# =========================================================================


class TestContains:
    def test_in(self):
        assert 2 in deque([1, 2, 3])

    def test_not_in(self):
        assert 99 not in deque([1, 2, 3])

    def test_contains_none(self):
        assert None in deque([None, 1])
        assert None not in deque([1, 2])

    def test_contains_unhashable(self):
        d = deque([[1, 2], [3, 4]])
        assert [1, 2] in d
        assert [5, 6] not in d

    def test_contains_empty(self):
        assert 1 not in deque()


# =========================================================================
#  __iter__ / __reversed__
# =========================================================================


class TestIteration:
    def test_iter(self):
        assert list(deque([1, 2, 3])) == [1, 2, 3]

    def test_iter_empty(self):
        assert list(deque()) == []

    def test_reversed(self):
        assert list(reversed(deque([1, 2, 3]))) == [3, 2, 1]

    def test_reversed_empty(self):
        assert list(reversed(deque())) == []

    def test_iter_with_maxlen(self):
        d = deque(range(10), maxlen=3)
        assert list(d) == [7, 8, 9]

    def test_multiple_iterations(self):
        d = deque([1, 2, 3])
        assert list(d) == list(d)


# =========================================================================
#  __getitem__ / __setitem__ / __delitem__
# =========================================================================


class TestIndexing:
    def test_getitem(self):
        d = deque([10, 20, 30])
        assert d[0] == 10
        assert d[1] == 20
        assert d[2] == 30

    def test_getitem_negative(self):
        d = deque([10, 20, 30])
        assert d[-1] == 30
        assert d[-2] == 20
        assert d[-3] == 10

    def test_getitem_out_of_range(self):
        d = deque([10, 20])
        with pytest.raises(IndexError):
            d[5]
        with pytest.raises(IndexError):
            d[-5]

    def test_setitem(self):
        d = deque([10, 20, 30])
        d[1] = 99
        assert list(d) == [10, 99, 30]

    def test_setitem_negative(self):
        d = deque([10, 20, 30])
        d[-1] = 99
        assert list(d) == [10, 20, 99]

    def test_setitem_out_of_range(self):
        d = deque([10, 20])
        with pytest.raises(IndexError):
            d[5] = 99

    def test_delitem(self):
        d = deque([10, 20, 30])
        del d[1]
        assert list(d) == [10, 30]

    def test_delitem_first(self):
        d = deque([10, 20, 30])
        del d[0]
        assert list(d) == [20, 30]

    def test_delitem_last(self):
        d = deque([10, 20, 30])
        del d[-1]
        assert list(d) == [10, 20]

    def test_delitem_out_of_range(self):
        d = deque([10, 20])
        with pytest.raises(IndexError):
            del d[5]


# =========================================================================
#  Comparison operators
# =========================================================================


class TestComparison:
    def test_eq(self):
        assert deque([1, 2]) == deque([1, 2])

    def test_ne(self):
        assert deque([1, 2]) != deque([1, 3])

    def test_eq_different_lengths(self):
        assert deque([1, 2]) != deque([1, 2, 3])

    def test_eq_empty(self):
        assert deque() == deque()

    def test_eq_stdlib(self):
        assert deque([1, 2]) == stdlib_deque([1, 2])

    def test_eq_stdlib_reverse(self):
        assert stdlib_deque([1, 2]) == deque([1, 2])

    def test_ne_stdlib(self):
        assert deque([1, 2]) != stdlib_deque([1, 3])

    def test_eq_different_maxlen(self):
        # maxlen does NOT affect equality — only contents matter
        assert deque([1, 2], maxlen=5) == deque([1, 2], maxlen=10)

    def test_lt(self):
        assert deque([1, 2]) < deque([1, 3])

    def test_lt_prefix(self):
        assert deque([1, 2]) < deque([1, 2, 3])

    def test_lt_false(self):
        assert not (deque([1, 3]) < deque([1, 2]))

    def test_le(self):
        assert deque([1, 2]) <= deque([1, 2])
        assert deque([1, 2]) <= deque([1, 3])

    def test_gt(self):
        assert deque([1, 3]) > deque([1, 2])

    def test_gt_prefix(self):
        assert deque([1, 2, 3]) > deque([1, 2])

    def test_ge(self):
        assert deque([1, 3]) >= deque([1, 2])
        assert deque([1, 2]) >= deque([1, 2])

    def test_comparison_with_non_deque(self):
        assert deque([1, 2]) != [1, 2]
        assert deque([1, 2]) != (1, 2)


# =========================================================================
#  Arithmetic operators
# =========================================================================


class TestArithmetic:
    def test_add(self):
        result = deque([1, 2]) + deque([3, 4])
        assert list(result) == [1, 2, 3, 4]
        assert type(result) is deque

    def test_add_empty(self):
        result = deque([1, 2]) + deque()
        assert list(result) == [1, 2]

    def test_add_both_empty(self):
        result = deque() + deque()
        assert list(result) == []

    def test_add_with_stdlib(self):
        result = deque([1, 2]) + stdlib_deque([3, 4])
        assert list(result) == [1, 2, 3, 4]
        assert type(result) is deque

    def test_iadd(self):
        d = deque([1, 2])
        d += deque([3, 4])
        assert list(d) == [1, 2, 3, 4]

    def test_iadd_iterable(self):
        d = deque([1, 2])
        d += [3, 4]
        assert list(d) == [1, 2, 3, 4]

    def test_iadd_self(self):
        d = deque([1, 2])
        d += d
        assert list(d) == [1, 2, 1, 2]

    def test_mul(self):
        result = deque([1, 2]) * 3
        assert list(result) == [1, 2, 1, 2, 1, 2]
        assert type(result) is deque

    def test_mul_zero(self):
        result = deque([1, 2]) * 0
        assert list(result) == []

    def test_mul_one(self):
        result = deque([1, 2]) * 1
        assert list(result) == [1, 2]

    def test_mul_negative(self):
        result = deque([1, 2]) * -1
        assert list(result) == []

    def test_mul_empty(self):
        result = deque() * 5
        assert list(result) == []

    def test_rmul(self):
        result = 2 * deque([1, 2])
        assert list(result) == [1, 2, 1, 2]
        assert type(result) is deque

    def test_rmul_zero(self):
        result = 0 * deque([1, 2])
        assert list(result) == []

    def test_imul(self):
        d = deque([1, 2])
        d *= 2
        assert list(d) == [1, 2, 1, 2]

    def test_imul_zero(self):
        d = deque([1, 2])
        d *= 0
        assert list(d) == []

    def test_imul_negative(self):
        d = deque([1, 2])
        d *= -1
        assert list(d) == []


# =========================================================================
#  copy / deepcopy / pickle
# =========================================================================


class TestCopy:
    def test_copy_method(self):
        d = deque([1, 2, 3], maxlen=5)
        c = d.copy()
        assert list(c) == [1, 2, 3]
        assert c.maxlen == 5
        assert type(c) is deque

    def test_copy_is_shallow(self):
        inner = [1, 2]
        d = deque([inner])
        c = d.copy()
        assert c[0] is inner

    def test_copy_is_independent(self):
        d = deque([1, 2, 3])
        c = d.copy()
        d.append(4)
        assert list(c) == [1, 2, 3]

    def test_copy_empty(self):
        d = deque()
        c = d.copy()
        assert list(c) == []

    def test_copy_maxlen_none(self):
        d = deque([1, 2])
        c = d.copy()
        assert c.maxlen is None

    def test_copy_maxlen_zero(self):
        d = deque(maxlen=0)
        c = d.copy()
        assert list(c) == []
        assert c.maxlen == 0

    def test_copy_module(self):
        d = deque([1, 2, 3], maxlen=5)
        c = copy.copy(d)
        assert list(c) == [1, 2, 3]
        assert c.maxlen == 5
        assert type(c) is deque

    def test_deepcopy(self):
        inner = [1, 2]
        d = deque([inner], maxlen=5)
        c = copy.deepcopy(d)
        assert c[0] is not inner
        assert c[0] == [1, 2]
        assert c.maxlen == 5
        assert type(c) is deque

    def test_deepcopy_empty(self):
        c = copy.deepcopy(deque())
        assert list(c) == []
        assert type(c) is deque

    def test_deepcopy_recursive(self):
        """deepcopy handles self-referential structures."""
        d = deque()
        d.append(d)
        c = copy.deepcopy(d)
        assert c[0] is c
        assert c[0] is not d

    def test_deepcopy_maxlen_zero(self):
        d = deque(maxlen=0)
        c = copy.deepcopy(d)
        assert list(c) == []
        assert c.maxlen == 0
        assert type(c) is deque


class TestPickle:
    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_pickle_all_protocols(self, protocol: int):
        d = deque([1, 2, 3], maxlen=5)
        loaded = pickle.loads(pickle.dumps(d, protocol))
        assert list(loaded) == [1, 2, 3]
        assert loaded.maxlen == 5
        assert type(loaded) is deque

    def test_pickle_empty(self):
        d = deque()
        loaded = pickle.loads(pickle.dumps(d))
        assert list(loaded) == []
        assert loaded.maxlen is None

    def test_pickle_no_maxlen(self):
        d = deque([1, 2, 3])
        loaded = pickle.loads(pickle.dumps(d))
        assert list(loaded) == [1, 2, 3]
        assert loaded.maxlen is None

    def test_pickle_maxlen_zero(self):
        d = deque(maxlen=0)
        loaded = pickle.loads(pickle.dumps(d))
        assert loaded.maxlen == 0


# =========================================================================
#  __repr__
# =========================================================================


class TestRepr:
    def test_repr_basic(self):
        assert repr(deque([1, 2, 3])) == "deque([1, 2, 3])"

    def test_repr_maxlen(self):
        assert repr(deque([1, 2], maxlen=5)) == "deque([1, 2], maxlen=5)"

    def test_repr_empty(self):
        assert repr(deque()) == "deque([])"

    def test_repr_empty_maxlen(self):
        assert repr(deque(maxlen=3)) == "deque([], maxlen=3)"

    def test_repr_nested(self):
        assert repr(deque([[1, 2], [3]])) == "deque([[1, 2], [3]])"

    def test_repr_roundtrip(self):
        """eval(repr(d)) should reconstruct the deque."""
        d = deque([1, 2, 3], maxlen=5)
        reconstructed = eval(repr(d))  # noqa: S307
        assert list(reconstructed) == [1, 2, 3]
        assert reconstructed.maxlen == 5


# =========================================================================
#  __hash__
# =========================================================================


class TestHash:
    def test_not_hashable(self):
        with pytest.raises(TypeError):
            hash(deque([1, 2]))

    def test_not_usable_as_dict_key(self):
        with pytest.raises(TypeError):
            {deque(): 1}  # pyright: ignore[reportUnusedExpression, reportUnhashable]

    def test_not_usable_in_set(self):
        with pytest.raises(TypeError):
            {deque()}  # pyright: ignore[reportUnusedExpression, reportUnhashable]


# =========================================================================
#  isinstance / type identity
# =========================================================================


class TestTypeIdentity:
    def test_isinstance_stdlib(self):
        assert isinstance(deque([1, 2]), stdlib_deque)

    def test_type_is_aiodeque(self):
        assert type(deque([1, 2])) is deque

    def test_class_getitem(self):
        alias = deque[int]
        assert alias is not None

    def test_subclass_preserved_on_copy(self):
        class MyDeque(deque):
            pass

        d = MyDeque([1, 2, 3])
        c = d.copy()
        assert type(c) is MyDeque

    def test_subclass_preserved_on_add(self):
        class MyDeque(deque):
            pass

        d = MyDeque([1, 2]) + deque([3])
        assert type(d) is MyDeque

    def test_subclass_preserved_on_mul(self):
        class MyDeque(deque):
            pass

        d = MyDeque([1, 2]) * 2
        assert type(d) is MyDeque


# =========================================================================
#  Cross-check: every mutating method vs stdlib
# =========================================================================


class TestCrossCheckStdlib:
    """Run identical operations on both deques and compare results."""

    def test_mixed_ops_unbounded(self):
        def fn(cls):
            d = cls()
            d.append(1)
            d.append(2)
            d.appendleft(0)
            d.extend([3, 4, 5])
            d.extendleft([-2, -1])
            d.rotate(2)
            d.insert(3, 99)
            d.remove(99)
            d.reverse()
            d.pop()
            d.popleft()
            return d

        _both(fn)

    def test_mixed_ops_bounded(self):
        def fn(cls):
            d = cls(maxlen=5)
            d.extend(range(10))
            d.appendleft(-1)
            d.rotate(-2)
            d.pop()
            d.append(100)
            d.reverse()
            d.popleft()
            return d

        _both(fn)

    def test_maxlen_one_stress(self):
        def fn(cls):
            d = cls(maxlen=1)
            for i in range(20):
                d.append(i)
            d.appendleft(99)
            d.extend([100, 101, 102])
            return d

        _both(fn)

    def test_alternating_sides(self):
        def fn(cls):
            d = cls(maxlen=4)
            for i in range(8):
                if i % 2:
                    d.append(i)
                else:
                    d.appendleft(i)
            return d

        _both(fn)

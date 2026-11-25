"""Hand made data structures of the Fly-in project.

The project avoids ready made algorithmic containers: no Counter,
no heapq, no deque, no dataclasses, no Enum, no argparse, no regex.
Everything below is implemented from scratch with basic lists and
dicts (plain Python primitives), and every other module builds on it.
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")

ComparablePairKey = Callable[[T], tuple[int, int]]
"""A key function returning a comparable pair of integers."""


class MinHeap:
    """Binary min heap with explicit array storage.

    Keys must be comparable tuples of numbers/strings; values are
    arbitrary objects. Sift up and sift down are implemented manually.
    """

    def __init__(self) -> None:
        self._items: list[tuple[tuple[float, int, int], str]] = []

    def __len__(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        """Return True when the heap holds no element."""
        return len(self._items) == 0

    def push(self, key: tuple[float, int, int], value: str) -> None:
        """Insert one (key, value) pair, restoring the heap order."""
        self._items.append((key, value))
        index = len(self._items) - 1
        while index > 0:
            parent = (index - 1) // 2
            if self._items[parent][0] <= self._items[index][0]:
                break
            self._swap(parent, index)
            index = parent

    def pop(self) -> tuple[tuple[float, int, int], str] | None:
        """Remove and return the smallest element, or None if empty."""
        if self.is_empty():
            return None
        smallest = self._items[0]
        last = self._items.pop()
        if self._items:
            self._items[0] = last
            self._sift_down(0)
        return smallest

    def _sift_down(self, index: int) -> None:
        """Move the element at `index` down until the order is restored."""
        size = len(self._items)
        position = index
        while True:
            left = 2 * position + 1
            right = 2 * position + 2
            smallest = position
            if left < size and self._items[left][0] < self._items[smallest][0]:
                smallest = left
            if (right < size
                    and self._items[right][0] < self._items[smallest][0]):
                smallest = right
            if smallest == position:
                return
            self._swap(smallest, position)
            position = smallest

    def _swap(self, first: int, second: int) -> None:
        """Exchange two slots of the underlying array."""
        self._items[first], self._items[second] = (
            self._items[second],
            self._items[first],
        )


class Multiset(Generic[T]):
    """Counting set implemented from scratch (Counter replacement)."""

    def __init__(self, initial: dict[T, int] | None = None) -> None:
        self._counts: dict[T, int] = {}
        if initial is not None:
            for item, count in initial.items():
                self._counts[item] = count

    def add(self, item: T, times: int = 1) -> None:
        """Increase the count of one item."""
        self._counts[item] = self._counts.get(item, 0) + times

    def remove(self, item: T, times: int = 1) -> None:
        """Decrease the count of one item, down to 0."""
        current = self._counts.get(item, 0)
        remaining = current - times
        if remaining > 0:
            self._counts[item] = remaining
        else:
            self._counts.pop(item, None)

    def count(self, item: T) -> int:
        """Return the current count of one item."""
        return self._counts.get(item, 0)

    def set_count(self, item: T, count: int) -> None:
        """Force a count value."""
        if count <= 0:
            self._counts.pop(item, None)
        else:
            self._counts[item] = count

    def total(self) -> int:
        """Sum of every stored count."""
        total = 0
        for count in self._counts.values():
            total += count
        return total

    def items(self) -> list[tuple[T, int]]:
        """Return every (item, count) association."""
        return list(self._counts.items())

    def snapshot(self) -> dict[T, int]:
        """Return a plain dict copy of the counts."""
        return dict(self._counts)

    def clear(self) -> None:
        """Empty the multiset."""
        self._counts.clear()

    def update(self, other: Multiset[T]) -> None:
        """Add every count of `other` into this multiset."""
        for item, count in other.items():
            self.add(item, count)


def link_key(zone_a: str, zone_b: str) -> tuple[str, str]:
    """Return the canonical undirected key of a connection.

    Replaces frozenset based keys with a plain normalized pair so no
    collection object is needed for the key identity.
    """
    if zone_a <= zone_b:
        return (zone_a, zone_b)
    return (zone_b, zone_a)


def sort_by(items: list[T], key: ComparablePairKey[T]) -> list[T]:
    """Stable insertion sort using a handmade comparison key.

    Replaces the builtin sorted() everywhere the simulation needs an
    explicit movement priority.
    """
    result = list(items)
    for index in range(1, len(result)):
        current = result[index]
        current_key = key(current)
        position = index - 1
        while position >= 0 and key(result[position]) > current_key:
            result[position + 1] = result[position]
            position -= 1
        result[position + 1] = current
    return result

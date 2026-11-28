"""Tests of the hand made data structures."""

from __future__ import annotations

from datastructures import MinHeap, Multiset, link_key, sort_by


def test_minheap_orders_keys() -> None:
    heap = MinHeap()
    heap.push((5, 0, 0), "e")
    heap.push((1, 0, 0), "a")
    heap.push((3, 0, 0), "c")
    order: list[str] = []
    while not heap.is_empty():
        popped = heap.pop()
        assert popped is not None
        order.append(popped[1])
    assert order == ["a", "c", "e"]


def test_minheap_empty_pop() -> None:
    heap = MinHeap()
    assert heap.is_empty()
    assert heap.pop() is None
    heap.push((2, 0, 0), "b")
    assert not heap.is_empty()
    assert heap.pop() == ((2, 0, 0), "b")


def test_minheap_breaks_ties_by_key_order() -> None:
    heap = MinHeap()
    heap.push((1, 5, 0), "second")
    heap.push((1, 2, 0), "first")
    popped = heap.pop()
    assert popped is not None
    assert popped[1] == "first"


def test_multiset_counts() -> None:
    counter = Multiset[str]({"a": 2})
    counter.add("a")
    counter.add("b")
    assert counter.count("a") == 3
    assert counter.count("b") == 1
    assert counter.count("zzz") == 0
    counter.remove("a", 3)
    assert counter.count("a") == 0
    counter.remove("b")
    assert counter.count("b") == 0


def test_multiset_items_snapshot_total() -> None:
    counter = Multiset[str]({"a": 1, "b": 2})
    assert counter.total() == 3
    snapshot = counter.snapshot()
    counter.clear()
    assert snapshot == {"a": 1, "b": 2}
    assert counter.total() == 0


def test_multiset_update_and_set_count() -> None:
    first = Multiset[str]({"a": 2})
    second = Multiset[str]({"a": 1, "b": 4})
    first.update(second)
    assert first.count("a") == 3
    first.set_count("b", -1)
    assert first.count("b") == 0
    first.set_count("b", 7)
    assert first.count("b") == 7


def test_multiset_counts_any_hashable_item() -> None:
    links = Multiset[tuple[str, str]]({("a", "b"): 2})
    links.add(("b", "a"))
    assert links.count(("a", "b")) == 2
    assert links.count(("b", "a")) == 1


def test_link_key_is_undirected() -> None:
    assert link_key("b", "a") == link_key("a", "b") == ("a", "b")


def test_sort_by_uses_the_key() -> None:
    items = [("b", 2), ("a", 1), ("c", 1), ("a", 0)]
    ordered = sort_by(items, lambda item: (item[1], 0))
    assert ordered == [("a", 0), ("a", 1), ("c", 1), ("b", 2)]


def test_sort_by_empty_list() -> None:
    assert sort_by([], lambda item: (len(item), 0)) == []

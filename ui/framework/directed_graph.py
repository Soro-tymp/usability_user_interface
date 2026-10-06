from __future__ import annotations

from collections import deque
from typing import Hashable, Iterable, Iterator


class CycleError(Exception):
    def __init__(self, cycles: list[list[Hashable]]):
        self.cycles = cycles
        super().__init__(f"Graph contains cycles: {cycles}")


class DirectedGraph:

    __slots__ = ("_successors", "_predecessors")

    def __init__(self) -> None:
        self._successors: dict[Hashable, set[Hashable]] = {}
        self._predecessors: dict[Hashable, set[Hashable]] = {}

    # introspection

    def __contains__(self, node: Hashable) -> bool:
        return node in self._successors

    def __len__(self) -> int:
        return len(self._successors)

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._successors)

    @property
    def nodes(self) -> list[Hashable]:
        return list(self._successors)

    def edges(self) -> Iterator[tuple[Hashable, Hashable]]:
        for src, dsts in self._successors.items():
            for dst in dsts:
                yield (src, dst)

    def successors(self, node: Hashable) -> frozenset[Hashable]:
        return frozenset(self._successors[node])

    def predecessors(self, node: Hashable) -> frozenset[Hashable]:
        return frozenset(self._predecessors[node])

    def has_edge(self, source: Hashable, target: Hashable) -> bool:
        return source in self._successors and target in self._successors[source]

    # mutation

    def add_node(self, node: Hashable) -> bool:
        if node in self._successors:
            return False
        self._successors[node] = set()
        self._predecessors[node] = set()
        return True

    def remove_node(self, node: Hashable) -> bool:
        if node not in self._successors:
            return False
        for succ in self._successors[node]:
            self._predecessors[succ].discard(node)
        for pred in self._predecessors[node]:
            self._successors[pred].discard(node)
        del self._successors[node]
        del self._predecessors[node]
        return True

    def add_edge(self, source: Hashable, target: Hashable) -> bool:
        if source not in self._successors:
            raise KeyError(f"source node not in graph: {source!r}")
        if target not in self._successors:
            raise KeyError(f"target node not in graph: {target!r}")
        if target in self._successors[source]:
            return False
        self._successors[source].add(target)
        self._predecessors[target].add(source)
        return True

    def remove_edge(self, source: Hashable, target: Hashable) -> bool:
        succs = self._successors.get(source)
        if succs is None or target not in succs:
            return False
        succs.discard(target)
        self._predecessors[target].discard(source)
        return True

    def update(
        self,
        nodes: Iterable[Hashable] = (),
        edges: Iterable[tuple[Hashable, Hashable]] = (),
    ) -> None:
        for n in nodes:
            self.add_node(n)
        for s, t in edges:
            self.add_edge(s, t)

    # analysis

    def find_sccs(self) -> list[list[Hashable]]:
        index_of: dict[Hashable, int] = {}
        lowlink: dict[Hashable, int] = {}
        on_stack: dict[Hashable, bool] = {}
        tarjan_stack: list[Hashable] = []
        result: list[list[Hashable]] = []
        counter = 0

        for root in self._successors:
            if root in index_of:
                continue

            index_of[root] = counter
            lowlink[root] = counter
            counter += 1
            tarjan_stack.append(root)
            on_stack[root] = True
            work: list[tuple[Hashable, Iterator[Hashable]]] = [
                (root, iter(self._successors[root]))
            ]

            while work:
                node, succ_iter = work[-1]
                recursed = False

                for succ in succ_iter:
                    if succ not in index_of:
                        index_of[succ] = counter
                        lowlink[succ] = counter
                        counter += 1
                        tarjan_stack.append(succ)
                        on_stack[succ] = True
                        work.append((succ, iter(self._successors[succ])))
                        recursed = True
                        break
                    if on_stack.get(succ, False):
                        if index_of[succ] < lowlink[node]:
                            lowlink[node] = index_of[succ]

                if recursed:
                    continue

                if lowlink[node] == index_of[node]:
                    scc: list[Hashable] = []
                    while True:
                        w = tarjan_stack.pop()
                        on_stack[w] = False
                        scc.append(w)
                        if w == node:
                            break
                    result.append(scc)

                work.pop()
                if work:
                    parent = work[-1][0]
                    if lowlink[node] < lowlink[parent]:
                        lowlink[parent] = lowlink[node]

        return result

    def find_cycles(self) -> list[list[Hashable]]:
        cycles: list[list[Hashable]] = []
        for scc in self.find_sccs():
            if len(scc) > 1:
                cycles.append(scc)
            elif scc[0] in self._successors[scc[0]]:
                cycles.append(scc)
        return cycles

    def is_acyclic(self) -> bool:
        return not self.find_cycles()

    def topological_sort(self) -> list[Hashable]:
        in_degree = {n: len(self._predecessors[n]) for n in self._successors}
        ready: deque[Hashable] = deque(n for n, d in in_degree.items() if d == 0)
        order: list[Hashable] = []

        while ready:
            node = ready.popleft()
            order.append(node)
            for succ in self._successors[node]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    ready.append(succ)

        if len(order) != len(self._successors):
            raise CycleError(self.find_cycles())

        return order

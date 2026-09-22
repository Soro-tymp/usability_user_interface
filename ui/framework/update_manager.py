"""
update_manager.py
"""


from __future__ import annotations

from typing import Any, Callable, Hashable, Mapping, Optional

import threading

from ui.framework.directed_graph import CycleError, DirectedGraph



FlagSet = Optional[frozenset]



class UpdateManager:
    """
    update_manager.py

    The UpdateManager owns the dependency graph and coordinates two-phase
    propagation of change notifications through it.

    **Model.** Nodes are Models, ViewModels, Bindings — anything participating
    in propagation. Edges declare dependencies: an edge ``subject -> observer``
    means "if ``subject`` records a payload during a batch, ``observer`` is
    a candidate for invocation in that batch." The graph is maintained
    acyclic; adding a cycle-creating edge raises :class:`CycleError` and
    leaves the graph unchanged.

    **Notify.** A subject calls :meth:`notify` to announce a change with an
    optional flag set. Flags are application-defined hashables describing
    which aspects changed; ``None`` means "check everything." The manager
    records the notification in the current batch's payload table (per-source
    flag accumulation: union of specific flag sets, with ``None`` absorbing
    any specific flags).

    **Two-phase batch.** When :meth:`notify` is called outside an in-progress
    batch, the manager runs a batch synchronously. Each batch consists of:

    Phase 1 — for every source in the batch's seed set (in insertion
    order), walk the graph in topological order and invoke
    ``on_notified(sources)`` on every non-seed node that has at least
    one contributing predecessor in the current payload table. Handlers
    may call ``self.notify(flags)`` to propagate the cascade further;
    in-flight propagation records into the same payload table so
    downstream nodes still ahead in the walk can see the contribution.

    Phase 2 — walk the graph in topological order and invoke
    ``on_invoked()`` on every node that had at least one contributing
    predecessor across the whole of phase 1. Phase 2 is for side-effecting
    work (typically widget updates). ``notify`` calls from inside an
    ``on_invoked`` handler defer to the next batch.

    If new ``notify`` calls accumulate during the batch (e.g. from worker
    threads), they enter the pending set for the next batch. After phase 2
    completes, the manager checks pending; if non-empty, it starts another
    batch. The drain loop continues until pending is empty.

    **Threading.** All mutation of internal state is guarded by an
    :class:`threading.RLock`. The lock is held for the entire batch, so
    worker-thread :meth:`notify` calls block until the GUI thread's
    batch completes. Under typical use, ``notify`` is called from the
    GUI thread; worker threads marshal through whatever mechanism is
    appropriate for the host application (e.g. ``QMetaObject.invokeMethod``).

    **Public surface.** :meth:`register`, :meth:`unregister`,
    :meth:`observe`, :meth:`unobserve`, :meth:`notify`. Internals
    (:meth:`_run_batch`, the payload tables, the lock) are not part of
    the contract.
    """
    def __init__(self, marshal=None) -> None:
        self._graph: DirectedGraph = DirectedGraph()
        # Pending captures notify calls that arrived during a batch. Consumed by _run_batches.
        self._pending: dict[Hashable, FlagSet] = {}
        self._in_phase_1: bool = False
        self._in_phase_2: bool = False
        self._lock: threading.RLock = threading.RLock()
        self._marshal = marshal or (lambda cb, *a, **k: cb(*a, **k))


    # ---------------------------------------------------------------- registration

    def register(self, node: Hashable) -> bool:
        """Register ``node`` with the manager. Idempotent.

        Returns True if newly registered, False if already present.
        """
        with self._lock:
            return self._graph.add_node(node)


    def unregister(self, node: Hashable) -> bool:
        """Remove ``node`` and all incident edges. Idempotent."""
        with self._lock:
            self._pending.pop(node, None)
            return self._graph.remove_node(node)


    def __contains__(self, node: Hashable) -> bool:
        with self._lock:
            return node in self._graph


    def __len__(self) -> int:
        with self._lock:
            return len(self._graph)

    # ---------------------------------------------------------------- dependencies

    def observe(self, observer: Hashable, subject: Hashable) -> bool:
        """Declare that ``observer`` observes ``subject``.

        Returns True if the dependency was newly added, False if it
        already existed. Raises :class:`CycleError` if adding this
        edge would create a cycle (graph left unchanged). Raises
        :class:`KeyError` if either node is not registered.
        """
        with self._lock:
            if subject not in self._graph:
                raise KeyError(f"subject not registered: {subject!r}")
            if observer not in self._graph:
                raise KeyError(f"observer not registered: {observer!r}")
            if self._graph.has_edge(subject, observer):
                return False
            self._graph.add_edge(subject, observer)
            cycles = self._graph.find_cycles()
            if cycles:
                self._graph.remove_edge(subject, observer)
                raise CycleError(cycles)
            return True


    def unobserve(self, observer: Hashable, subject: Hashable) -> bool:
        """Remove the dependency. Idempotent."""
        with self._lock:
            return self._graph.remove_edge(subject, observer)

    # ---------------------------------------------------------------- notify

    def notify(self, node: Hashable | None = None, flags: Any = None, propagate: bool = True) -> None:
        """Record that ``node`` has changed and (if idle) run a batch.

        ``flags`` is an optional iterable of application-defined
        hashables, or ``None`` for "check everything." Repeated
        notifications on the same source before its observers run
        accumulate per the union-with-None-absorbing rule.

        Outside a batch, this synchronously runs a batch with ``node``
        as the (initial) seed.

        Inside phase 1, if ``node`` is the node currently being
        processed, this is in-flight propagation: the flags merge into
        the current payload table so downstream nodes still ahead in
        the walk can see them.

        Inside phase 1 from any other source (mid-flush notify of a
        different node, e.g. from a worker thread that acquired the
        lock between handler invocations), or inside phase 2, the
        notification accumulates into the pending set for the next
        batch.
        """
        with self._lock:
            if node is not None:
                if node not in self._graph:
                    raise KeyError(f"node not registered: {node!r}")

                new_flags = self._coerce_flags(flags)

                if self._in_phase_1 or self._in_phase_2:
                    # Mid-batch notification of some other node; defer.
                    _accumulate(self._pending, node, new_flags)
                    return

                # Idle: this notify is the start of a new batch.
                _accumulate(self._pending, node, new_flags)

        if propagate:
            self._marshal(self._run_batches)


    # ---------------------------------------------------------------- batch loop

    def _run_batches(self) -> None:
        """Drain the pending set in batches until it is empty.

        Must be called with the lock held. Each iteration takes a
        snapshot of pending, runs phase 1 (per-source topological walks)
        followed by phase 2 (one topological walk for on_invoked), then
        loops if more notifications arrived during the batch.
        """
        while True:
            with self._lock:
                if len(self._pending) > 0:
                    pending = self._pending
                    self._pending = {}
                    self._run_phase_1(pending)
                    self._run_phase_2(pending)
                else:
                    break


    def _run_phase_1(self, pending: Mapping[Hashable, FlagSet]) -> None:
        """
        Run phase 1: walk topological order for each seed in
        insertion order, invoking on_notified on contributing
        non-seed nodes.

        Example:
          /> B \
        A        > D
          \> C /

        Topological sort places the nodes in an order that no node is visited before its
        predecessors are visited.
        For the above example, there are two potential orders:
         . A, B, C, D
         . A, C, B, D

        Predecessors:
            A -> None
            B -> A
            C -> A
            D -> B, C

        Update pattern:
        A.notify()
        This causes _run_batches to be called with the following:
        { A: None } # None here just means there are no flags to specify precisely what updated

        _run_phase_1 is called with pending = { A: None }
        Run through the nodes in partial node order A, C, B, D
        Evaluate A - A has no predecessors, and doesn't need its handler calling (it already notified
                     in any case, but if there was another element 'X' with no predecessors this would
                     also be the case) - nothing happens
                   - pending = {A: None}
        Evaluate C - C has A as a predecessor, and A is in the pending dictionary, therefore call its
                     on_notified handler - in this case, C checks and decides it doesn't need to update,
                     so its handler returns (False, None)
                   - pending = {A: None}
        Evaluate B - B has A as a predecessor, and A is in the pending dictionary, therefore call its
                     on_notified handler - B needs to update, and so calls (True, 'Foo'). 'Foo' here tells
                     us that some specific aspect of it needed to update.
                   - pending = {A: None, C: 'Foo'}

        """
        self._in_phase_1 = True
        try:
            order = self._graph.topological_sort()
            for node in order:
                preds = self._graph.predecessors(node)
                contributing = {p: pending[p]
                                for p in preds
                                if p in pending}
                if not contributing:
                    continue
                handler = getattr(node, "on_notified", None)
                if handler is None:
                    continue
                # self._current_node = node
                propagating, flags = handler(contributing)
                if propagating:
                    _accumulate(pending, node, flags)
        except Exception as e:
            print(e)
        finally:
            self._in_phase_1 = False


    def _run_phase_2(self, pending) -> None:
        """Run phase 2: walk topological order, invoking on_invoked on
        every node that had at least one contributing predecessor
        during phase 1."""
        self._in_phase_2 = True
        try:
            order = self._graph.topological_sort()
            for node in order:
                preds = self._graph.predecessors(node)
                if not any(p in pending for p in preds):
                    continue
                handler = getattr(node, "on_invoked", None)
                if handler is None:
                    continue
                handler()
        finally:
            self._in_phase_2 = False

    # ---------------------------------------------------------------- introspection

    @property
    def is_pending(self) -> bool:
        """Whether any notifications are pending for the next batch."""
        with self._lock:
            return bool(self._pending)


    def pending_sources(self) -> list[Hashable]:
        """List of sources currently in the pending set."""
        with self._lock:
            return list(self._pending)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _coerce_flags(flags: Any) -> FlagSet:
        """Normalize a user-supplied flags argument to None or frozenset."""
        if flags is None:
            return None
        if isinstance(flags, frozenset):
            return flags
        return frozenset(flags)



def _accumulate(table: dict[Hashable, FlagSet],
                source: Hashable,
                new_flags: FlagSet) -> None:
    """Set-union with None absorbing: any contribution of None makes
    the accumulated value None forever."""
    if source in table:
        existing = table[source]
        if existing is None or new_flags is None:
            table[source] = None
        else:
            table[source] = existing | new_flags
    else:
        table[source] = new_flags

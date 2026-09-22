"""
subject_observer.py

Subject and Observer protocols plus convenience mixins.

Two protocols describe the role a node plays in an UpdateManager's
dependency graph:

    Subject — can announce state changes via ``notify``.
    Observer — can be notified during phase 1 (``on_notified``) and
               invoked during phase 2 (``on_invoked``).

These are typing contracts; conformance is structural. Any class with
the right methods satisfies the protocol without inheriting from it.

The mixins (:class:`SubjectMixin`, :class:`ObserverMixin`) are
convenience bases that handle manager-registration boilerplate and
provide reasonable defaults. Concrete classes inherit them when the
defaults fit and implement the protocol directly otherwise.
"""


from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ui.framework.update_manager import UpdateManager


# ---------------------------------------------------------------------- protocols


@runtime_checkable
class Subject(Protocol):
    """A node that can announce state changes.

    The single method ``notify(flags=None)`` records that this subject
    has changed. ``flags`` is an optional iterable of application-defined
    hashables describing which aspects changed; ``None`` means
    "check everything," and is the conservative default.

    Concrete subjects typically call ``self.notify(flags)`` from their
    mutator methods. External code may also call it to force a
    propagation cycle.
    """

    def notify(self, flags: Any = None) -> None: ...


@runtime_checkable
class Observer(Protocol):
    """A node that participates in flush propagation.

    Observers receive two callbacks during a flush:

      ``on_notified(sources)``
          Phase 1. Called when at least one upstream subject contributed
          a payload during this batch. ``sources`` is a mapping from
          each contributing upstream to its accumulated flag set
          (or ``None`` if any contribution to that source was unflagged).
          The handler may inspect upstream state, decide whether its
          own state has meaningfully changed, and call
          ``self.notify(flags)`` to propagate the cascade further.

      ``on_invoked()``
          Phase 2. Called after phase 1 has fully settled, on every
          observer that had at least one contributing upstream during
          phase 1. Intended for side-effecting work like pushing state
          to widgets. Calling ``self.notify`` from inside ``on_invoked``
          defers to the next batch — phase 2 does not propagate.

    A typical ViewModel implements ``on_notified`` and leaves
    ``on_invoked`` as a no-op. A typical widget binding leaves
    ``on_notified`` as a no-op and implements ``on_invoked``. A node
    that has both kinds of work implements both.
    """

    def on_notified(self, sources: Mapping[Any, Optional[frozenset]]) -> None: ...
    def on_invoked(self) -> None: ...


# ---------------------------------------------------------------------- mixins


class SubjectMixin:
    """Default implementation of :class:`Subject`.

    Registers the node with an update manager on construction and
    routes :meth:`notify` calls through that manager. Concrete model
    elements typically inherit this mixin.
    """

    def __init__(self, manager: UpdateManager) -> None:
        self._manager = manager
        if manager is not None:
            manager.register(self)

    @property
    def manager(self) -> UpdateManager:
        return self._manager

    @manager.setter
    def manager(self, manager: UpdateManager):
        if self._manager is not None:
            self._manager.unregister(self)
        self._manager = manager
        if manager is not None:
            self._manager.register(self)

    def notify(self, flags: Any = None) -> None:
        """Announce that this subject's state has changed.

        Delegates to :meth:`UpdateManager.notify`. ``flags`` is an
        optional iterable of application-defined hashables; ``None``
        means "check everything."
        """
        if self._manager is not None:
            self._manager.notify(self, flags)


class ObserverMixin:
    """Default implementation of :class:`Observer`.

    Registers the node with an update manager on construction and
    provides no-op defaults for both ``on_notified`` and ``on_invoked``.
    Subclasses override whichever method they actually do work in.
    """

    def __init__(self, manager: UpdateManager) -> None:
        self._manager = manager
        manager.register(self)

    @property
    def manager(self) -> UpdateManager:
        return self._manager

    def observe(self, subject):
        self._manager.observe(self, subject)

    def unobserve(self, subject):
        self._manager.unobserve(self, subject)

    def on_notified(self, sources: Mapping[Any, Optional[frozenset]]) -> None:
        """Default: do nothing. Override to react to upstream changes."""
        return False, None

    def on_invoked(self) -> None:
        """Default: do nothing. Override to perform phase-2 side effects."""
        pass



class SubjectObserverMixin:
    """Default implementation of :class:`Subject` and :class:`Observer`.

    Registers the node with an update manager on construction and:
     - routes :meth:`notify` calls through that manager. Concrete model
    elements typically inherit this mixin.
     - provides no-op defaults for both ``on_notified`` and ``on_invoked``.
    Subclasses override whichever method they actually do work in.
    """

    def __init__(self, manager: UpdateManager) -> None:
        self._manager = manager
        manager.register(self)

    @property
    def manager(self) -> UpdateManager:
        return self._manager

    def notify(self, flags: Any = None) -> None:
        """Announce that this subject's state has changed.

        Delegates to :meth:`UpdateManager.notify`. ``flags`` is an
        optional iterable of application-defined hashables; ``None``
        means "check everything."
        """
        self._manager.notify(self, flags)

    def observe(self, subject):
        self._manager.observe(self, subject)

    def unobserve(self, subject):
        self._manager.unobserve(self, subject)

    def on_notified(self, sources: Mapping[Any, Optional[frozenset]]) -> None:
        """Default: do nothing. Override to react to upstream changes."""
        return False, None

    def on_invoked(self) -> None:
        """Default: do nothing. Override to perform phase-2 side effects."""
        pass

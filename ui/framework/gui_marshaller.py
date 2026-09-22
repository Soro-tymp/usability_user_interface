from functools import partial

import threading

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot



class GuiMarshaller(QObject):
    """Runs a callable on the thread that owns this object (the GUI thread,
    when constructed there). Calling the marshaller from any thread posts the
    callable to the owning thread's event loop via a queued signal.

    Reusable: call it as many times as you like. Arguments supplied at call
    time are bound into the callable before dispatch.
    """

    _invoke = pyqtSignal(object)  # carries a zero-arg callable

    def __init__(self, parent):
        super().__init__(parent)
        self._invoke.connect(self._run)
        self._gui_thread_id = threading.get_ident()

    @pyqtSlot(object)
    def _run(self, fn):
        fn()

    def __call__(self, fn, *args, **kwargs):
        # Bind args now; the signal carries a single zero-arg callable.
        if threading.get_ident() == self._gui_thread_id:
            fn(*args, **kwargs)
        else:
            self._invoke.emit(partial(fn, *args, **kwargs) if (args or kwargs) else fn)

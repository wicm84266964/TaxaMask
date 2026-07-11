import os
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication, QPushButton
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from AntSleap.ui.tif_workbench_view import TifWorkbenchView


class SignalOwner(QObject if QApplication is not None else object):
    if QApplication is not None:
        triggered = Signal()


@unittest.skipUnless(QApplication is not None, "PySide6 is required for signal router tests")
class TifWorkbenchSignalRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_view_scope_rejects_undeclared_widget_access(self):
        class Workbench:
            button = QPushButton("A")

        view = TifWorkbenchView(Workbench())
        view.register_scope("shell", "button")

        self.assertIsInstance(view.require("shell", "button"), QPushButton)
        with self.assertRaises(KeyError):
            view.require("annotation", "button")

    def test_bind_is_idempotent_and_unbind_stops_future_delivery(self):
        owner = SignalOwner()
        router = TifWorkbenchSignalRouter()
        calls = []

        def on_triggered():
            calls.append("called")

        self.assertTrue(router.bind("shell", "action", owner.triggered, on_triggered))
        self.assertFalse(router.bind("shell", "action", owner.triggered, on_triggered))
        owner.triggered.emit()
        self.assertEqual(calls, ["called"])
        self.assertEqual(router.connection_count("shell"), 1)

        self.assertEqual(router.unbind_scope("shell"), 1)
        owner.triggered.emit()
        self.assertEqual(calls, ["called"])


if __name__ == "__main__":
    unittest.main()

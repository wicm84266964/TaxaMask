import unittest

from AntSleap.ui.main_window_workers import InferenceThread


class _RecordingEngine:
    def __init__(self, failing_image=""):
        self.failing_image = failing_image
        self.calls = []

    def predict_full_pipeline(self, image_path, **kwargs):
        context = dict(kwargs.get("model_profile_context") or {})
        self.calls.append((str(image_path), context))
        if str(image_path) == self.failing_image:
            raise RuntimeError("synthetic inference failure")
        return {"polygons": {}, "auto_boxes": {}, "scores": {}, "meta": {}}


def _thread(engine, images):
    return InferenceThread(
        engine,
        images,
        ["Head"],
        ["Head"],
        {
            "conf": 0.1,
            "adapt": 0.4,
            "pad": 0.4,
            "noise_floor": 0.15,
            "poly_epsilon": 2.0,
        },
        model_profile_context={"active_profile_id": "profile_test"},
    )


class InferenceThreadRuntimeTests(unittest.TestCase):
    def test_batch_assigns_distinct_prediction_ids(self):
        engine = _RecordingEngine()
        thread = _thread(engine, ["ant_1.png", "ant_2.png"])
        results = []
        finished = []
        thread.result_signal.connect(lambda image, payload: results.append((image, payload)))
        thread.finished_signal.connect(lambda: finished.append(True))

        thread.run()

        self.assertEqual([item[0] for item in results], ["ant_1.png", "ant_2.png"])
        self.assertEqual(finished, [True])
        prediction_ids = [call[1]["prediction_run_id"] for call in engine.calls]
        self.assertEqual(len(set(prediction_ids)), 2)
        self.assertTrue(all(value.startswith(thread.prediction_batch_id) for value in prediction_ids))

    def test_batch_reports_failure_and_still_finishes(self):
        engine = _RecordingEngine(failing_image="bad.png")
        thread = _thread(engine, ["ant_1.png", "bad.png", "ant_3.png"])
        errors = []
        finished = []
        thread.error_signal.connect(
            lambda image, message: errors.append((image, message))
        )
        thread.finished_signal.connect(lambda: finished.append(True))

        thread.run()

        self.assertEqual(len(engine.calls), 2)
        self.assertEqual(errors, [("bad.png", "synthetic inference failure")])
        self.assertEqual(finished, [True])


if __name__ == "__main__":
    unittest.main()

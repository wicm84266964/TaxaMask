"""One persistent background thread per instance workbench."""
from PySide6.QtCore import QObject, Signal, Slot


class InstanceJobWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.sam = None
        self.sam_options = None

    def sam_predict(self, image_path, options, prompt, project_root=None):
        if project_root is not None:
            from ..core.instance_model_jobs import run_model_job
            return run_model_job(project_root, lambda: self.sam_predict(image_path, options, prompt))
        from ..core.sam_helper import SAMWorker
        if self.sam is None or self.sam_options != options:
            self.sam = SAMWorker(model_type=options["model"], device=options["device"])
            self.sam.load_model()
            self.sam_options = dict(options)
        return self.sam.predict_instance_masks(image_path, **prompt)

    @Slot(object)
    def execute(self, job):
        try:
            self.finished.emit(job(self))
        except Exception as exc:
            self.failed.emit(str(exc))

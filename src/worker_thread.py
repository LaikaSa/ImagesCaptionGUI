from PySide6.QtCore import QThread, Signal

class WorkerThread(QThread):
    finished = Signal(object)  # For success result
    error = Signal(str)       # For error message
    progress = Signal(str)    # For progress updates

    def __init__(self, task_func, **kwargs):  # Changed to only accept kwargs
        super().__init__()
        self.task_func = task_func
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.task_func(**self.kwargs)  # Pass only kwargs
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
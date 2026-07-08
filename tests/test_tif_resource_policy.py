import unittest

from AntSleap.core.tif_resource_policy import (
    RESOURCE_KIND_COMMIT_MEMORY,
    RESOURCE_KIND_GPU_PREVIEW,
    RESOURCE_KIND_SYSTEM_MEMORY,
    RESOURCE_KIND_VOLUME_IO,
    classify_resource_exception,
    is_commit_memory_issue,
)


class TifResourcePolicyTests(unittest.TestCase):
    def test_winerror_1455_is_commit_memory_issue(self):
        exc = OSError(1455, "页面文件太小，无法完成操作。")
        exc.winerror = 1455

        issue = classify_resource_exception(exc, operation="load_edit_volume", path="labels/working_edit.ome.zarr")

        self.assertEqual(issue.kind, RESOURCE_KIND_COMMIT_MEMORY)
        self.assertTrue(is_commit_memory_issue(issue))
        self.assertTrue(issue.recoverable)
        self.assertTrue(issue.edit_limited)
        self.assertEqual(issue.winerror, 1455)
        self.assertEqual(issue.operation, "load_edit_volume")

    def test_memory_error_is_system_memory_issue(self):
        issue = classify_resource_exception(MemoryError("cannot allocate array"), operation="build_preview")

        self.assertEqual(issue.kind, RESOURCE_KIND_SYSTEM_MEMORY)
        self.assertTrue(issue.edit_limited)

    def test_gpu_opengl_error_is_preview_resource_issue(self):
        issue = classify_resource_exception(RuntimeError("OpenGL texture allocation failed"), operation="gpu_upload")

        self.assertEqual(issue.kind, RESOURCE_KIND_GPU_PREVIEW)
        self.assertFalse(issue.edit_limited)

    def test_regular_os_error_is_volume_io_issue(self):
        issue = classify_resource_exception(OSError("file is locked"), operation="load_label")

        self.assertEqual(issue.kind, RESOURCE_KIND_VOLUME_IO)
        self.assertTrue(issue.edit_limited)


if __name__ == "__main__":
    unittest.main()

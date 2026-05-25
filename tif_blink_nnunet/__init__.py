"""Experimental TIF-Blink adapters for nnU-Net v2.

The package intentionally keeps top-level imports light so a repository without
PyTorch or nnU-Net v2 can still inspect docs and import the trainer symbol.
Import submodules such as ``boundary3d`` or ``views3d`` when running tests or
training in a PyTorch environment.
"""

__all__: list[str] = []

# Ant-Code Agent Center Source

This directory contains the first-party Ant-Code Agent Center source that is bundled with TaxaMask.

Ant-Code is part of the TaxaMask source release, not a third-party dependency. The `vendor/ant-code` directory name is retained for runtime layout compatibility and to keep the Node dashboard package isolated from the Python workbench, but the source in this directory is an original TaxaMask Agent Center component.

The public TaxaMask release keeps only the runtime source, assets, package metadata, and generic templates needed for the bundled dashboard. Private gateway configs, local handoff notes, historical development logs, and machine-specific paths are intentionally excluded.

Unless a file states otherwise, the Ant-Code Agent Center source is covered by the same repository license and attribution requirements described in the root `LICENSE` and `NOTICE` files.

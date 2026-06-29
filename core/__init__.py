"""Top-level package for legacy modules used by tests.

Some tests add ``AntSleap`` to ``sys.path`` and import application modules as
``core.*``.  Keep this package compatible when the repository-root ``core``
package is imported first.
"""

from pathlib import Path


antsleap_core = Path(__file__).resolve().parents[1] / "AntSleap" / "core"
if antsleap_core.is_dir():
    antsleap_text = str(antsleap_core)
    if antsleap_text not in __path__:
        __path__.append(antsleap_text)

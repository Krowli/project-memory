"""`python -m pagelore` — the entry point the npm wrapper uses.

The wheel is refused by pip on an interpreter below `requires-python`, so the
`lore` console script never reaches an old Python. The npm route has no package
metadata and therefore nothing that has already refused, so the floor is checked
here instead.

Exit 69 (EX_UNAVAILABLE) and print nothing: the JS shim reads it as "this
interpreter is too old, try the next candidate" and prints one message after it
has tried them all. A message here would print once per candidate.

Like `__init__.py`, this file must parse on any Python 3 — it is read before the
check it performs.
"""
import sys

if sys.version_info < (3, 9):
    raise SystemExit(69)

from pagelore.cli import main

raise SystemExit(main())

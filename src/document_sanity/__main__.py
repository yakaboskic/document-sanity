"""`python -m document_sanity` — the same CLI as `document-sanity`."""

import sys

from .cli import main

sys.exit(main())

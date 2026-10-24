#!/usr/bin/env python3
"""Install the reviewed Meineke FCG III source as work-level CTS editions."""

from __future__ import annotations

from datetime import date

import install_meineke_volume2 as compiler


compiler.VERSION = "meineke1840-grc1"
compiler.LABEL = "Greek (Meineke, 1840; OCR draft)"
compiler.SOURCE = compiler.Path(
    "sources/volumes/meineke/meineke.fragmenta-comicorum-graecorum.vol3.xml"
)
compiler.VOLUME_NUMBER = "3"
compiler.PUBLICATION_YEAR = "1840"
compiler.REVISION_DATE = date.today().isoformat()
compiler.REPORT = compiler.Path(
    "sources/volumes/meineke/meineke-fcg3-install-report.json"
)


if __name__ == "__main__":
    compiler.main()

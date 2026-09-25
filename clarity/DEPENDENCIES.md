# Dependency and license inventory

MoneyMoney's source uses the repository's MIT license. Dependencies retain their
own terms. They are installed through package managers, not copied into this
release. No model weights, fonts, broker documents or third-party assets are
vendored in `clarity/`.

Direct runtime/build/test dependencies, checked against installed package metadata
on 25 September 2026:

| Dependency | License |
| --- | --- |
| React, React DOM, Recharts | MIT |
| Lucide React | ISC |
| Vite, React Vite plugin, React/Node type declarations | MIT |
| TypeScript | Apache-2.0 |
| FastAPI | MIT |
| uvicorn | BSD-3-Clause |
| python-multipart | Apache-2.0 |
| casparser, casparser-isin | MIT |
| pikepdf | MPL-2.0 |
| pypdfium2 | BSD-3-Clause / Apache-2.0, plus PDFium dependency licenses |
| pdfplumber | MIT |
| httpx | BSD-3-Clause |
| pytest | MIT |

`package-lock.json` fixes the npm dependency graph. `requirements.lock.txt` records
the tested Python package versions, including transitive dependencies. Consult
each installed distribution's license files for its full terms and notices,
especially the PDF parsing libraries. These version locks are not hashes of
third-party package artifacts or a guarantee that future advisories will be absent.

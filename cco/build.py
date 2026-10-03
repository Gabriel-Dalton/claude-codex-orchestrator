"""Minimal standard-library PEP 517 backend. No build dependencies."""

import base64
import csv
import hashlib
import io
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DIST = "cco-0.1.0.dist-info"
METADATA = "Metadata-Version: 2.4\nName: cco\nVersion: 0.1.0\nSummary: Claude Codex Orchestrator\nRequires-Python: >=3.11\nLicense-Expression: MIT\n"


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    name = "cco-0.1.0-py3-none-any.whl"
    files = {"cco/" + p.name: p.read_bytes() for p in (ROOT / "cco").glob("*.py")}
    files.update({"cco/templates/" + p.name: p.read_bytes() for p in (ROOT / "templates").glob("*.md")})
    files.update({
        DIST + "/METADATA": METADATA.encode(),
        DIST + "/WHEEL": b"Wheel-Version: 1.0\nGenerator: cco\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        DIST + "/entry_points.txt": b"[console_scripts]\ncco = cco.cli:main\n",
        DIST + "/licenses/LICENSE": (ROOT / "LICENSE").read_bytes(),
    })
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for path, content in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
        writer.writerow((path, "sha256=" + digest, len(content)))
    writer.writerow((DIST + "/RECORD", "", ""))
    files[DIST + "/RECORD"] = record.getvalue().encode()
    Path(wheel_directory).mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(Path(wheel_directory) / name, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return name


def build_sdist(sdist_directory, config_settings=None):
    name = "cco-0.1.0.tar.gz"
    Path(sdist_directory).mkdir(parents=True, exist_ok=True)
    with tarfile.open(Path(sdist_directory) / name, "w:gz") as archive:
        for pattern in ("cco/*.py", "templates/*.md", "tests/*.py", "docs/*.md", "skill/*.md", "*.toml", "README.md", "LICENSE"):
            for path in ROOT.glob(pattern):
                archive.add(path, arcname="cco-0.1.0/" + path.relative_to(ROOT).as_posix())
    return name

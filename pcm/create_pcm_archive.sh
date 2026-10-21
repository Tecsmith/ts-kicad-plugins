#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python3 - "${1:-0.0.0}" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile

version = sys.argv[1]
if not re.fullmatch(r"\d{1,4}(\.\d{1,4}(\.\d{1,6})?)?", version):
    raise SystemExit("Use a numeric PCM version, for example 1.0.0.")

metadata = json.loads(Path("pcm/metadata.template.json").read_text())
metadata["versions"][0]["version"] = version
archive = Path(f"pcm/ts-kicad-plugins-{version}.zip")
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
    for path in sorted(Path("plugins").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".png", ".svg"}:
            package.write(path, path.as_posix())
    package.write("resources/icon.png")
    package.writestr("metadata.json", json.dumps(metadata, indent=2) + "\n")
    install_size = sum(entry.file_size for entry in package.infolist())

values = {
    "VERSION": version,
    "DOWNLOAD_SHA256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "DOWNLOAD_SIZE": archive.stat().st_size,
    "DOWNLOAD_URL": f"https://github.com/tecsmith/ts-kicad-plugins/releases/download/{version}/{archive.name}",
    "INSTALL_SIZE": install_size,
    "KICAD_VERSION": metadata["versions"][0]["kicad_version"],
    "PROJECT_NAME": metadata["name"],
}
output = "".join(f"{key}={value}\n" for key, value in values.items())
if os.environ.get("GITHUB_ENV"):
    with open(os.environ["GITHUB_ENV"], "a") as env:
        env.write(output)
print(f"Created {archive}")
print(output, end="")
PY

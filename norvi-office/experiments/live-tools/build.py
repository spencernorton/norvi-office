"""Build the standalone Norvi Document Tools extension."""
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

source = Path(__file__).resolve().parent / "extension"
output = Path(sys.argv[1])
with ZipFile(output, "x", ZIP_DEFLATED) as archive:
    for file in sorted(source.rglob("*")):
        if file.is_file() and file.suffix in {".py", ".xml", ".xcu", ".soc"}:
            archive.write(file, file.relative_to(source))

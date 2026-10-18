"""Build a source-only ZIP, excluding local secrets, private data and dependencies."""
import argparse
from pathlib import Path
import zipfile

from check_package import ROOT,check

parser=argparse.ArgumentParser()
parser.add_argument("output",type=Path)
args=parser.parse_args()
files=check()
args.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(args.output,"w",zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path,path.relative_to(ROOT).as_posix())
print(f"Created source ZIP: {args.output.resolve()} ({args.output.stat().st_size:,} bytes)")

"""Verify the deliverable source set. Never enumerate contents of excluded private folders."""
import os
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={".git",".venv","node_modules","private","__pycache__",".pytest_cache","uploads","test-results","htmlcov"}
ALLOWED={".py",".md",".json",".toml",".sql",".txt",".yml",".yaml",".mjs",".png",".jpg"}
SPECIAL={".gitignore",".python-version"}
PATTERNS=[r"AIza[0-9A-Za-z_-]{30,}",r"sb_secret_[0-9A-Za-z_-]{25,}",r"gh[pousr]_[A-Za-z0-9]{30,}",r"github_pat_[A-Za-z0-9_]{30,}",
          r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{40,}\.[A-Za-z0-9_-]{20,}"]


def source_files():
    for parent,dirs,files in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in EXCLUDED]
        for name in sorted(files):
            path=Path(parent)/name
            if name=="secrets.toml" or name.startswith(".env"):
                continue
            if path.suffix in ALLOWED or name in SPECIAL:
                yield path


def check():
    sys.path.insert(0,str(ROOT))
    from scripts.build_schema import build
    from atlas.models import ImportProposal
    from atlas.catalog_models import Opportunity
    from scripts.build_catalog_schema import build as build_catalog
    if (ROOT/"supabase/migrations/001_learning_atlas.sql").read_text(encoding="utf-8")!=build():
        raise SystemExit("SQL does not match its generator. Run scripts/build_schema.py and recheck.")
    ImportProposal.model_validate_json((ROOT/"examples/import-mini.json").read_text(encoding="utf-8"))
    if (ROOT/"supabase/migrations/002_discovery_catalog.sql").read_text(encoding="utf-8")!=build_catalog():
        raise SystemExit("Catalog SQL does not match its generator.")
    seed=json.loads((ROOT/"data/catalog_seed.json").read_text(encoding="utf-8"))
    items=[Opportunity.model_validate(i) for i in seed['opportunities']]
    if len({i.identity() for i in items})!=len(items):
        raise SystemExit("Duplicate catalog seed identity.")
    files=list(source_files())
    for path in files:
        if path.suffix in {".png",".jpg"}:
            continue
        text=path.read_text(encoding="utf-8")
        if any(re.search(pattern,text) for pattern in PATTERNS):
            raise SystemExit("Potential secret in deliverable file: "+str(path.relative_to(ROOT)))
    print(f"Package checks passed: {len(files)} source files; migration and import fixture valid; no matching secret patterns.")
    return files


if __name__=="__main__":
    check()

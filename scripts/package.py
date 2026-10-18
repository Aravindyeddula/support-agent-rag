"""Build a source-only ZIP without credentials, databases, or virtual environments."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT.parent / "atlas-support-agent-rag.zip"
EXCLUDED = {".venv", ".git", ".data", "__pycache__", ".pytest_cache", "test-results"}


def main():
    count = 0
    with ZipFile(DESTINATION, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or EXCLUDED.intersection(relative.parts):
                continue
            if path.name.startswith(".env") and path.name != ".env.example":
                continue
            if path.suffix in {".zip", ".pyc", ".sqlite3"} or ".sqlite3-" in path.name:
                continue
            archive.write(path, Path("support-agent-rag") / relative)
            count += 1
    print(f"Packaged {count} source and documentation files: {DESTINATION}")


if __name__ == "__main__":
    main()

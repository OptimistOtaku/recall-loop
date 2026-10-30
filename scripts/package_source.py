"""Create a source handoff without credentials, databases, caches, or environments."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent.parent
destination = root.parent / "bunch-source.zip"
folders = ["recall_loop", "frontend/src", "frontend/test", "frontend/dist", "tests", "scripts", "docs", "evaluation", "screenshots"]
files = ["README.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "uv.lock", "requirements.lock",
         "Dockerfile", ".dockerignore", ".gitignore", "render.yaml", "Start-RecallLoop.ps1",
         "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json",
         "frontend/vite.config.ts", "frontend/index.html"]
paths = [root / name for name in files]
for folder in folders:
    paths.extend((root / folder).rglob("*"))
with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(set(paths)):
        relative = path.relative_to(root)
        if path.is_file() and "__pycache__" not in relative.parts and path.suffix != ".pyc":
            archive.write(path, Path("bunch") / relative)
print(f"Created {destination.name}: {destination.stat().st_size:,} bytes")

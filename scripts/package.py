"""Stage the local Typst package and a self-contained web-editor project.

Freedoom Phase 1 and its notices provide freely licensed game data. The complete
engine source and build scripts accompany the WASM in both distributions.
"""
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = (ROOT / 'typst.toml').read_text()
    name = re.search(r'^name = "([^"]+)"$', manifest, re.M)[1]
    version = re.search(r'^version = "([^"]+)"$', manifest, re.M)[1]
    reference = f'@preview/{name}:{version}'
    if reference not in (ROOT / 'template/main.typ').read_text():
        raise SystemExit('Template import must match the package name/version.')
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    destination = build / 'packages/preview' / name / version
    web = build / f'{name}-web'
    with tempfile.TemporaryDirectory(prefix='package-', dir=build) as temporary:
        stage = Path(temporary)
        package = stage / 'package'
        package.mkdir()
        for filename in ('lib.typ', 'typst.toml', 'README.md', 'LICENSE', 'thumbnail.png',
                         'engine/core.typ', 'engine/controls.typ', 'engine/doom.wasm',
                         'scripts/build_engine.py', 'scripts/wasm_imports.py',
                         'docs/development.md', 'demo.gif'):
            target = package / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / filename, target)
        for directory in ('template', 'engine/native', 'vendor/doomgeneric', 'assets'):
            shutil.copytree(ROOT / directory, package / directory,
                            ignore=shutil.ignore_patterns('.git', '__pycache__', '*.o', 'screenshots', 'doom1.wad'))
        # Use the same runtime in the web project; only the import is local.
        web_stage = stage / 'web'
        shutil.copytree(package, web_stage)
        (web_stage / 'main.typ').write_text((package / 'template/main.typ').read_text().replace(
            f'"{reference}"', '"lib.typ"'))
        for source, target in ((package, destination), (web_stage, web)):
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(source), target)
    archive = build / f'{name}-web.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for file in sorted(web.rglob('*')):
            if file.is_file():
                output.write(file, file.relative_to(web))
    print(f'Package: {destination}')
    print(f'Web project: {archive}')
    print(f'typst init --package-path {build / "packages"} {reference} <new-directory>')


if __name__ == '__main__':
    main()

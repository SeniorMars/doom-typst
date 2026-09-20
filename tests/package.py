"""Integration checks against an staged preview package, not repository imports."""
import json
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package-path', type=Path, default=ROOT / 'build/packages')
PACKAGES = parser.parse_args().package_path.resolve()
PACKAGE = PACKAGES / 'preview/doom-wasm/0.1.0'


def run(*args, cwd, succeeds=True):
    result = subprocess.run(['typst', *args, '--package-path', str(PACKAGES)],
                            cwd=cwd, text=True, capture_output=True, timeout=90)
    if (result.returncode == 0) != succeeds:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout if succeeds else result.stderr


def state(project, *inputs):
    args = [item for value in inputs for item in ('--input', value)]
    return json.loads(run('eval', '--in', 'main.typ', *args,
                          'query(<doom-engine>).first().value', cwd=project))


def main():
    assert [p.name for p in PACKAGE.rglob('*.wad')] == ['freedoom1.wad']
    assert (PACKAGE / 'assets/FREEDOOM-LICENSE.txt').is_file()
    assert (PACKAGE / 'template/LICENSE').is_file()
    assert (PACKAGE / 'engine/native/typst_doom.c').is_file()
    assert (PACKAGE / 'vendor/doomgeneric/doomgeneric/doomgeneric.c').is_file()
    with tempfile.TemporaryDirectory(prefix='package-test-', dir=ROOT / 'build') as directory:
        root = Path(directory)
        project = root / 'game'
        run('init', '@preview/doom-wasm:0.1.0', str(project), cwd=root)
        run('compile', 'main.typ', 'setup.png', cwd=project)
        source = project / 'main.typ'
        starter = source.read_text()
        original = state(project, 'actions=')
        assert original['health'] == 100 and original['map'] == 1
        expected = state(project, 'actions=wwffff')
        source.write_text(source.read_text().replace(
            '// actions: (fire: ("v",), use: ("u",)),',
            'actions: (fire: ("v",), use: ("u",), forward: ("w", "↑")),'
        ) + '\n↑↑vvvv\n')
        assert state(project) == expected, 'Remapped document input differs from canonical input'
        assert state(project, 'actions=wwvvvv') == expected, 'CLI input bypassed custom bindings'
        assert state(project, 'actions=fff') == original, 'Old binding still active'
        run('compile', 'main.typ', 'game.png', cwd=project)

        # Reads of user files must happen in the project, not the package root.
        exported = run('eval', '--in', 'main.typ', '--input', 'export-save=true',
                       'query(<doom-save>).first().value', cwd=project)
        (project / 'save.json').write_text(exported)
        loaded = state(project, 'save=save.json', 'actions=')
        for key in ('x', 'y', 'angle', 'health', 'ammo', 'map', 'episode'):
            assert loaded[key] == expected[key], f'Save restore changed {key}'
        assert state(project, 'save=save.json', 'actions=r') == original

        # Reject ambiguous bindings and malformed action dictionaries cleanly.
        for actions, message in (
            ('(fire: ("w",))', 'bound more than once'),
            ('(unknown: ("v",))', 'Unknown action'),
            ('(fire: "v")', 'keys must be a tuple'),
            ('(fire: ("vv",))', 'one non-whitespace character'),
            ('(fire: (" ",))', 'one non-whitespace character'),
        ):
            (project / 'invalid.typ').write_text(
                '#import "@preview/doom-wasm:0.1.0": game\n#show: game.with(actions: ' + actions + ')')
            error = run('compile', 'invalid.typ', 'invalid.pdf', cwd=project, succeeds=False)
            assert message in error, error

        # Test the actual web zip after extraction, without a package lookup.
        web = root / 'web'
        with zipfile.ZipFile(ROOT / 'build/doom-wasm-web.zip') as archive:
            assert [name for name in archive.namelist() if name.lower().endswith('.wad')] == ['assets/freedoom1.wad']
            archive.extractall(web)
        subprocess.run(['typst', 'compile', 'main.typ', 'setup.png'], cwd=web, check=True, timeout=90)
        shutil.copyfile(ROOT / 'assets/freedoom1.wad', web / 'doom1.wad')
        entry = web / 'main.typ'
        entry.write_text(entry.read_text().replace('// wad: read', 'wad: read') + '\nwwffff\n')
        subprocess.run(['typst', 'compile', 'main.typ', 'game.png'], cwd=web, check=True, timeout=90)
    print('Package checks passed: init, bundled Freedoom, gameplay, bindings, CLI, saves, and web zip.')


if __name__ == '__main__':
    main()

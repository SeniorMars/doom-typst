"""Measure cold compilation and warm typed-input updates (requires file watching)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import sys
try:
    import resource
except ImportError:
    resource = None

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commands', type=int, default=700)
    parser.add_argument('--edits', type=int, default=8)
    parser.add_argument('--chunk-size', type=int, default=16)
    parser.add_argument('--engine', type=Path, default=ROOT / 'engine/doom.wasm')
    parser.add_argument('--wad', type=Path, default=ROOT / 'assets/freedoom1.wad')
    args = parser.parse_args()
    if args.commands < 0 or args.edits < 1:
        parser.error('commands must be nonnegative and edits must be positive')
    if not 1 <= args.chunk_size <= 4096:
        parser.error('chunk size must be 1–4096')
    (ROOT / 'build').mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='benchmark-', dir=ROOT / 'build'))
    source, image, log = [directory / name for name in ('main.typ', 'frame.png', 'watch.log')]
    shutil.copyfile(args.engine, directory / 'engine.wasm')
    # The public wrapper now imports the shared engine and keybinding modules.
    core = (ROOT / 'engine/core.typ').read_text().replace('plugin("doom.wasm")', 'plugin("engine.wasm")')
    (directory / 'core.typ').write_text(core)
    shutil.copyfile(ROOT / 'engine/controls.typ', directory / 'controls.typ')
    shutil.copyfile(args.wad, directory / 'game.wad')
    wrapper = '#import "core.typ" as core\n#let doom = core.doom.with(wad: read("game.wad", encoding: none))\n'
    (directory / 'wrapper.typ').write_text(wrapper)
    prefix = f'#import "wrapper.typ": doom\n#show: doom.with(help: false, chunk-size: {args.chunk_size})\n\n'
    actions = ('wwwwjjffex' * ((args.commands + 9) // 10))[:args.commands]
    source.write_text(prefix + actions + '\n')

    def completed_count():
        content = log.read_text() if log.exists() else ''
        if 'error:' in content:
            raise RuntimeError(content[-4000:])
        return content.count('compiled successfully')

    def wait_for_compile(previous, start):
        while time.monotonic() - start < 120:
            if process.poll() is not None:
                raise RuntimeError(log.read_text())
            if completed_count() > previous:
                return {
                    'seconds': round(time.monotonic() - start, 4),
                    'sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                }
            time.sleep(.01)
        raise RuntimeError('Watch timed out; file notifications may be blocked.\n' + log.read_text())

    process = None
    try:
        with log.open('w') as stream:
            start = time.monotonic()
            process = subprocess.Popen(['typst', 'watch', '--root', str(ROOT), str(source), str(image)],
                                       cwd=ROOT, stdout=stream, stderr=stream)
            report = {'commands': args.commands, 'chunk_size': args.chunk_size, 'engine_sha256': hashlib.sha256((directory / 'engine.wasm').read_bytes()).hexdigest(), 'cold': wait_for_compile(0, start), 'warm': []}
            time.sleep(1)  # Allow the initial file watches to be registered.
            for i in range(args.edits):
                previous = completed_count()
                start = time.monotonic()
                source.write_text(prefix + actions + 'w' * (i + 1) + '\n')
                report['warm'].append(wait_for_compile(previous, start))
                time.sleep(.1)
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        shutil.rmtree(directory)
    if resource is not None:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        report['peak_rss_bytes'] = usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        report['cpu_seconds'] = round(usage.ru_utime + usage.ru_stime, 4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

"""Measure cold compilation and warm typed-input updates (requires file watching)."""
import argparse
import hashlib
import json
import re
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
    parser.add_argument('--runner', choices=('typst', 'tinymist'), default='typst',
                        help='PNG export or Tinymist preview packet delivery (requires Node)')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commands', type=int, default=700)
    parser.add_argument('--edits', type=int, default=8)
    parser.add_argument('--mode', choices=('chunked', 'full', 'c-cache', 'package'), default='chunked',
                        help='Cached chunks or one C advance call for the whole history')
    parser.add_argument('--edit-pattern', choices=('append', 'mixed', 'tail', 'rewind', 'session'), default='append')
    parser.add_argument('--chunk-size', type=int, default=16)
    parser.add_argument('--engine', type=Path, default=ROOT / 'engine/doom.wasm')
    parser.add_argument('--wad', type=Path, default=ROOT / 'assets/freedoom1.wad')
    args = parser.parse_args()
    if args.commands < 0 or args.edits < 1:
        parser.error('commands must be nonnegative and edits must be positive')
    if not 1 <= args.chunk_size <= 4096:
        parser.error('chunk size must be 1–4096')
    actions = ('wwwwjjffex' * ((args.commands + 9) // 10))[:args.commands]
    histories = edit_histories(actions, args.edit_pattern, args.edits)
    limit = 4096 if args.mode == 'full' else 65536
    if args.mode != 'chunked' and max(map(len, [actions, *histories])) > limit:
        parser.error(f'{args.mode} accepts at most {limit} commands')
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='benchmark-', dir=ROOT / 'build') as directory:
        report = run_benchmark(args, Path(directory), actions, histories)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def edit_histories(actions, pattern, count):
    """Build the workload once, so validation and execution use identical inputs."""
    if pattern == 'session':
        histories = []
        history = actions
        for i in range(count):
            if i and i % 499 == 0:
                history += 'r'
            elif i and i % 127 == 0:
                middle = len(history) // 2
                history = history[:middle] + 's' + history[middle + 1:]
            elif i and i % 31 == 0:
                history = history[:-4]
            elif i % 251 in (249, 250):
                history += 'p'
            else:
                history += 'wwjjffex'[i % 8]
            histories.append(history)
        return histories
    if pattern == 'append':
        return [actions + 'w' * (i + 1) for i in range(count)]
    if pattern == 'mixed':
        middle = len(actions) // 2
        cycle = [actions + 'w', actions + 'ww', actions[:-1],
                 actions[:middle] + 's' + actions[middle + 1:],
                 actions, actions + 'www', actions[:middle], actions + 'wwww']
    elif pattern == 'tail':
        cycle = [actions + 'w', actions + 'ww', actions[:-1],
                 actions[:-2] + 'ss', actions + 'www', actions[:-3],
                 actions[:-4] + 'jj', actions + 'wwww']
    elif pattern == 'rewind':
        cycle = [actions + 'w' * n for n in (16, 32, 48, 64, 15, 31, 47, 65)]
    else:
        raise ValueError(f'Unknown edit pattern: {pattern}')
    return [cycle[i % len(cycle)] for i in range(count)]


def stop_process(process):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def current_rss(pid):
    """Resident bytes for the compiler process, not a lifetime high-water mark."""
    try:
        result = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)],
                                capture_output=True, text=True, check=True)
        return int(result.stdout.strip()) * 1024
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def run_benchmark(args, directory, actions, histories):
    packets = directory / 'preview-packets.jsonl'
    source, image, log = [directory / name for name in ('main.typ', 'frame.png', 'watch.log')]
    shutil.copyfile(args.engine, directory / 'engine.wasm')
    # The public wrapper now imports the shared engine and keybinding modules.
    core = (ROOT / 'engine/core.typ').read_text().replace('plugin("doom.wasm")', 'plugin("engine.wasm")')
    if args.mode == 'full':
        loop = '\n'.join((
            '  for start in range(0, commands.len(), step: chunk-size) {',
            '    game = advance(game, commands.slice(start, calc.min(start + chunk-size, commands.len())))',
            '  }',
        ))
        if core.count(loop) != 1:
            raise RuntimeError('Cannot locate replay loop in core.typ')
        core = core.replace(loop, '  game = advance(game, commands)')
    (directory / 'core.typ').write_text(core)
    shutil.copyfile(ROOT / 'engine/controls.typ', directory / 'controls.typ')
    shutil.copyfile(args.wad, directory / 'game.wad')
    wrapper = '#import "core.typ" as core\n#let doom = core.doom.with(wad: read("game.wad", encoding: none))\n'
    if args.mode in ('chunked', 'full'):
        wrapper = wrapper.replace('core.doom.with(wad:', 'core.doom.with(cache: false, wad:')
    if args.mode == 'c-cache':
        wrapper += '\n'.join((
            '#let doom(body, help: false, chunk-size: 16) = {',
            '  set page(width: 640pt, height: 480pt, margin: 0pt, fill: black)',
            '  let commands = core.parse-actions(body).split("r").last()',
            '  let game = core.new-game(read("game.wad", encoding: none))',
            '  image(game.cached_frame(bytes(commands)),',
            '    format: (encoding: "rgb8", width: 320, height: 200),',
            '    width: 640pt, height: 480pt, fit: "stretch", scaling: "pixelated")',
            '}',
        )) + '\n'
    (directory / 'wrapper.typ').write_text(wrapper)
    prefix = f'#import "wrapper.typ": doom\n#show: doom.with(help: false, chunk-size: {args.chunk_size})\n\n'
    source.write_text(prefix + actions + '\n')

    def completed_count():
        content = log.read_text() if log.exists() else ''
        if 'error:' in content or 'compilation failed' in content:
            raise RuntimeError(content[-4000:])
        if args.runner == 'tinymist':
            return len(packets.read_text().splitlines()) if packets.exists() else 0
        return content.count('compiled successfully')

    def wait_for_compile(previous, start):
        while time.monotonic() - start < 120:
            if process.poll() is not None or (observer is not None and observer.poll() is not None):
                raise RuntimeError(log.read_text())
            if completed_count() > previous:
                timing = re.findall(r'(?:compiled successfully|compilation succeeded) in ([0-9.]+) ?(ms|s)', log.read_text())
                compile_seconds = (float(timing[-1][0]) / (1000 if timing[-1][1] == 'ms' else 1)) if timing else None
                if args.runner == 'tinymist':
                    packet = json.loads(packets.read_text().splitlines()[-1])
                    return {'seconds': round(time.monotonic() - start, 4),
                            'compile_seconds': compile_seconds, **packet}
                return {
                    'compile_seconds': compile_seconds,
                    'seconds': round(time.monotonic() - start, 4),
                    'sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                }
            time.sleep(.01)
        raise RuntimeError('Watch timed out; file notifications may be blocked.\n' + log.read_text())

    process = observer = None
    packet_stream = None
    try:
        with log.open('w') as stream:
            start = time.monotonic()
            command = ['typst', 'watch', '--root', str(ROOT), str(source), str(image)]
            if args.runner == 'tinymist':
                command = ['tinymist', 'preview', '--no-open', '--verbose',
                           '--data-plane-host', '127.0.0.1:0', '--control-plane-host', '127.0.0.1:0',
                           '--root', str(ROOT), str(source)]
            process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=stream)
            if args.runner == 'tinymist':
                while True:
                    content = log.read_text()
                    match = re.search(r'Data plane server listening on: (127\.0\.0\.1:\d+)', content)
                    if match:
                        packet_stream = packets.open('w')
                        observer = subprocess.Popen(['node', str(ROOT / 'scripts/preview_probe.mjs'),
                                                     'ws://' + match[1]], stdout=packet_stream, stderr=stream)
                        break
                    if process.poll() is not None or time.monotonic() - start > 120:
                        raise RuntimeError('Tinymist preview did not start.\n' + content)
                    time.sleep(.01)
            report = {
                'mode': args.mode,
                'runner': args.runner,
                'latency_endpoint': 'PNG exported' if args.runner == 'typst' else 'preview packet received, excluding client paint',
                'tinymist_version': subprocess.check_output(['tinymist', '--version'], text=True).strip() if args.runner == 'tinymist' else None,
                'edit_pattern': args.edit_pattern,
                'wad_sha256': hashlib.sha256(args.wad.read_bytes()).hexdigest(),
                'typst_version': subprocess.check_output(['typst', '--version'], text=True).strip(),
                'commands': args.commands,
                'chunk_size': args.chunk_size if args.mode == 'chunked' else None,
                'engine_sha256': hashlib.sha256((directory / 'engine.wasm').read_bytes()).hexdigest(),
                'cold': wait_for_compile(0, start),
                'warm': [],
            }
            report['cold']['rss_bytes'] = current_rss(process.pid)
            time.sleep(1)  # Allow the initial file watches to be registered.
            for history in histories:
                previous = completed_count()
                start = time.monotonic()
                source.write_text(prefix + history + '\n')
                sample = wait_for_compile(previous, start)
                sample['rss_bytes'] = current_rss(process.pid)
                report['warm'].append(sample)
                time.sleep(.1)
    finally:
        stop_process(observer)
        if packet_stream is not None:
            packet_stream.close()
        stop_process(process)
    if resource is not None:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        report['peak_rss_bytes'] = usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        report['cpu_seconds'] = round(usage.ru_utime + usage.ru_stime, 4)
    return report


if __name__ == '__main__':
    main()

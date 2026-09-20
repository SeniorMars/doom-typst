"""Exercise concurrent publication and failure cleanup without requiring a SDK."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_engine
from test_wasm_imports import wasm
from wasm_imports import EXPECTED_IMPORTS, validate_plugin


class BuildTests(unittest.TestCase):
    def test_concurrent_builds_and_failure_preserve_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / 'vendor'
            src.mkdir()
            (src / 'Makefile').write_text('SRC_DOOM = doom.o\n')
            native = root / 'engine/native'
            native.mkdir(parents=True)
            (native / 'wasi_stubs.c').write_text('')
            sdk = root / 'sdk'
            (sdk / 'bin').mkdir(parents=True)
            (sdk / 'bin/clang').touch()
            output = root / 'engine/doom.wasm'
            barrier = threading.Barrier(2)
            directories = set()
            lock = threading.Lock()
            valid = wasm(sorted(EXPECTED_IMPORTS))

            def compiler(command, **kwargs):
                destination = Path(command[command.index('-o') + 1])
                mode = b'lto' if '-flto' in command else b'normal'
                if '-c' in command:
                    destination.write_bytes(mode)
                else:
                    with lock:
                        directories.add(destination.parent)
                    barrier.wait(timeout=10)
                    for item in command:
                        if item.endswith('.o'):
                            self.assertEqual(Path(item).read_bytes(), mode)
                    # Valid custom section makes the two candidates distinct.
                    payload = b'\x04mode' + mode
                    destination.write_bytes(valid + b'\x00' + bytes([len(payload)]) + payload)

            with patch.object(build_engine, 'ROOT', root), \
                 patch.object(build_engine, 'SRC', src), \
                 patch.dict('os.environ', {'WASI_SDK_PATH': str(sdk)}), \
                 patch.object(build_engine.subprocess, 'run', side_effect=compiler):
                common = ['--no-wasm-opt', '--no-ccache', '--jobs', '1', '--output', str(output)]
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(build_engine.main, common)
                    second = pool.submit(build_engine.main, common + ['--lto'])
                    first.result(timeout=15)
                    second.result(timeout=15)
                self.assertEqual(len(directories), 2)
                validate_plugin(output)
                before = output.read_bytes()
                self.assertEqual(list((root / 'build').iterdir()), [])
                self.assertEqual(list(output.parent.glob('*.tmp')), [])

                # A failed compiler must neither replace the published engine
                # nor leave partially built objects behind.
                with patch.object(build_engine.subprocess, 'run', side_effect=RuntimeError('compile failed')):
                    with self.assertRaisesRegex(RuntimeError, 'compile failed'):
                        build_engine.main(common)
                self.assertEqual(output.read_bytes(), before)
                self.assertEqual(list((root / 'build').iterdir()), [])

                def invalid_compiler(command, **kwargs):
                    destination = Path(command[command.index('-o') + 1])
                    destination.write_bytes(wasm([('env', 'evil')]))

                with patch.object(build_engine.subprocess, 'run', side_effect=invalid_compiler):
                    with self.assertRaisesRegex(ValueError, 'Unexpected plugin imports'):
                        build_engine.main(common)
                self.assertEqual(output.read_bytes(), before)
                self.assertEqual(list((root / 'build').iterdir()), [])
                self.assertEqual(list(output.parent.glob('*.tmp')), [])

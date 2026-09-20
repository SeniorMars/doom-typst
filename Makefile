TYPST ?= typst

.PHONY: play test engine demo

play:
	mkdir -p build
	$(TYPST) watch main.typ build/doom.pdf

TEST_JOBS ?= 4

.PHONY: test-suite test-imports test-engine test-save test-walkthrough test-frames
.PHONY: test-memory-fs test-tools test-controls test-freedoom test-shareware package test-package

test:
	$(MAKE) --no-print-directory -j$(TEST_JOBS) test-suite

test-suite: test-imports test-memory-fs test-tools test-controls test-freedoom

# Original DOOM fixtures are optional and never shipped with the package.
ifneq ($(wildcard assets/doom1.wad),)
test-suite: test-shareware
endif
test-shareware: test-engine test-save test-walkthrough test-frames

build:
	mkdir -p build

test-imports: | build
	python3 scripts/wasm_imports.py --check engine/doom.wasm

test-tools:
	python3 -m unittest discover -s tests -p 'test_*.py'

test-engine test-save test-walkthrough: test-%: | build
	$(TYPST) compile --root . tests/native-$*.typ build/native-$*-tests.pdf

test-frames: | build
	$(TYPST) compile --root . tests/native-frames.typ 'build/native-frame-{p}.png'

test-memory-fs: | build
	$(CC) -O2 -D__real_fclose=fclose -Iengine/native engine/native/memory_fs.c tests/memory-fs.c -o build/test-memory-fs
	build/test-memory-fs

engine:
	python3 scripts/build_engine.py

demo:
	mkdir -p build/demo
	rm -f build/demo/frame-*.png
	$(TYPST) compile --root . --ppi 72 examples/replay.typ 'build/demo/frame-{0p}.png'
	ffmpeg -y -loglevel error -framerate 10 -i 'build/demo/frame-%03d.png' -c:v libx264 -pix_fmt yuv420p -movflags +faststart build/doom-demo.mp4

# Package commands keep all staging inside the repository's build directory.
package:
	python3 scripts/package.py

test-package: package
	python3 tests/package.py

test-controls: | build
	$(TYPST) compile --root . tests/controls.typ build/controls-tests.pdf

test-freedoom: | build
	$(TYPST) compile --root . tests/freedoom.typ build/freedoom-tests.pdf

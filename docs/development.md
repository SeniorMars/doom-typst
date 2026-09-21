# Development

Run the commands below from the repository root.

## Engine interface

```typst
#import "lib.typ": new-game, advance, info, framebuffer
#let first = new-game(read("assets/freedoom1.wad", encoding: none), tics: 1)
#let second = advance(first, "wwff")
#let state = info(second)
#let pixels = framebuffer(second)
```

`new-game` starts the engine. `advance` applies commands and returns a new game
state, leaving the old one unchanged. `info` returns a dictionary with the
player's position, health, ammo, and other state. `framebuffer` returns RGB bytes.

Both `new-game` and `advance` use `plugin.transition`. Use these functions when
changing engine state so Typst can track and cache the resulting snapshots.
An `advance` call can take up to 4,096 command bytes.

`play` handles a whole input history. It splits the commands into blocks of 16,
which lets Typst reuse earlier blocks when you append input in live preview.
This API is useful for explicit state transitions and save export, but retaining
many plugin snapshots can use substantial memory.

`view(input, ...)` returns `(state: ..., frame: ...)` from a single cached call.
It accepts the same game settings, bindings, and optional save as `play`, up to
65,536 commands. It returns values rather than a game handle.

`game` is the show rule used by the template, and `doom` is an alias for it.
It uses `view` by default. Set `cache: false` to use the transition path for
comparison. Save export uses that path automatically. A fresh compiler process
still replays the history; the C cache speeds up later edits.
The older `engine/doom.typ` import still defaults to a local `assets/doom1.wad`.
The package entry point, `lib.typ`, defaults to Freedoom.

## How it runs

The adapter in `engine/native/` supplies input, a virtual clock, and file access
for the WAD and save slots. DoomGeneric handles the game logic and rendering.
There is no sound, multiplayer, or screen-wipe animation. The game advances when
you type a command.

WAD lumps are read directly from the supplied bytes. This avoids making another
copy of each resource in Doom's heap. The original BSP renderer is still used.
It draws nearer geometry first and skips areas that are already hidden.

Render traversal runs on every tic because the fuzz effect and HUD keep state
between frames. Wall and floor pixel writes are deferred until the last tic of
each command; fuzz, sprites, HUD, and display bookkeeping still run. Only the
frame requested by Typst is converted to RGB. Typst displays
those bytes with its `rgb8` image format.

`engine/native/draw.c` has versions of the column and span loops that keep texture
and lighting pointers in local variables. They keep the original arithmetic and
lookup order. Low-detail, fuzz, and translated drawing use the original code.

Save slots live in memory and are rebuilt from the input history. The menu's
Save option doesn't write a file to your computer. To do that, use the export
commands below.

## Optional save export

Saving the document keeps your input history. If it gets too long, you can export
a native game save and continue with an empty history:

```sh
mkdir -p build
typst eval --input export-save=true --in main.typ 'query(<doom-save>).first().value' > save.json
typst compile --input save=save.json --input actions= main.typ build/loaded.pdf
typst compile --input save=save.json --input actions=wwff main.typ build/continued.pdf
```

Export while you're in a level. The JSON file contains the bytes of a DOOM
`.dsg` save. In the supplied `main.typ`, the save path is relative to that file.
Clear the old commands before continuing, or they will be replayed after loading.

Native saves don't preserve every engine detail, including the random-number
state. Keep the input history if you need an exact replay.

For scripts, use `save-game(game)`, `saved-bytes(game)`, and
`load-game(game, bytes)`.

## Building the engine

The repository includes `engine/doom.wasm`, so you only need a C toolchain if
you're changing the engine. Install the WASI SDK, then run:

```sh
WASI_SDK_PATH=/path/to/wasi-sdk python3 scripts/build_engine.py
```

The script also looks for the SDK at `build/wasi-sdk-34.0-arm64-macos`. It builds
DoomGeneric with the adapter and checks that the WASM imports only Typst's two
plugin protocol functions.

If `ccache` is installed, the build uses it and stores its cache in `build/ccache`.
Use `--no-ccache` to turn it off. `--jobs N` sets the number of compiler workers;
the default is the CPU count.

The build runs `wasm-opt -O3` when Binaryen is available. It checks `--wasm-opt
PATH`, `WASM_OPT`, `PATH`, and then `build/binaryen-version_131/bin/wasm-opt`.
Binaryen 131 was used for testing. Use `--no-wasm-opt` to skip it.

Other build options:

| Flag | What it does |
| --- | --- |
| `--output PATH` | Writes a separate WASM file for testing |
| `--lto` | Enables link-time optimization |
| `--gc-sections` | Enables section-based dead-code removal |
| `--initial-memory BYTES` | Sets initial memory; `0` lets the linker choose |

LTO and section GC are off by default. With LTO, the build uses the SDK's ordinary
libc archive because SDK 34's LTO libc adds a `random_get` import that the plugin
can't use.

Memory grows as needed, up to 128 MiB. Doom's zone allocator gets 16 MiB.
Each build has its own temporary directory. The output file is replaced only
after linking, optimization, and import checks succeed. If two builds use the
same output path, the last successful build wins.

The vendored DoomGeneric revision is
`dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284`. Its Makefile supplies the source list;
the adapter replaces the Xlib host. The build has a known upstream warning about
`abs` on an unsigned value in `r_segs.c`.

## Tests

```sh
make test
make test-package
```

These need Typst, Python, and a native C compiler. `make test` runs checks in
parallel; use `make test TEST_JOBS=1` to run them one at a time.

The default tests cover all 36 Freedoom level starts, movement, firing, menus,
keybindings, save/load, and replay across different chunk sizes. They also check
the memory filesystem, build script, and WASM imports.

If `assets/doom1.wad` is present, `make test` also runs the original DOOM tests.
These include a 2,314-command E1M1 playthrough that reaches the exit with 63 health
and two kills, then continues into E1M2. The WAD is not included in the repository.
Neither test set covers a full campaign.

`make test-package` builds the package, creates a project with `typst init`, and
tests gameplay, custom controls, CLI input, and save files. It also compiles the
web zip after extracting it into a separate directory.

To compare an engine change with the previous build, keep a copy before rebuilding:

```sh
mkdir -p build
cp engine/doom.wasm build/previous.wasm
# Make your changes and rebuild, then:
typst compile --root . --input reference=/build/previous.wasm tests/native-equivalence.typ build/equivalence.pdf
```

This comparison needs the local shareware `assets/doom1.wad`. It checks game state
and every pixel at 237 points across nine maps and the E1M1-to-E1M2 replay.
Add `--input candidate=/build/candidate.wasm` to test a separate build without
replacing `engine/doom.wasm`. The leading `/` means the Typst project root.

## Benchmarks

```sh
python3 scripts/benchmark.py --mode package --output build/benchmarks/run.json
python3 scripts/benchmark.py --mode package --runner tinymist --commands 1000 --edits 1000 --edit-pattern session --output build/benchmarks/session.json
```

The default workload starts with 700 commands and appends eight more. Reports
include compile times, image hashes, CPU time, peak memory, and current compiler
RSS when `ps` is available. Tinymist needs Node with built-in `WebSocket`; its
latency ends at receipt of a preview packet, before browser painting.

Use `--commands`, `--edits`, `--engine`, and `--wad` to change the workload.
The edit patterns are `append`, `tail`, `mixed`, `rewind`, and `session`. The
session pattern includes firing, menus, deletion, middle edits, and restart.

`--mode package` measures the normal show rule. For comparisons, `chunked` uses
the transition API, `full` replays the history in one C call, and `c-cache`
measures the frame-only cache. Full replay accepts at most 4,096 commands per
call; cached play accepts 65,536. All modes work in a temporary directory.

On September 20, 2026, with Freedoom, Typst 0.15.1, and four tics per command:

| Workload | First frame | Median edit | Peak process RSS |
| --- | ---: | ---: | ---: |
| CLI, 1,000 commands and 32 appends | 2.45 s | 188 ms | 328 MiB |
| CLI, 4,000 commands and eight appends | 9.64 s | 194 ms | 310 MiB |
| Tinymist, 1,000 starting commands and 1,000 varied edits | 2.92 s | 41 ms | 300 MiB |

All 42 CLI frames matched the previous renderer. Cold replay at 4,000 commands
previously took 16.3 seconds. The integrated metadata/pixel path is slightly
slower on warm CLI edits than the earlier frame-only prototype.

Both 1,000-edit sessions completed. The CLI cache-integration run peaked at
267 MiB current RSS and ended at 195 MiB. The final Tinymist build peaked at
300 MiB and ended at 252 MiB. Neither showed sustained memory growth in this
workload. Five CLI session frames, including branches and restart, also matched
independent full replay. These are single-machine runs, not a memory bound for
every WAD or a repeated latency study. Local reports are in `build/benchmarks/`.

## Replay cache

The C cache keeps the last input history, an initial snapshot, one recent full
checkpoint, and up to 4 MiB of reverse deltas. Appending runs only new commands.
Deleting or replacing input restores a retained checkpoint and replays from
there. Older edits fall back to the initial snapshot. The immutable WAD is
excluded from both full snapshots.

Checkpoints use 16-command boundaries. Reverse deltas store the old bytes of
changed 1 KiB blocks, with at most 64 entries. Old patches are dropped when the
buffer fills. A patch too large for the budget discards the rewind chain; replay
still works. If the heap grows, the cache retains its older complete checkpoint.

```sh
make test-replay-cache
make test-replay-cache REPLAY_DELTA_BYTES=64
make test-replay-cache REPLAY_DELTA_BYTES=0
```

These compare cached frames with normal replay, including deletion, branching,
checkpoint boundaries, and multiple game configurations. The smaller budgets
exercise fallback when a patch does not fit.

The cache depends on wasm-ld's C data and heap layout. The package uses a
dedicated initializer and returns metadata and pixels together through
`cached_view`. A save is loaded before taking the baseline; restart ignores it.
Public transition-based handles stay separate. Do not mix low-level cached
exports with advance, info, frame, or save/load on the same module.

Typst can discard an instance, in which case the next call replays from the
start. The cache is bounded per instance, not across the compiler. Save export
uses larger replay blocks to avoid retaining a snapshot every 16 commands.

## Rendering checks

```sh
make test-render-effects
```

This compares the default deferred pixel writes with a build that draws every
tic. It covers invulnerability, invisibility, menus, and the automap. The engine
equivalence test also covers the nine shareware maps and the E1M1 exit trace.

For profiling, `--render-mode all` draws every tic. `--render-mode none` omits
intermediate display work and requires a separate output path. It fails the
powerup/automap comparison and must not be used for play.

At 1,000 commands, full replay took about 4.0 seconds with every pixel drawn,
2.4 seconds with deferred pixel writes, and 0.16 seconds with intermediate
display work omitted. This is a coarse timing comparison, not a sampled profile.
The initial frame tests missed the powerup regression; the effect tests caught it.

## Cleaning up

```sh
make clean
```

Removes generated test files, trial engines, and temporary projects. Toolchains,
benchmark reports, staged packages, downloaded archives, and history backups stay
in `build/`. The runtime at `engine/doom.wasm` is kept too.

## Game options

| Option | Default | What it does |
| --- | --- | --- |
| `wad` | Freedoom Phase 1 | Use another IWAD's bytes; `none` shows setup instructions |
| `skill` | `3` | Difficulty, `1`–`5` |
| `episode` | `1` | Episode, `1`–`4` |
| `map` | `1` | Map number; it must exist in the IWAD |
| `tics` | `4` | Game tics per command, `1`–`35` |
| `actions` | `(:)` | Change selected keybindings |
| `help` | `true` | Show controls below the game |
| `cache` | `true` | Use the bounded C cache for document play |
| `chunk-size` | `16` | Commands per transition when `cache: false` |
| `save` | `none` | Native DOOM save bytes to load before the commands |

To use your own DOOM II IWAD, pass `wad: read("doom2.wad", encoding: none)`.
The adapter recognizes its map format, but a full DOOM II playthrough hasn't
been tested here.

Available action names:

```text
forward, backward, strafe-left, strafe-right
run-forward, run-backward, run-left, run-right
turn-left, turn-right, fire, use, forward-fire, backward-fire
weapon-1, weapon-2, weapon-3, weapon-4, weapon-5, weapon-6, weapon-7
automap, wait, restart, menu
menu-up, menu-down, menu-left, menu-right, confirm, back, yes, no
```

Import `default-actions` to see the default keys. If a key is also Typst markup,
put the commands in a raw text block. Clear the old commands when changing
bindings, since they'll be read using the new controls.

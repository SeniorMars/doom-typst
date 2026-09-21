// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef TYPST_REPLAY_CACHE_H
#define TYPST_REPLAY_CACHE_H
#include <stddef.h>

#define REPLAY_MAX_COMMANDS 65536

typedef void (*replay_advance_fn)(const unsigned char *actions, size_t length);

// Advance an already initialized engine to the end of a complete input history.
// One cache belongs to one engine/WAD for the lifetime of the WASM instance.
// The WAD is borrowed and must remain immutable. Actions must be on the stack:
// restoring a checkpoint overwrites the engine's data and heap.
// Returns 1 on success, 0 if the arguments or snapshot layout are unsupported.
// Do not interleave this with other mutations of the same engine.
int replay_cached_advance(const unsigned char *actions, size_t length, const unsigned char *wad,
                          size_t wad_size, replay_advance_fn advance);

#endif

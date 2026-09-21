// SPDX-License-Identifier: GPL-2.0-or-later
// Bounded replay cache for a dedicated initialized WASM instance.
// A cache belongs to one initialized module (one IWAD/configuration). Only call
// cached_frame on this module: mixing it with the stateful API is unsupported.
// The baseline covers C data and heap, including allocator and virtual files.
// It excludes immutable WAD bytes, the live stack, and cache storage. This relies
// on wasm-ld memory layout; it is not a general WASM save-state format.
#include "replay_cache.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef REPLAY_CACHE
#ifndef REPLAY_DELTA_BYTES
#define REPLAY_DELTA_BYTES (4 * 1024 * 1024)
#endif
#define REPLAY_DELTA_COUNT 64
#define REPLAY_DELTA_BLOCK 1024
#define REPLAY_CHECKPOINT_INTERVAL 16

typedef enum {
    SNAPSHOT_CAPTURE,
    SNAPSHOT_RESTORE,
    SNAPSHOT_MEASURE_DELTA,
    SNAPSHOT_WRITE_DELTA
} snapshot_operation;
typedef struct {
    size_t offset, size, previous_length;
} replay_delta;
extern unsigned char __global_base, __data_end, __heap_base;
typedef struct {
    const unsigned char *wad;
    size_t wad_size;
    unsigned char *snapshot;
    size_t data_start, data_end, heap_start, buffer_start, buffer_end, memory_end;
    size_t length, checkpoint_length;
    unsigned char *checkpoint, *deltas;
    size_t delta_count, delta_used;
    replay_delta delta[REPLAY_DELTA_COUNT];
    unsigned char history[REPLAY_MAX_COMMANDS];
} replay_cache;
static replay_cache replay;

// Scan once to size a reverse patch, then write only changed blocks. Each
// record stores an offset into the packed snapshot followed by the old bytes.
static int same_block(const unsigned char *a, const unsigned char *b, size_t n) {
    size_t i = 0;
    for (; i + 8 <= n; i += 8) {
        uint64_t x, y;
        memcpy(&x, a + i, 8);
        memcpy(&y, b + i, 8);
        if (x != y)
            return 0;
    }
    return !memcmp(a + i, b + i, n - i);
}
static size_t delta_region(replay_cache *c, unsigned char *old, const unsigned char *now,
                           size_t size, size_t used, int write) {
    size_t needed = 0;
    for (size_t at = 0; at < size; at += REPLAY_DELTA_BLOCK) {
        size_t n = size - at < REPLAY_DELTA_BLOCK ? size - at : REPLAY_DELTA_BLOCK;
        if (same_block(old + at, now + at, n))
            continue;
        if (write) {
            uint32_t offset = (uint32_t)(old + at - c->checkpoint), length = n;
            unsigned char *out = c->deltas + c->delta_used + used + needed;
            memcpy(out, &offset, 4);
            memcpy(out + 4, &length, 4);
            memcpy(out + 8, old + at, n);
        }
        needed += 8 + n;
    }
    return needed;
}

static size_t snapshot_walk(replay_cache *c, unsigned char *storage, snapshot_operation operation) {
    size_t starts[] = {c->data_start, c->heap_start, c->buffer_end};
    size_t ends[] = {c->data_end, c->buffer_start, c->memory_end};
    size_t skip_start[] = {(uintptr_t)c->wad, (uintptr_t)&replay};
    size_t skip_end[] = {skip_start[0] + c->wad_size, skip_start[1] + sizeof(replay)};
    unsigned char *cursor = storage;
    size_t delta_size = 0;
    for (int i = 0; i < 3; ++i) {
        size_t at = starts[i];
        while (at < ends[i]) {
            size_t end = ends[i], next = at;
            for (size_t j = 0; j < sizeof(skip_start) / sizeof(skip_start[0]); ++j) {
                if (at >= skip_start[j] && at < skip_end[j])
                    next = skip_end[j];
                else if (at < skip_start[j] && skip_start[j] < end)
                    end = skip_start[j];
            }
            if (next != at) {
                at = next < ends[i] ? next : ends[i];
                continue;
            }
            size_t size = end - at;
            unsigned char *memory = (unsigned char *)(uintptr_t)at;
            if (operation == SNAPSHOT_RESTORE)
                memcpy(memory, cursor, size);
            else if (operation == SNAPSHOT_CAPTURE)
                memcpy(cursor, memory, size);
            else
                delta_size += delta_region(c, cursor, memory, size, delta_size,
                                           operation == SNAPSHOT_WRITE_DELTA);
            cursor += size;
            at = end;
        }
    }
    return delta_size;
}

static int baseline_init(const unsigned char *wad, size_t wad_size) {
    size_t memory_size = __builtin_wasm_memory_size(0) * 65536u;
    const size_t allocator_slack = 1048576u;
    if (wad_size > memory_size || memory_size - wad_size > SIZE_MAX - allocator_slack)
        return 0;
    size_t snapshot_size = memory_size - wad_size + allocator_slack;
    if (snapshot_size > (SIZE_MAX - REPLAY_DELTA_BYTES) / 2)
        return 0;
    size_t capacity = snapshot_size * 2 + REPLAY_DELTA_BYTES;
    unsigned char *snapshot = malloc(capacity);
    if (!snapshot)
        return 0;
    replay.wad = wad;
    replay.wad_size = wad_size;
    replay.snapshot = snapshot;
    replay.checkpoint = snapshot + snapshot_size;
    replay.deltas = snapshot + snapshot_size * 2;
    replay.data_start = (uintptr_t)&__global_base;
    replay.data_end = (uintptr_t)&__data_end;
    replay.heap_start = (uintptr_t)&__heap_base;
    replay.buffer_start = (uintptr_t)snapshot;
    replay.buffer_end = replay.buffer_start + capacity;
    replay.memory_end = __builtin_wasm_memory_size(0) * 65536u;
    size_t stack_address = (uintptr_t)&capacity;
    if ((stack_address >= replay.data_start && stack_address < replay.data_end) ||
        (stack_address >= replay.heap_start && stack_address < replay.memory_end) ||
        replay.data_end < replay.data_start || replay.data_end > replay.heap_start ||
        (uintptr_t)wad < replay.heap_start || (uintptr_t)wad + wad_size > replay.buffer_start ||
        replay.heap_start > replay.buffer_start || replay.buffer_end > replay.memory_end ||
        replay.data_end - replay.data_start + replay.memory_end - replay.heap_start - capacity -
                wad_size >
            snapshot_size) {
        free(snapshot);
        memset(&replay, 0, sizeof(replay));
        return 0;
    }
    snapshot_walk(&replay, replay.snapshot, SNAPSHOT_CAPTURE);
    return 1;
}

static void checkpoint_capture(void) {
    size_t previous = replay.checkpoint_length;
    if (previous && (REPLAY_DELTA_BYTES > 0)) {
        size_t needed = snapshot_walk(&replay, replay.checkpoint, SNAPSHOT_MEASURE_DELTA);
        if (needed <= REPLAY_DELTA_BYTES) {
            while (replay.delta_count && (replay.delta_count == REPLAY_DELTA_COUNT ||
                                          replay.delta_used + needed > REPLAY_DELTA_BYTES)) {
                size_t drop = replay.delta[0].size;
                memmove(replay.deltas, replay.deltas + drop, replay.delta_used - drop);
                replay.delta_used -= drop;
                --replay.delta_count;
                memmove(replay.delta, replay.delta + 1, replay.delta_count * sizeof(replay_delta));
                for (size_t i = 0; i < replay.delta_count; ++i)
                    replay.delta[i].offset -= drop;
            }
            snapshot_walk(&replay, replay.checkpoint, SNAPSHOT_WRITE_DELTA);
            replay.delta[replay.delta_count++] =
                (replay_delta){replay.delta_used, needed, previous};
            replay.delta_used += needed;
        } else {
            // The budget cannot hold this transition. Break the chain safely.
            replay.delta_count = replay.delta_used = 0;
        }
    }
    replay.checkpoint_length = replay.length;
    snapshot_walk(&replay, replay.checkpoint, SNAPSHOT_CAPTURE);
}

static int checkpoint_rewind(size_t common) {
    while (replay.checkpoint_length > common && replay.delta_count) {
        replay_delta *d = &replay.delta[--replay.delta_count];
        size_t at = d->offset, end = at + d->size;
        while (at < end) {
            uint32_t offset, size;
            memcpy(&offset, replay.deltas + at, 4);
            memcpy(&size, replay.deltas + at + 4, 4);
            memcpy(replay.checkpoint + offset, replay.deltas + at + 8, size);
            at += 8 + size;
        }
        replay.delta_used = d->offset;
        replay.checkpoint_length = d->previous_length;
    }
    return replay.checkpoint_length && replay.checkpoint_length <= common;
}

int replay_cached_advance(const unsigned char *actions, size_t len, const unsigned char *wad,
                          size_t wad_size, replay_advance_fn advance) {
    if (len > REPLAY_MAX_COMMANDS || !advance)
        return 0;
    if (replay.snapshot && (replay.wad != wad || replay.wad_size != wad_size))
        return 0;
    if (!replay.snapshot && !baseline_init(wad, wad_size))
        return 0;
    if (len < replay.length || memcmp(actions, replay.history, replay.length)) {
        size_t common = 0;
        while (common < len && common < replay.length && actions[common] == replay.history[common])
            ++common;
        int use_checkpoint = checkpoint_rewind(common);
        // Cache metadata is excluded from both snapshots.
        snapshot_walk(&replay, use_checkpoint ? replay.checkpoint : replay.snapshot,
                      SNAPSHOT_RESTORE);
        replay.length = use_checkpoint ? replay.checkpoint_length : 0;
        if (!use_checkpoint)
            replay.checkpoint_length = replay.delta_count = replay.delta_used = 0;
    }
    // Keep just one recent 16-command boundary, not every historical state.
    // On cold replay, create only the final useful checkpoint.
    size_t boundary =
        len ? ((len - 1) / REPLAY_CHECKPOINT_INTERVAL) * REPLAY_CHECKPOINT_INTERVAL : 0;
    if (boundary > replay.length) {
        advance(actions + replay.length, boundary - replay.length);
        replay.length = boundary;
        // A checkpoint must cover the entire heap used at capture time. If
        // memory grew, retain the older complete checkpoint instead of taking
        // a partial one. The baseline remains valid for a full replay.
        if (__builtin_wasm_memory_size(0) * 65536u == replay.memory_end) {
            checkpoint_capture();
        }
    }
    advance(actions + replay.length, len - replay.length);
    memcpy(replay.history, actions, len);
    replay.length = len;
    return 1;
}

#endif

// Exercise stream reopening after buffers have been trimmed, including saves
// larger than 128 KiB. Compile with -D__real_fclose=fclose for the native host.
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include "memory_fs.h"
extern int __wrap_fclose(FILE *);
extern int __wrap_rename(const char *, const char *);
extern int __wrap_remove(const char *);

int main(void) {
    assert(__wrap_rename("missing", "missing") == -1 && errno == ENOENT);
    unsigned char *data = malloc(MEMORY_FILE_CAPACITY);
    assert(data);
    for (size_t i = 0; i < MEMORY_FILE_CAPACITY; ++i) data[i] = i % 251;
    for (int slot = 0; slot < 6; ++slot) {
        char path[16];
        snprintf(path, sizeof(path), "save%d", slot);
        FILE *f = memory_open(path, "wb");
        assert(f && fwrite(data, 1, 3, f) == 3);
        assert(__wrap_fclose(f) == 0);
        // Growing a previously trimmed slot must not truncate the new save.
        f = memory_open(path, "wb");
        assert(f && fwrite(data, 1, 200000, f) == 200000);
        assert(__wrap_fclose(f) == 0);
        size_t size = 0;
        const unsigned char *saved = memory_read(path, &size);
        assert(saved && size == 200000 && memcmp(saved, data, size) == 0);
        f = memory_open(path, "ab");
        assert(f && fwrite(data, 1, 2, f) == 2);
        assert(__wrap_fclose(f) == 0);
        saved = memory_read(path, &size);
        assert(size == 200002 && memcmp(saved + 200000, data, 2) == 0);
        f = memory_open(path, "rb");
        assert(f && fgetc(f) == data[0]);
        assert(__wrap_fclose(f) == 0);
    }
    assert(memory_write("import", data, MEMORY_FILE_CAPACITY - 1) == 0);
    assert(memory_write("import", data, MEMORY_FILE_CAPACITY) == -1 && errno == EFBIG);
    assert(__wrap_rename("import", "save0") == 0);
    size_t size;
    const unsigned char *saved = memory_read("save0", &size);
    assert(saved && size == MEMORY_FILE_CAPACITY - 1 && memcmp(saved, data, size) == 0);
    assert(__wrap_remove("save0") == 0);
    assert(memory_read("save0", &size) == NULL);

    // Active readers keep their backing buffer stable, including across a
    // failed writer/open, replacement, removal, or rename.
    assert(memory_write("shared", data, 200000) == 0);
    assert(memory_write("other", data, 3) == 0);
    FILE *first = memory_open("shared", "rb");
    FILE *second = memory_open("shared", "rb");
    assert(first && second);
    assert(memory_open("shared", "wb") == NULL && errno == EBUSY);
    assert(memory_open("shared", "ab") == NULL && errno == EBUSY);
    assert(memory_write("shared", data, 1) == -1 && errno == EBUSY);
    assert(__wrap_remove("shared") == -1 && errno == EBUSY);
    assert(__wrap_rename("shared", "other") == -1 && errno == EBUSY);
    assert(__wrap_rename("other", "shared") == -1 && errno == EBUSY);
    unsigned char *readback = malloc(200000);
    assert(readback && fread(readback, 1, 200000, first) == 200000);
    assert(memcmp(readback, data, 200000) == 0);
    assert(__wrap_fclose(first) == 0);
    assert(memory_open("shared", "wb") == NULL && errno == EBUSY);
    assert(fread(readback, 1, 200000, second) == 200000);
    assert(memcmp(readback, data, 200000) == 0);
    assert(__wrap_fclose(second) == 0);

    // A writer excludes all other access until its buffer is flushed/trimmed.
    first = memory_open("shared", "wb");
    assert(first && fwrite(data, 1, 3, first) == 3);
    assert(memory_open("shared", "rb") == NULL && errno == EBUSY);
    assert(memory_open("shared", "ab") == NULL && errno == EBUSY);
    assert(memory_read("shared", &size) == NULL && errno == EBUSY);
    assert(memory_write("shared", data, 1) == -1 && errno == EBUSY);
    assert(__wrap_remove("shared") == -1 && errno == EBUSY);
    assert(__wrap_rename("other", "shared") == -1 && errno == EBUSY);
    assert(__wrap_fclose(first) == 0);
    saved = memory_read("shared", &size);
    assert(saved && size == 3 && memcmp(saved, data, 3) == 0);
    assert(__wrap_rename("other", "shared") == 0);
    assert(__wrap_remove("shared") == 0);
    free(readback);
    free(data);
    return 0;
}

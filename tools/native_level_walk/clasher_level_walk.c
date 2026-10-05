/*
 * clasher-level-walk: one on-device process per frame for Clasher's native
 * public level read (scripts/read_native_public_levels.py, reader "batched").
 *
 * It performs the same bounded range reads, in the same order, as the host
 * reader's legacy per-range `dd if=/proc/PID/mem` walk and writes a framed
 * transcript of every (address, size, bytes) it read. It interprets nothing
 * beyond what is needed to choose the next address; the host replays its own
 * unchanged walk against the transcript and re-validates every pointer hop,
 * identity, component inventory, backlink and level bound. Nothing is cached:
 * each invocation opens /proc/PID/mem, reads, and exits.
 *
 * Usage: clasher-level-walk PID MANAGER_ADDRESS_DECIMAL [BODY_ID ...]
 * BODY_ID values are the nativeObjectIds whose ordinary-observation "hp" is
 * non-null (the host reader's body set).
 *
 * Output (little-endian):
 *   "CLWALK01"                                  8 bytes
 *   u32 pid, u32 body_id_count
 *   u32 stat_before_length, stat bytes          /proc/PID/stat before reading
 *   repeated: u8 1, u64 address, u32 size, u32 got, got bytes
 *   u8 2, u32 record_count, u32 stop_reason
 *   u32 stat_after_length, stat bytes           /proc/PID/stat after reading
 *   "CLWEND01"                                  8 bytes
 *
 * Stop reasons: 0 complete, 1 short read, 2 invalid bounded request,
 * 3 invalid object vector, 4 missing body component inventory,
 * 5 HP component backlink mismatch.
 *
 * Build (Android arm64, static):
 *   $NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android24-clang \
 *     -std=c11 -O2 -Wall -Wextra -static -s -o clasher-level-walk clasher_level_walk.c
 * Host test build adds -DCLASHER_WALK_TEST, which reads memory and stat from
 * the files named by CLASHER_WALK_MEM_FILE / CLASHER_WALK_STAT_FILE instead.
 */
#define _FILE_OFFSET_BITS 64
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_BODIES 128
#define MAX_OBJECTS 128
#define MAX_OUTPUT (512 * 1024)
#define ADDRESS_LIMIT (UINT64_C(1) << 56)
#ifdef CLASHER_WALK_TEST
#define PATH_BUFFER 1024 /* host test file paths */
#else
#define PATH_BUFFER 64 /* /proc/PID/{mem,stat} */
#endif

static unsigned char output[MAX_OUTPUT];
static size_t output_used;
static uint32_t record_count;
static int memory_fd = -1;

static void fail(const char *message) {
  fprintf(stderr, "clasher-level-walk: %s\n", message);
  exit(2);
}

static void emit(const void *data, size_t size) {
  if (size > MAX_OUTPUT - output_used) {
    fail("output bound exceeded");
  }
  memcpy(output + output_used, data, size);
  output_used += size;
}

static void emit_u8(uint8_t value) { emit(&value, 1); }
static void emit_u32(uint32_t value) {
  unsigned char bytes[4] = {(unsigned char)value, (unsigned char)(value >> 8), (unsigned char)(value >> 16),
                            (unsigned char)(value >> 24)};
  emit(bytes, 4);
}
static void emit_u64(uint64_t value) {
  emit_u32((uint32_t)value);
  emit_u32((uint32_t)(value >> 32));
}

static uint64_t load_u64(const unsigned char *bytes) {
  uint64_t value = 0;
  for (int index = 7; index >= 0; --index) {
    value = (value << 8) | bytes[index];
  }
  return value;
}
static uint32_t load_u32(const unsigned char *bytes) {
  return (uint32_t)bytes[0] | (uint32_t)bytes[1] << 8 | (uint32_t)bytes[2] << 16 | (uint32_t)bytes[3] << 24;
}

static void emit_stat(const char *path) {
  unsigned char stat[4096];
  size_t used = 0;
  const int fd = open(path, O_RDONLY | O_CLOEXEC);
  if (fd >= 0) {
    for (;;) {
      const ssize_t got = read(fd, stat + used, sizeof(stat) - used);
      if (got <= 0) {
        break;
      }
      used += (size_t)got;
      if (used == sizeof(stat)) {
        break;
      }
    }
    close(fd);
  }
  emit_u32((uint32_t)used);
  emit(stat, used);
}

/* One bounded pread; returns bytes read. The transcript records the request
 * and exactly the bytes obtained; no retry or splice happens here. */
static uint32_t read_range(uint64_t address, uint32_t size, unsigned char *destination) {
  uint32_t got = 0;
  while (got < size) {
    const ssize_t count = pread(memory_fd, destination + got, size - got, (off_t)(address + got));
    if (count < 0 && errno == EINTR) {
      continue;
    }
    if (count <= 0) {
      break;
    }
    got += (uint32_t)count;
  }
  emit_u8(1);
  emit_u64(address);
  emit_u32(size);
  emit_u32(got);
  emit(destination, got);
  ++record_count;
  return got;
}

/* Mirrors the host's single-read bound: 0 < address < 2^56, 0 < size <= 4096. */
static int single_valid(uint64_t address, uint32_t size) {
  return address > 0 && address < ADDRESS_LIMIT && size > 0 && size <= 4096;
}
/* Mirrors the host's batch bound, which also requires address + size <= 2^56. */
static int batch_valid(uint64_t address, uint32_t size) {
  return single_valid(address, size) && address + size <= ADDRESS_LIMIT;
}

static int finish(int reason, const char *stat_path) {
  emit_u8(2);
  emit_u32(record_count);
  emit_u32((uint32_t)reason);
  emit_stat(stat_path);
  emit("CLWEND01", 8);
  size_t written = 0;
  while (written < output_used) {
    const ssize_t count = write(STDOUT_FILENO, output + written, output_used - written);
    if (count < 0 && errno == EINTR) {
      continue;
    }
    if (count <= 0) {
      return 3;
    }
    written += (size_t)count;
  }
  return 0;
}

static int parse_u64(const char *text, uint64_t *value) {
  if (text == NULL || *text < '0' || *text > '9' || strlen(text) > 20) {
    return 0;
  }
  char *end = NULL;
  errno = 0;
  const unsigned long long parsed = strtoull(text, &end, 10);
  if (errno != 0 || end == NULL || *end != '\0') {
    return 0;
  }
  *value = (uint64_t)parsed;
  return 1;
}

int main(int argc, char **argv) {
  if (argc < 3 || argc - 3 > MAX_BODIES) {
    fail("usage: clasher-level-walk PID MANAGER_ADDRESS_DECIMAL [BODY_ID ...]");
  }
  uint64_t pid = 0, manager = 0;
  if (!parse_u64(argv[1], &pid) || pid == 0 || pid > UINT32_MAX || !parse_u64(argv[2], &manager)) {
    fail("invalid pid or manager address");
  }
  uint32_t body_ids[MAX_BODIES];
  const int body_count = argc - 3;
  for (int index = 0; index < body_count; ++index) {
    uint64_t value = 0;
    if (!parse_u64(argv[3 + index], &value) || value == 0 || value > UINT32_MAX) {
      fail("invalid body identity");
    }
    body_ids[index] = (uint32_t)value;
  }

  char memory_path[PATH_BUFFER], stat_path[PATH_BUFFER];
#ifdef CLASHER_WALK_TEST
  const char *test_memory = getenv("CLASHER_WALK_MEM_FILE");
  const char *test_stat = getenv("CLASHER_WALK_STAT_FILE");
  if (test_memory == NULL || test_stat == NULL || strlen(test_memory) >= sizeof(memory_path) ||
      strlen(test_stat) >= sizeof(stat_path)) {
    fail("test build requires CLASHER_WALK_MEM_FILE and CLASHER_WALK_STAT_FILE");
  }
  snprintf(memory_path, sizeof(memory_path), "%s", test_memory);
  snprintf(stat_path, sizeof(stat_path), "%s", test_stat);
#else
  snprintf(memory_path, sizeof(memory_path), "/proc/%llu/mem", (unsigned long long)pid);
  snprintf(stat_path, sizeof(stat_path), "/proc/%llu/stat", (unsigned long long)pid);
#endif

  emit("CLWALK01", 8);
  emit_u32((uint32_t)pid);
  emit_u32((uint32_t)body_count);
  emit_stat(stat_path);
  memory_fd = open(memory_path, O_RDONLY | O_CLOEXEC);
  if (memory_fd < 0) {
    return finish(1, stat_path) == 0 ? 0 : 3;
  }

  unsigned char word[8];
  /* Pointer hops: manager+0xa8 -> world, +0xe0 -> king, +0x10 -> object
   * manager, +0x08 -> vector; then capacity/count at object manager+0x10. */
  uint64_t address = manager + 0xa8;
  const uint64_t hop_offsets[3] = {0xe0, 0x10, 0x08};
  uint64_t pointer = 0;
  for (int hop = 0; hop < 4; ++hop) {
    if (!single_valid(address, 8)) {
      return finish(2, stat_path);
    }
    if (read_range(address, 8, word) != 8) {
      return finish(1, stat_path);
    }
    pointer = load_u64(word);
    if (hop < 3) {
      address = pointer + hop_offsets[hop];
    }
  }
  /* After four hops: `address` is object_manager + 8, `pointer` is vector. */
  const uint64_t object_manager = address - 0x08;
  const uint64_t vector = pointer;
  if (!single_valid(object_manager + 0x10, 8)) {
    return finish(2, stat_path);
  }
  if (read_range(object_manager + 0x10, 8, word) != 8) {
    return finish(1, stat_path);
  }
  const int32_t capacity = (int32_t)load_u32(word);
  const int32_t count = (int32_t)load_u32(word + 4);
  const int32_t bound = capacity < MAX_OBJECTS ? capacity : MAX_OBJECTS;
  if (!(count > 0 && count <= bound)) {
    return finish(3, stat_path);
  }
  unsigned char pointer_bytes[MAX_OBJECTS * 8];
  if (!single_valid(vector, (uint32_t)count * 8)) {
    return finish(2, stat_path);
  }
  if (read_range(vector, (uint32_t)count * 8, pointer_bytes) != (uint32_t)count * 8) {
    return finish(1, stat_path);
  }
  uint64_t objects[MAX_OBJECTS];
  for (int32_t index = 0; index < count; ++index) {
    objects[index] = load_u64(pointer_bytes + 8 * index);
    if (!batch_valid(objects[index], 0xb0)) {
      return finish(2, stat_path);
    }
  }
  /* Object headers (0xb0 bytes each), in vector order. */
  static unsigned char headers[MAX_OBJECTS][0xb0];
  for (int32_t index = 0; index < count; ++index) {
    if (read_range(objects[index], 0xb0, headers[index]) != 0xb0) {
      return finish(1, stat_path);
    }
  }
  uint64_t body_address[MAX_OBJECTS], body_components[MAX_OBJECTS];
  int bodies = 0;
  for (int32_t index = 0; index < count; ++index) {
    const uint32_t identity = load_u32(headers[index] + 8);
    int is_body = 0;
    for (int body = 0; body < body_count; ++body) {
      is_body |= body_ids[body] == identity;
    }
    if (!is_body) {
      continue;
    }
    const int32_t component_count = (int32_t)load_u32(headers[index] + 0x20);
    if (component_count < 3 || component_count > 64) {
      return finish(4, stat_path);
    }
    body_address[bodies] = objects[index];
    body_components[bodies] = load_u64(headers[index] + 0x18);
    ++bodies;
  }
  /* HP component pointers (components[2]), then their owner backlinks. */
  uint64_t hp_components[MAX_OBJECTS];
  for (int body = 0; body < bodies; ++body) {
    if (!batch_valid(body_components[body] + 16, 8)) {
      return finish(2, stat_path);
    }
  }
  for (int body = 0; body < bodies; ++body) {
    if (read_range(body_components[body] + 16, 8, word) != 8) {
      return finish(1, stat_path);
    }
    hp_components[body] = load_u64(word);
  }
  for (int body = 0; body < bodies; ++body) {
    if (!batch_valid(hp_components[body] + 8, 8)) {
      return finish(2, stat_path);
    }
  }
  int backlinks_valid = 1;
  for (int body = 0; body < bodies; ++body) {
    if (read_range(hp_components[body] + 8, 8, word) != 8) {
      return finish(1, stat_path);
    }
    backlinks_valid &= load_u64(word) == body_address[body];
  }
  if (!backlinks_valid) {
    return finish(5, stat_path);
  }
  /* Level words only after every body layout/backlink validated. */
  for (int body = 0; body < bodies; ++body) {
    if (!batch_valid(body_address[body] + 0x120, 4)) {
      return finish(2, stat_path);
    }
  }
  for (int body = 0; body < bodies; ++body) {
    if (read_range(body_address[body] + 0x120, 4, word) != 4) {
      return finish(1, stat_path);
    }
  }
  return finish(0, stat_path);
}

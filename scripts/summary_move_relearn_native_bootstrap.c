/*
 * Native trust anchor for the Summary move-relearn runtime.
 *
 * This program deliberately links only against the platform C runtime
 * (libSystem on Darwin) and contains its own SHA-256 implementation.  It must
 * be invoked as an externally pinned artifact: the caller authenticates the
 * exact bootstrap SHA-256 (and, on Darwin, its AMFI/code-signature identity)
 * before entering this process, then supplies that same digest through
 * --expected-self-sha256.  The bootstrap self-check is defense in depth; an
 * already substituted program cannot authenticate itself.  This explicit
 * external exact-artifact check is the root of trust.
 *
 * Inventory format (UTF-8/ASCII paths; tabs/newlines are forbidden in paths):
 *
 *   summary-move-relearn-native-bootstrap-inventory-v2\n
 *   F\t<size>\t<lowercase-sha256>\t<absolute-canonical-path>\n
 *   E\t<size>\t<lowercase-sha256>\t<absolute-canonical-python-path>\n
 *   A\t<size>\t<lowercase-sha256>\t<absolute-exec-alias-symlink>\n
 *   L\t<size>\t<lowercase-sha256>\t<absolute-symlink-hop>\n
 *   D\t0\t<sha256-of-empty-input>\t<retained-identity-directory>\n
 *   M\t<payload-size>\t<directory-membership-sha256>\t<sealed-directory>\n
 *   N\t0\t<sha256-of-empty-input>\t<absolute-required-absent-path>\n
 *
 * There must be exactly one E and one A record.  A/L hashes cover the exact
 * readlink bytes. M hashes cover the exact sorted immediate entry names and
 * regular/directory/symlink types; unsupported member types fail closed.
 * Every A/L/N parent must have a retained D record, and the
 * ordered A/L chain must resolve to E.  This preserves
 * the repository .venv argv/executable path so CPython applies pyvenv.cfg
 * while authenticating every symlink hop.  Every record is retained and
 * monitored.  macOS has no fexecve/execveat and does not permit execve of an
 * O_EXEC /dev/fd path, so execve necessarily uses the authenticated A path.
 * Retained dev/inode identity, EVFILT_VNODE monitoring, and
 * complete descriptor/path reauthentication bracket that unavoidable path
 * handoff.  The publication verifier must additionally pin the Python.org
 * Developer-ID/code-sign requirement for the Python executable/framework.
 */

#define _DARWIN_C_SOURCE 1

#include <sys/types.h>
#include <sys/event.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/wait.h>

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif

#ifdef O_NOFOLLOW_ANY
#define BOOTSTRAP_NOFOLLOW O_NOFOLLOW_ANY
#else
#define BOOTSTRAP_NOFOLLOW O_NOFOLLOW
#endif

#define INVENTORY_HEADER \
    "summary-move-relearn-native-bootstrap-inventory-v2\n"
#define READY_MESSAGE "SUMMARY_MOVE_RELEARN_PYTHON_READY_V1\n"
#define GO_MESSAGE "SUMMARY_MOVE_RELEARN_NATIVE_GO_V1\n"
#define PROTOCOL_VERSION "summary-move-relearn-native-bootstrap-v1"
#define MAX_INVENTORY_BYTES (16U * 1024U * 1024U)
#define MAX_RECORDS 8192U
#define MAX_RESULT_PATHS 64U
#define MAX_DRAIN_EVENTS 65536U
#define EVENT_BACKLOG_SELF_TEST_FILES 130U
#define DEFAULT_READY_TIMEOUT_SECONDS 300U

#ifndef SMR_EXPECTED_INVENTORY_SHA256
#error "compile with -DSMR_EXPECTED_INVENTORY_SHA256=\\\"<sha256>\\\""
#endif

static const char compiled_inventory_sha256[] =
    SMR_EXPECTED_INVENTORY_SHA256;

typedef struct {
    uint32_t state[8];
    uint64_t total;
    unsigned char pending[64];
    size_t pending_size;
} Sha256;

typedef struct {
    char kind;
    char *path;
    uint64_t size;
    unsigned char digest[32];
    int fd;
    dev_t device;
    ino_t inode;
} InventoryRecord;

typedef struct {
    InventoryRecord *items;
    size_t count;
    size_t capacity;
    InventoryRecord *executable;
    InventoryRecord *alias;
    size_t absent_count;
} Inventory;

typedef struct {
    const char *inventory_path;
    unsigned char inventory_digest[32];
    unsigned char self_digest[32];
    const char *result_paths[MAX_RESULT_PATHS];
    size_t result_count;
    unsigned ready_timeout_seconds;
    int command_index;
    int print_self_record;
    int inventory_digest_set;
    int self_digest_set;
} Options;

typedef struct {
    const char **paths;
    size_t count;
} ResultTargets;

typedef struct {
    pid_t pid;
    int status;
    int owned;
    int terminal;
    int stopped;
} ChildState;

static const uint32_t sha256_rounds[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
    0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
    0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
    0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
    0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
};

static const unsigned char sha256_empty[32] = {
    0xe3, 0xb0, 0xc4, 0x42, 0x98, 0xfc, 0x1c, 0x14,
    0x9a, 0xfb, 0xf4, 0xc8, 0x99, 0x6f, 0xb9, 0x24,
    0x27, 0xae, 0x41, 0xe4, 0x64, 0x9b, 0x93, 0x4c,
    0xa4, 0x95, 0x99, 0x1b, 0x78, 0x52, 0xb8, 0x55,
};

static const unsigned char directory_digest_domain[] =
    "summary-move-relearn-directory-membership-v1\0";

typedef struct {
    unsigned char kind;
    char *name;
    size_t name_size;
} DirectoryMember;

static uint32_t rotate_right(uint32_t value, unsigned shift) {
    return (value >> shift) | (value << (32U - shift));
}

static void sha256_block(Sha256 *context, const unsigned char block[64]) {
    uint32_t words[64];
    uint32_t a, b, c, d, e, f, g, h;
    size_t index;

    for (index = 0; index < 16; index++) {
        size_t offset = index * 4;
        words[index] = ((uint32_t)block[offset] << 24)
            | ((uint32_t)block[offset + 1] << 16)
            | ((uint32_t)block[offset + 2] << 8)
            | (uint32_t)block[offset + 3];
    }
    for (index = 16; index < 64; index++) {
        uint32_t x = words[index - 15];
        uint32_t y = words[index - 2];
        uint32_t small0 = rotate_right(x, 7) ^ rotate_right(x, 18) ^ (x >> 3);
        uint32_t small1 = rotate_right(y, 17) ^ rotate_right(y, 19) ^ (y >> 10);
        words[index] = words[index - 16] + small0 + words[index - 7] + small1;
    }

    a = context->state[0]; b = context->state[1];
    c = context->state[2]; d = context->state[3];
    e = context->state[4]; f = context->state[5];
    g = context->state[6]; h = context->state[7];
    for (index = 0; index < 64; index++) {
        uint32_t large1 = rotate_right(e, 6) ^ rotate_right(e, 11)
            ^ rotate_right(e, 25);
        uint32_t choose = (e & f) ^ ((~e) & g);
        uint32_t first = h + large1 + choose + sha256_rounds[index]
            + words[index];
        uint32_t large0 = rotate_right(a, 2) ^ rotate_right(a, 13)
            ^ rotate_right(a, 22);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t second = large0 + majority;
        h = g; g = f; f = e; e = d + first;
        d = c; c = b; b = a; a = first + second;
    }
    context->state[0] += a; context->state[1] += b;
    context->state[2] += c; context->state[3] += d;
    context->state[4] += e; context->state[5] += f;
    context->state[6] += g; context->state[7] += h;
}

static void sha256_init(Sha256 *context) {
    static const uint32_t initial[8] = {
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U,
    };
    memcpy(context->state, initial, sizeof(initial));
    context->total = 0;
    context->pending_size = 0;
}

static void sha256_update(Sha256 *context, const void *input, size_t length) {
    const unsigned char *data = input;
    context->total += length;
    while (length != 0) {
        size_t available = 64 - context->pending_size;
        size_t take = length < available ? length : available;
        memcpy(context->pending + context->pending_size, data, take);
        context->pending_size += take;
        data += take;
        length -= take;
        if (context->pending_size == 64) {
            sha256_block(context, context->pending);
            context->pending_size = 0;
        }
    }
}

static void sha256_final(Sha256 *context, unsigned char output[32]) {
    uint64_t bit_length = context->total * 8U;
    unsigned char marker = 0x80;
    unsigned char zero = 0;
    unsigned char length_bytes[8];
    size_t index;

    sha256_update(context, &marker, 1);
    while (context->pending_size != 56)
        sha256_update(context, &zero, 1);
    for (index = 0; index < 8; index++)
        length_bytes[7 - index] = (unsigned char)(bit_length >> (index * 8));
    sha256_update(context, length_bytes, sizeof(length_bytes));
    for (index = 0; index < 8; index++) {
        output[index * 4] = (unsigned char)(context->state[index] >> 24);
        output[index * 4 + 1] = (unsigned char)(context->state[index] >> 16);
        output[index * 4 + 2] = (unsigned char)(context->state[index] >> 8);
        output[index * 4 + 3] = (unsigned char)context->state[index];
    }
}

static int digest_fd(int fd, uint64_t *size, unsigned char digest[32]) {
    Sha256 context;
    unsigned char buffer[128U * 1024U];
    uint64_t total = 0;
    ssize_t count;

    if (lseek(fd, 0, SEEK_SET) < 0)
        return -1;
    sha256_init(&context);
    while ((count = read(fd, buffer, sizeof(buffer))) != 0) {
        if (count < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        sha256_update(&context, buffer, (size_t)count);
        total += (uint64_t)count;
    }
    sha256_final(&context, digest);
    if (size != NULL)
        *size = total;
    return lseek(fd, 0, SEEK_SET) < 0 ? -1 : 0;
}

static void digest_hex(const unsigned char digest[32], char output[65]) {
    static const char alphabet[] = "0123456789abcdef";
    size_t index;
    for (index = 0; index < 32; index++) {
        output[index * 2] = alphabet[digest[index] >> 4];
        output[index * 2 + 1] = alphabet[digest[index] & 15];
    }
    output[64] = '\0';
}

static int parse_digest(const char *text, unsigned char digest[32]) {
    size_t index;
    if (text == NULL || strlen(text) != 64)
        return -1;
    for (index = 0; index < 32; index++) {
        unsigned char high = (unsigned char)text[index * 2];
        unsigned char low = (unsigned char)text[index * 2 + 1];
        if (!((high >= '0' && high <= '9') || (high >= 'a' && high <= 'f'))
            || !((low >= '0' && low <= '9') || (low >= 'a' && low <= 'f')))
            return -1;
        high = high <= '9' ? high - '0' : high - 'a' + 10;
        low = low <= '9' ? low - '0' : low - 'a' + 10;
        digest[index] = (unsigned char)((high << 4) | low);
    }
    return 0;
}

static int canonical_regular_open(const char *path, struct stat *metadata) {
    char resolved[PATH_MAX];
    char descriptor_path[PATH_MAX];
    struct stat before, after;
    int fd;

    if (path == NULL || path[0] != '/' || strchr(path, '\t') != NULL
        || strchr(path, '\n') != NULL || strchr(path, '\r') != NULL) {
        errno = EINVAL;
        return -1;
    }
    if (realpath(path, resolved) == NULL || strcmp(path, resolved) != 0) {
        errno = ELOOP;
        return -1;
    }
    if (lstat(path, &before) != 0 || !S_ISREG(before.st_mode)) {
        errno = EINVAL;
        return -1;
    }
    fd = open(path, O_RDONLY | O_CLOEXEC | BOOTSTRAP_NOFOLLOW);
    if (fd < 0)
        return -1;
    if (fstat(fd, &after) != 0 || !S_ISREG(after.st_mode)
        || before.st_dev != after.st_dev || before.st_ino != after.st_ino) {
        close(fd);
        errno = ESTALE;
        return -1;
    }
#ifdef F_GETPATH
    if (fcntl(fd, F_GETPATH, descriptor_path) != 0
        || strcmp(descriptor_path, path) != 0) {
        close(fd);
        errno = ESTALE;
        return -1;
    }
#endif
    *metadata = after;
    return fd;
}

static int symlink_open(const char *path, struct stat *metadata) {
    struct stat before, after;
    int fd;
    if (path == NULL || path[0] != '/' || strchr(path, '\t') != NULL
        || strchr(path, '\n') != NULL || strchr(path, '\r') != NULL
        || lstat(path, &before) != 0 || !S_ISLNK(before.st_mode)) {
        errno = EINVAL;
        return -1;
    }
#ifdef O_SYMLINK
    fd = open(path, O_RDONLY | O_CLOEXEC | O_SYMLINK);
#else
    (void)metadata;
    errno = ENOTSUP;
    return -1;
#endif
    if (fd < 0)
        return -1;
    if (fstat(fd, &after) != 0 || !S_ISLNK(after.st_mode)
        || before.st_dev != after.st_dev || before.st_ino != after.st_ino) {
        close(fd);
        errno = ESTALE;
        return -1;
    }
    *metadata = after;
    return fd;
}

static int directory_open(const char *path, struct stat *metadata) {
    char resolved[PATH_MAX];
    struct stat before, after;
    int fd;
    if (path == NULL || path[0] != '/' || realpath(path, resolved) == NULL
        || strcmp(path, resolved) != 0 || lstat(path, &before) != 0
        || !S_ISDIR(before.st_mode)) {
        errno = EINVAL;
        return -1;
    }
    fd = open(path, O_RDONLY | O_DIRECTORY | O_CLOEXEC | BOOTSTRAP_NOFOLLOW);
    if (fd < 0)
        return -1;
    if (fstat(fd, &after) != 0 || !S_ISDIR(after.st_mode)
        || before.st_dev != after.st_dev || before.st_ino != after.st_ino) {
        close(fd);
        errno = ESTALE;
        return -1;
    }
    *metadata = after;
    return fd;
}

static int digest_symlink(const char *path, uint64_t *size,
    unsigned char digest[32], char *target, size_t target_capacity) {
    char buffer[PATH_MAX];
    ssize_t count = readlink(path, buffer, sizeof(buffer));
    Sha256 context;
    if (count < 0 || (size_t)count >= sizeof(buffer)
        || (target != NULL && (size_t)count + 1 > target_capacity)) {
        errno = ENAMETOOLONG;
        return -1;
    }
    sha256_init(&context);
    sha256_update(&context, buffer, (size_t)count);
    sha256_final(&context, digest);
    *size = (uint64_t)count;
    if (target != NULL) {
        memcpy(target, buffer, (size_t)count);
        target[count] = '\0';
    }
    return 0;
}

static int compare_directory_members(const void *left, const void *right) {
    const DirectoryMember *a = left;
    const DirectoryMember *b = right;
    size_t common = a->name_size < b->name_size ? a->name_size : b->name_size;
    int compared = memcmp(a->name, b->name, common);
    if (compared != 0)
        return compared;
    return a->name_size < b->name_size ? -1 : a->name_size > b->name_size;
}

static void sha256_u64_big_endian(Sha256 *context, uint64_t value) {
    unsigned char encoded[8];
    size_t index;
    for (index = 0; index < sizeof(encoded); index++)
        encoded[sizeof(encoded) - index - 1] = (unsigned char)(value >> (index * 8));
    sha256_update(context, encoded, sizeof(encoded));
}

static int digest_directory(int fd, uint64_t *size,
    unsigned char digest[32]) {
    DirectoryMember *members = NULL;
    size_t count = 0, capacity = 0, index;
    DIR *stream = NULL;
    struct dirent *entry;
    Sha256 context;
    int duplicate = openat(fd, ".",
        O_RDONLY | O_DIRECTORY | O_CLOEXEC | BOOTSTRAP_NOFOLLOW);
    int result = -1;
    if (duplicate < 0)
        return -1;
    stream = fdopendir(duplicate);
    if (stream == NULL) {
        close(duplicate);
        return -1;
    }
    errno = 0;
    while ((entry = readdir(stream)) != NULL) {
        struct stat metadata;
        DirectoryMember member;
        size_t name_size;
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0)
            continue;
        if (fstatat(fd, entry->d_name, &metadata, AT_SYMLINK_NOFOLLOW) != 0)
            goto cleanup;
        if (S_ISREG(metadata.st_mode))
            member.kind = 'F';
        else if (S_ISDIR(metadata.st_mode))
            member.kind = 'D';
        else if (S_ISLNK(metadata.st_mode))
            member.kind = 'L';
        else {
            errno = EAUTH;
            goto cleanup;
        }
        name_size = strlen(entry->d_name);
        member.name = malloc(name_size + 1);
        if (member.name == NULL)
            goto cleanup;
        memcpy(member.name, entry->d_name, name_size + 1);
        member.name_size = name_size;
        if (count == capacity) {
            size_t next = capacity == 0 ? 32 : capacity * 2;
            DirectoryMember *resized = realloc(members, next * sizeof(*resized));
            if (resized == NULL) {
                free(member.name);
                goto cleanup;
            }
            members = resized;
            capacity = next;
        }
        members[count++] = member;
        errno = 0;
    }
    if (errno != 0)
        goto cleanup;
    qsort(members, count, sizeof(*members), compare_directory_members);
    sha256_init(&context);
    sha256_update(&context, directory_digest_domain,
        sizeof(directory_digest_domain) - 1);
    for (index = 0; index < count; index++) {
        sha256_update(&context, &members[index].kind, 1);
        sha256_u64_big_endian(&context, (uint64_t)members[index].name_size);
        sha256_update(&context, members[index].name, members[index].name_size);
    }
    sha256_final(&context, digest);
    *size = (uint64_t)(sizeof(directory_digest_domain) - 1);
    for (index = 0; index < count; index++)
        *size += 1U + 8U + (uint64_t)members[index].name_size;
    result = 0;

cleanup:
    if (stream != NULL)
        closedir(stream);
    for (index = 0; index < count; index++)
        free(members[index].name);
    free(members);
    return result;
}

static int normalize_absolute_lexical(const char *input, char output[PATH_MAX]) {
    char copy[PATH_MAX], *component, *save = NULL;
    const char *parts[PATH_MAX / 2];
    size_t count = 0, used = 1, index;
    if (input == NULL || input[0] != '/' || strlen(input) >= sizeof(copy))
        return -1;
    memcpy(copy, input, strlen(input) + 1);
    for (component = strtok_r(copy, "/", &save); component != NULL;
            component = strtok_r(NULL, "/", &save)) {
        if (strcmp(component, ".") == 0 || *component == '\0')
            continue;
        if (strcmp(component, "..") == 0) {
            if (count == 0)
                return -1;
            count--;
        } else {
            parts[count++] = component;
        }
    }
    output[0] = '/';
    output[1] = '\0';
    for (index = 0; index < count; index++) {
        size_t length = strlen(parts[index]);
        if (used + length + (index + 1 < count ? 1 : 0) >= PATH_MAX)
            return -1;
        memcpy(output + used, parts[index], length);
        used += length;
        if (index + 1 < count)
            output[used++] = '/';
        output[used] = '\0';
    }
    return 0;
}

static int resolve_symlink_target(const char *link_path, const char *target,
    char output[PATH_MAX]) {
    char combined[PATH_MAX];
    const char *slash;
    int length;
    if (target[0] == '/')
        return normalize_absolute_lexical(target, output);
    slash = strrchr(link_path, '/');
    if (slash == NULL)
        return -1;
    length = snprintf(combined, sizeof(combined), "%.*s/%s",
        (int)(slash - link_path), link_path, target);
    return length < 0 || (size_t)length >= sizeof(combined)
        ? -1 : normalize_absolute_lexical(combined, output);
}

static int executable_path(char output[PATH_MAX]) {
#ifdef __APPLE__
    char raw[PATH_MAX];
    uint32_t size = sizeof(raw);
    if (_NSGetExecutablePath(raw, &size) != 0 || realpath(raw, output) == NULL)
        return -1;
#else
    ssize_t count = readlink("/proc/self/exe", output, PATH_MAX - 1);
    if (count < 0)
        return -1;
    output[count] = '\0';
#endif
    return 0;
}

static int self_record(unsigned char expected[32], int check, int print) {
    char path[PATH_MAX], hex[65];
    unsigned char actual[32];
    struct stat metadata;
    uint64_t size;
    int fd;

    if (executable_path(path) != 0)
        return -1;
    fd = canonical_regular_open(path, &metadata);
    if (fd < 0)
        return -1;
    if (digest_fd(fd, &size, actual) != 0) {
        close(fd);
        return -1;
    }
    close(fd);
    if (check && memcmp(actual, expected, 32) != 0) {
        errno = EAUTH;
        return -1;
    }
    if (print) {
        digest_hex(actual, hex);
        printf("%s\t%llu\t%s\n", path, (unsigned long long)size, hex);
    }
    return 0;
}

static int read_bounded_fd(int fd, unsigned char **data, size_t *size) {
    struct stat metadata;
    size_t used = 0;
    unsigned char *buffer;
    if (fstat(fd, &metadata) != 0 || metadata.st_size < 0
        || (uint64_t)metadata.st_size > MAX_INVENTORY_BYTES) {
        errno = EFBIG;
        return -1;
    }
    buffer = malloc((size_t)metadata.st_size + 1);
    if (buffer == NULL)
        return -1;
    if (lseek(fd, 0, SEEK_SET) < 0) {
        free(buffer);
        return -1;
    }
    while (used < (size_t)metadata.st_size) {
        ssize_t count = read(fd, buffer + used, (size_t)metadata.st_size - used);
        if (count < 0 && errno == EINTR)
            continue;
        if (count <= 0) {
            free(buffer);
            errno = EIO;
            return -1;
        }
        used += (size_t)count;
    }
    buffer[used] = '\0';
    *data = buffer;
    *size = used;
    return lseek(fd, 0, SEEK_SET) < 0 ? -1 : 0;
}

static int inventory_append(Inventory *inventory, InventoryRecord record) {
    InventoryRecord *resized;
    size_t capacity;
    if (inventory->count == MAX_RECORDS) {
        errno = E2BIG;
        return -1;
    }
    if (inventory->count == inventory->capacity) {
        capacity = inventory->capacity == 0 ? 128 : inventory->capacity * 2;
        resized = realloc(inventory->items, capacity * sizeof(*resized));
        if (resized == NULL)
            return -1;
        inventory->items = resized;
        inventory->capacity = capacity;
    }
    inventory->items[inventory->count++] = record;
    return 0;
}

static int require_descriptor_capacity(size_t inventory_count) {
    struct rlimit limit;
    rlim_t required = (rlim_t)inventory_count + 32U;
    if (getrlimit(RLIMIT_NOFILE, &limit) != 0)
        return -1;
    if (limit.rlim_max != RLIM_INFINITY && limit.rlim_max < required) {
        errno = EMFILE;
        return -1;
    }
    if (limit.rlim_cur < required) {
        limit.rlim_cur = required;
        if (setrlimit(RLIMIT_NOFILE, &limit) != 0)
            return -1;
    }
    return 0;
}

static int parse_u64(const char *text, uint64_t *value) {
    char *end;
    unsigned long long parsed;
    if (text == NULL || *text == '\0' || (*text == '0' && text[1] != '\0'))
        return -1;
    errno = 0;
    parsed = strtoull(text, &end, 10);
    if (errno != 0 || *end != '\0')
        return -1;
    *value = (uint64_t)parsed;
    return 0;
}

static int parse_inventory(unsigned char *data, size_t size, Inventory *result) {
    char *cursor = (char *)data;
    char *end = (char *)data + size;
    size_t header_size = strlen(INVENTORY_HEADER);
    if (size <= header_size || memcmp(data, INVENTORY_HEADER, header_size) != 0)
        return -1;
    cursor += header_size;
    while (cursor < end) {
        InventoryRecord record;
        char *line_end = memchr(cursor, '\n', (size_t)(end - cursor));
        char *first, *second, *third;
        char saved;
        memset(&record, 0, sizeof(record));
        record.fd = -1;
        if (line_end == NULL || line_end == cursor)
            return -1;
        saved = *line_end;
        *line_end = '\0';
        first = strchr(cursor, '\t');
        second = first == NULL ? NULL : strchr(first + 1, '\t');
        third = second == NULL ? NULL : strchr(second + 1, '\t');
        if (first == NULL || second == NULL || third == NULL
            || strchr(third + 1, '\t') != NULL || first != cursor + 1
            || (cursor[0] != 'F' && cursor[0] != 'E'
                && cursor[0] != 'A' && cursor[0] != 'L'
                && cursor[0] != 'D' && cursor[0] != 'M'
                && cursor[0] != 'N'))
            return -1;
        *first = '\0'; *second = '\0'; *third = '\0';
        record.kind = cursor[0];
        if (parse_u64(first + 1, &record.size) != 0
            || parse_digest(second + 1, record.digest) != 0
            || third[1] != '/')
            return -1;
        record.path = strdup(third + 1);
        if (record.path == NULL || inventory_append(result, record) != 0)
            return -1;
        *line_end = saved;
        cursor = line_end + 1;
    }
    if (result->count == 0)
        return -1;
    for (size_t index = 0; index < result->count; index++) {
        size_t prior;
        if (result->items[index].kind == 'E') {
            if (result->executable != NULL)
                return -1;
            result->executable = &result->items[index];
        }
        if (result->items[index].kind == 'A') {
            if (result->alias != NULL)
                return -1;
            result->alias = &result->items[index];
        }
        if (result->items[index].kind == 'N')
            result->absent_count++;
        for (prior = 0; prior < index; prior++)
            if (strcmp(result->items[prior].path,
                    result->items[index].path) == 0)
                return -1;
    }
    if (result->executable == NULL || result->alias == NULL
        || result->absent_count == 0)
        return -1;
    return 0;
}

static int authenticate_record(InventoryRecord *record) {
    struct stat metadata;
    unsigned char digest[32];
    uint64_t size;
    int fd;
    if (record->kind == 'N') {
        char normalized[PATH_MAX];
        if (record->size != 0 || memcmp(record->digest, sha256_empty, 32) != 0
            || normalize_absolute_lexical(record->path, normalized) != 0
            || strcmp(record->path, normalized) != 0
            || lstat(record->path, &metadata) == 0 || errno != ENOENT) {
            errno = EAUTH;
            return -1;
        }
        record->fd = -1;
        return 0;
    }
    fd = record->kind == 'A' || record->kind == 'L'
        ? symlink_open(record->path, &metadata)
        : ((record->kind == 'D' || record->kind == 'M')
            ? directory_open(record->path, &metadata)
                               : canonical_regular_open(record->path, &metadata));
    if (fd < 0)
        return -1;
    if ((record->kind == 'D'
            ? (size = 0, memcpy(digest, sha256_empty, 32), 0)
            : (record->kind == 'M'
            ? digest_directory(fd, &size, digest)
            : (record->kind == 'A' || record->kind == 'L'
            ? digest_symlink(record->path, &size, digest, NULL, 0)
            : digest_fd(fd, &size, digest)))) != 0
        || size != record->size
        || memcmp(digest, record->digest, 32) != 0) {
        char actual_hex[65], expected_hex[65];
        digest_hex(digest, actual_hex);
        digest_hex(record->digest, expected_hex);
        fprintf(stderr,
            "native bootstrap: record digest differs: %s: "
            "actual=%llu/%s expected=%llu/%s\n",
            record->path, (unsigned long long)size, actual_hex,
            (unsigned long long)record->size, expected_hex);
        close(fd);
        errno = EAUTH;
        return -1;
    }
    record->fd = fd;
    record->device = metadata.st_dev;
    record->inode = metadata.st_ino;
    return 0;
}

static int reauthenticate_record(InventoryRecord *record) {
    char resolved[PATH_MAX];
    struct stat path_metadata, descriptor_metadata;
    unsigned char digest[32];
    uint64_t size;
    int symlink = record->kind == 'A' || record->kind == 'L';
    int directory = record->kind == 'D' || record->kind == 'M';
    int membership = record->kind == 'M';
    if (record->kind == 'N') {
        if (lstat(record->path, &path_metadata) == 0 || errno != ENOENT) {
            errno = EAUTH;
            return -1;
        }
        return 0;
    }
    if (lstat(record->path, &path_metadata) != 0
        || (symlink ? !S_ISLNK(path_metadata.st_mode)
                    : (directory ? !S_ISDIR(path_metadata.st_mode)
                                 : !S_ISREG(path_metadata.st_mode)))
        || (!symlink && (realpath(record->path, resolved) == NULL
            || strcmp(resolved, record->path) != 0))
        || fstat(record->fd, &descriptor_metadata) != 0
        || path_metadata.st_dev != record->device
        || path_metadata.st_ino != record->inode
        || descriptor_metadata.st_dev != record->device
        || descriptor_metadata.st_ino != record->inode
        || (membership && digest_directory(record->fd, &size, digest) != 0)
        || (!directory && (symlink
            ? digest_symlink(record->path, &size, digest, NULL, 0)
            : digest_fd(record->fd, &size, digest)) != 0)
        || (!directory && (size != record->size
            || memcmp(digest, record->digest, 32) != 0))
        || (membership && (size != record->size
            || memcmp(digest, record->digest, 32) != 0))) {
        errno = ESTALE;
        return -1;
    }
    return 0;
}

static InventoryRecord *inventory_find(Inventory *inventory, const char *path) {
    size_t index;
    for (index = 0; index < inventory->count; index++)
        if (strcmp(inventory->items[index].path, path) == 0)
            return &inventory->items[index];
    return NULL;
}

static void refresh_special_records(Inventory *inventory) {
    size_t index;
    inventory->alias = NULL;
    inventory->executable = NULL;
    for (index = 0; index < inventory->count; index++) {
        if (inventory->items[index].kind == 'A')
            inventory->alias = &inventory->items[index];
        else if (inventory->items[index].kind == 'E')
            inventory->executable = &inventory->items[index];
    }
}

static int append_anchor(Inventory *inventory, const char *path,
    uint64_t size, const unsigned char digest[32]) {
    InventoryRecord record;
    if (inventory_find(inventory, path) != NULL) {
        errno = EINVAL;
        return -1;
    }
    memset(&record, 0, sizeof(record));
    record.kind = 'F';
    record.path = strdup(path);
    record.size = size;
    memcpy(record.digest, digest, 32);
    record.fd = -1;
    if (record.path == NULL || inventory_append(inventory, record) != 0) {
        free(record.path);
        return -1;
    }
    refresh_special_records(inventory);
    return 0;
}

static int validate_exec_chain(Inventory *inventory) {
    InventoryRecord *current = inventory->alias;
    char target[PATH_MAX], next[PATH_MAX], canonical[PATH_MAX];
    unsigned char ignored_digest[32];
    uint64_t ignored_size;
    size_t steps = 0;
    while (current != inventory->executable) {
        if (current == NULL || (current->kind != 'A' && current->kind != 'L')
            || ++steps > inventory->count
            || digest_symlink(current->path, &ignored_size, ignored_digest,
                target, sizeof(target)) != 0
            || resolve_symlink_target(current->path, target, next) != 0)
            return -1;
        current = inventory_find(inventory, next);
    }
    if (realpath(inventory->alias->path, canonical) == NULL
        || strcmp(canonical, inventory->executable->path) != 0)
        return -1;
    return 0;
}

static int validate_parent_records(Inventory *inventory) {
    size_t index;
    for (index = 0; index < inventory->count; index++) {
        InventoryRecord *record = &inventory->items[index];
        char parent[PATH_MAX], *slash;
        InventoryRecord *parent_record;
        if (record->kind != 'A' && record->kind != 'L'
            && record->kind != 'N' && record->kind != 'F'
            && record->kind != 'E')
            continue;
        if (strlen(record->path) >= sizeof(parent))
            return -1;
        memcpy(parent, record->path, strlen(record->path) + 1);
        slash = strrchr(parent, '/');
        if (slash == NULL)
            return -1;
        if (slash == parent)
            slash[1] = '\0';
        else
            *slash = '\0';
        parent_record = inventory_find(inventory, parent);
        if (parent_record == NULL
            || ((record->kind == 'F' || record->kind == 'E')
                && parent_record->kind != 'M')
            || ((record->kind == 'A' || record->kind == 'L'
                    || record->kind == 'N')
                && parent_record->kind != 'D'
                && parent_record->kind != 'M'))
            return -1;
    }
    return 0;
}

static int reauthenticate_inventory(Inventory *inventory) {
    size_t index;
    for (index = 0; index < inventory->count; index++)
        if (reauthenticate_record(&inventory->items[index]) != 0)
            return -1;
    return 0;
}

static int register_monitors(int queue, Inventory *inventory) {
    size_t index;
    const uint32_t notes = NOTE_WRITE | NOTE_DELETE | NOTE_EXTEND
        | NOTE_ATTRIB | NOTE_LINK | NOTE_RENAME | NOTE_REVOKE;
    for (index = 0; index < inventory->count; index++) {
        struct kevent change;
        if (inventory->items[index].kind == 'N')
            continue;
        EV_SET(&change, (uintptr_t)inventory->items[index].fd,
            EVFILT_VNODE, EV_ADD | EV_CLEAR, notes, 0,
            &inventory->items[index]);
        if (kevent(queue, &change, 1, NULL, 0, NULL) != 0)
            return -1;
    }
    return 0;
}

static int monitor_clean(int queue) {
    struct kevent events[64];
    struct timespec immediate = {0, 0};
    int clean = 1;
    size_t drained = 0;
    for (;;) {
        int count = kevent(queue, NULL, 0, events,
            (int)(sizeof(events) / sizeof(events[0])), &immediate);
        int index;
        if (count < 0 && errno == EINTR)
            continue;
        if (count < 0)
            return 0;
        if (count == 0)
            return clean;
        drained += (size_t)count;
        if (drained > MAX_DRAIN_EVENTS) {
            fprintf(stderr, "native bootstrap: vnode event backlog exceeds limit\n");
            return 0;
        }
        for (index = 0; index < count; index++) {
            InventoryRecord *record = events[index].udata;
            /* execve updates access metadata on Darwin. Attribute-only events
             * are accepted only after exact descriptor/path/content or
             * directory-membership reauthentication. Every topology/data
             * event is fatal. The loop drains the complete ready backlog. */
            if (events[index].fflags == NOTE_ATTRIB && record != NULL
                && reauthenticate_record(record) == 0)
                continue;
            fprintf(stderr, "native bootstrap: vnode event 0x%x: %s\n",
                events[index].fflags,
                record != NULL ? record->path : "<unknown>");
            clean = 0;
        }
    }
}

static int event_backlog_self_test(void) {
    char directory[] = "/private/tmp/summary-relearn-event-backlog.XXXXXX";
    char paths[EVENT_BACKLOG_SELF_TEST_FILES][PATH_MAX];
    int descriptors[EVENT_BACKLOG_SELF_TEST_FILES];
    InventoryRecord records[EVENT_BACKLOG_SELF_TEST_FILES];
    int queue = -1;
    struct kevent first_batch[64];
    struct timespec timeout = {1, 0};
    size_t index, created = 0;
    int count, result = -1, stage = 0;
    memset(descriptors, -1, sizeof(descriptors));
    memset(records, 0, sizeof(records));
    if (mkdtemp(directory) == NULL)
        return -1;
    stage = 1;
    queue = kqueue();
    if (queue < 0)
        goto cleanup;
    stage = 2;
    for (index = 0; index < EVENT_BACKLOG_SELF_TEST_FILES; index++) {
        struct kevent change;
        struct stat metadata;
        int written = snprintf(paths[index], sizeof(paths[index]),
            "%s/event-%03zu", directory, index);
        if (written < 0 || (size_t)written >= sizeof(paths[index]))
            goto cleanup;
        descriptors[index] = open(paths[index],
            O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC | BOOTSTRAP_NOFOLLOW, 0600);
        if (descriptors[index] < 0)
            goto cleanup;
        created++;
        records[index].kind = 'F';
        records[index].path = paths[index];
        records[index].fd = descriptors[index];
        if (fstat(descriptors[index], &metadata) != 0
            || digest_fd(descriptors[index], &records[index].size,
                records[index].digest) != 0)
            goto cleanup;
        records[index].device = metadata.st_dev;
        records[index].inode = metadata.st_ino;
        EV_SET(&change, (uintptr_t)descriptors[index], EVFILT_VNODE,
            EV_ADD | EV_CLEAR, NOTE_WRITE | NOTE_EXTEND | NOTE_ATTRIB, 0,
            &records[index]);
        if (kevent(queue, &change, 1, NULL, 0, NULL) != 0)
            goto cleanup;
    }
    stage = 3;
    for (index = 0; index + 1 < EVENT_BACKLOG_SELF_TEST_FILES; index++)
        if (fchmod(descriptors[index], 0640) != 0)
            goto cleanup;
    if (write(descriptors[EVENT_BACKLOG_SELF_TEST_FILES - 1], "x", 1) != 1)
        goto cleanup;
    stage = 4;
    count = kevent(queue, NULL, 0, first_batch,
        (int)(sizeof(first_batch) / sizeof(first_batch[0])), &timeout);
    if (count != (int)(sizeof(first_batch) / sizeof(first_batch[0]))) {
        fprintf(stderr, "native bootstrap: same-kqueue first-batch=%d\n", count);
        goto cleanup;
    }
    for (int event = 0; event < count; event++) {
        InventoryRecord *record = first_batch[event].udata;
        if (first_batch[event].fflags != NOTE_ATTRIB || record == NULL
            || record == &records[EVENT_BACKLOG_SELF_TEST_FILES - 1]
            || reauthenticate_record(record) != 0) {
            fprintf(stderr,
                "native bootstrap: same-kqueue first batch is decisive at %d\n",
                event);
            goto cleanup;
        }
    }
    fprintf(stderr, "native bootstrap: same-kqueue first-batch=64\n");
    if (monitor_clean(queue) != 0) {
        fprintf(stderr, "native bootstrap: backlog drain accepted mutation\n");
        goto cleanup;
    }
    result = 0;

cleanup:
    if (queue >= 0)
        close(queue);
    for (index = 0; index < created; index++) {
        if (descriptors[index] >= 0)
            close(descriptors[index]);
        (void)unlink(paths[index]);
    }
    (void)rmdir(directory);
    if (result != 0)
        fprintf(stderr, "native bootstrap: backlog self-test failed stage=%d errno=%d\n",
            stage, errno);
    return result;
}

static int poll_child(ChildState *child) {
    for (;;) {
        pid_t waited;
        if (!child->owned)
            return child->terminal ? 1 : -1;
        waited = waitpid(child->pid, &child->status, WNOHANG | WUNTRACED);
        if (waited == 0)
            return 0;
        if (waited == child->pid) {
            if (WIFEXITED(child->status) || WIFSIGNALED(child->status)) {
                child->terminal = 1;
                child->stopped = 0;
                child->owned = 0;
            } else if (WIFSTOPPED(child->status)) {
                child->stopped = 1;
            }
            return 1;
        }
        if (errno == EINTR)
            continue;
        if (errno == ECHILD)
            child->owned = 0;
        return -1;
    }
}

static int terminate_and_reap(ChildState *child) {
    struct timespec started, now, delay = {0, 10000000};
    if (!child->owned)
        return child->terminal ? 0 : -1;
    if (kill(child->pid, SIGKILL) != 0 && errno != ESRCH)
        return -1;
    if (clock_gettime(CLOCK_MONOTONIC, &started) != 0)
        return -1;
    while (child->owned) {
        int polled = poll_child(child);
        if (polled < 0)
            return -1;
        if (child->terminal)
            return 0;
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0
            || now.tv_sec - started.tv_sec >= 5) {
            errno = ETIMEDOUT;
            return -1;
        }
        (void)nanosleep(&delay, NULL);
    }
    return child->terminal ? 0 : -1;
}

static int exact_read(int fd, const char *expected, unsigned timeout_seconds,
    int queue, ChildState *child) {
    size_t expected_size = strlen(expected), used = 0;
    char buffer[128];
    struct timespec started, now, delay = {0, 10000000};
    if (expected_size >= sizeof(buffer) || clock_gettime(CLOCK_MONOTONIC, &started) != 0)
        return -1;
    while (used < expected_size) {
        ssize_t count = read(fd, buffer + used, expected_size - used);
        if (count > 0) {
            used += (size_t)count;
            continue;
        }
        if (count == 0)
            return -1;
        if (errno != EAGAIN && errno != EINTR)
            return -1;
        if (!monitor_clean(queue))
            return -1;
        if (poll_child(child) != 0 || child->stopped)
            return -1;
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0
            || (uint64_t)(now.tv_sec - started.tv_sec) >= timeout_seconds) {
            errno = ETIMEDOUT;
            return -1;
        }
        nanosleep(&delay, NULL);
    }
    if (memcmp(buffer, expected, expected_size) != 0)
        return -1;
    return 0;
}

static int exact_write(int fd, const char *message) {
    size_t size = strlen(message), written = 0;
    while (written < size) {
        ssize_t count = write(fd, message + written, size - written);
        if (count < 0 && errno == EINTR)
            continue;
        if (count <= 0)
            return -1;
        written += (size_t)count;
    }
    return 0;
}

static int lexical_absolute_path(const char *path) {
    const char *component;
    size_t path_size;
    if (path == NULL || path[0] != '/' || path[1] == '/' || path[1] == '\0'
        || strchr(path, '\t') != NULL || strchr(path, '\n') != NULL
        || strchr(path, '\r') != NULL)
        return 0;
    path_size = strlen(path);
    if (path[path_size - 1] == '/')
        return 0;
    component = path + 1;
    while (*component != '\0') {
        const char *slash = strchr(component, '/');
        size_t size = slash == NULL ? strlen(component)
            : (size_t)(slash - component);
        if (size == 0 || (size == 1 && component[0] == '.')
            || (size == 2 && component[0] == '.' && component[1] == '.'))
            return 0;
        if (slash == NULL)
            break;
        component = slash + 1;
    }
    return 1;
}

static int invalidate_result_path(const char *path) {
    if (!lexical_absolute_path(path)) {
        errno = EINVAL;
        return -1;
    }
    if (unlink(path) == 0 || errno == ENOENT)
        return 0;
    return -1;
}

static int invalidate_results(const ResultTargets *targets) {
    size_t index;
    int result = 0;
    for (index = 0; index < targets->count; index++) {
        if (invalidate_result_path(targets->paths[index]) != 0) {
            fprintf(stderr, "native bootstrap: result invalidation failed: %s\n",
                targets->paths[index]);
            result = -1;
        }
    }
    return result;
}

static int collect_result_targets(int argc, char **argv,
    ResultTargets *targets) {
    int index, malformed = 0;
    targets->paths = calloc((size_t)argc, sizeof(*targets->paths));
    targets->count = 0;
    if (targets->paths == NULL)
        return -1;
    for (index = 1; index < argc; index++) {
        const char *argument = argv[index];
        if (strcmp(argument, "--") == 0)
            break;
        if (strcmp(argument, "--invalidate-result") == 0) {
            if (index + 1 >= argc || strncmp(argv[index + 1], "--", 2) == 0) {
                malformed = 1;
                continue;
            }
            targets->paths[targets->count++] = argv[++index];
            continue;
        }
        if (strncmp(argument, "--invalidate-result=", 20) == 0) {
            targets->paths[targets->count++] = argument + 20;
            continue;
        }
        if (strcmp(argument, "--inventory") == 0
            || strcmp(argument, "--expected-inventory-sha256") == 0
            || strcmp(argument, "--expected-self-sha256") == 0
            || strcmp(argument, "--ready-timeout-seconds") == 0) {
            if (index + 1 < argc
                && strncmp(argv[index + 1], "--", 2) != 0)
                index++;
            else
                malformed = 1;
        }
    }
    return malformed ? -1 : 0;
}

static int parse_options(int argc, char **argv, Options *options) {
    int index;
    memset(options, 0, sizeof(*options));
    options->ready_timeout_seconds = DEFAULT_READY_TIMEOUT_SECONDS;
    if (argc == 2 && strcmp(argv[1], "--print-self-record") == 0) {
        options->print_self_record = 1;
        return 0;
    }
    for (index = 1; index < argc; index++) {
        const char *argument = argv[index];
        const char *value = NULL;
        if (strcmp(argument, "--") == 0) {
            options->command_index = index + 1;
            break;
        }
#define OPTION_VALUE(name) \
        if (strcmp(argument, name) == 0 && index + 1 < argc) value = argv[++index]; \
        else if (strncmp(argument, name "=", sizeof(name)) == 0) value = argument + sizeof(name)
        OPTION_VALUE("--inventory");
        if (value != NULL) {
            if (options->inventory_path != NULL) return -1;
            options->inventory_path = value;
            continue;
        }
        OPTION_VALUE("--expected-inventory-sha256");
        if (value != NULL) {
            if (options->inventory_digest_set) return -1;
            if (parse_digest(value, options->inventory_digest) != 0) return -1;
            options->inventory_digest_set = 1;
            continue;
        }
        OPTION_VALUE("--expected-self-sha256");
        if (value != NULL) {
            if (options->self_digest_set) return -1;
            if (parse_digest(value, options->self_digest) != 0) return -1;
            options->self_digest_set = 1;
            continue;
        }
        OPTION_VALUE("--invalidate-result");
        if (value != NULL) {
            if (!lexical_absolute_path(value)) return -1;
            if (options->result_count == MAX_RESULT_PATHS) return -1;
            options->result_paths[options->result_count++] = value;
            continue;
        }
        OPTION_VALUE("--ready-timeout-seconds");
        if (value != NULL) {
            uint64_t timeout;
            if (parse_u64(value, &timeout) != 0 || timeout == 0 || timeout > 3600)
                return -1;
            options->ready_timeout_seconds = (unsigned)timeout;
            continue;
        }
#undef OPTION_VALUE
        return -1;
    }
    if (options->inventory_path == NULL || !options->inventory_digest_set
        || !options->self_digest_set || options->command_index <= 0
        || options->command_index >= argc || argv[options->command_index][0] == '\0')
        return -1;
    return 0;
}

static int set_inheritable(int fd) {
    int flags = fcntl(fd, F_GETFD);
    return flags < 0 ? -1 : fcntl(fd, F_SETFD, flags & ~FD_CLOEXEC);
}

static int has_path_suffix(const char *path, const char *suffix) {
    size_t path_size = strlen(path), suffix_size = strlen(suffix);
    return path_size >= suffix_size
        && memcmp(path + path_size - suffix_size, suffix, suffix_size) == 0;
}

static int validate_python_command(const Inventory *inventory, char **command) {
    static const char launcher_suffix[] =
        "/scripts/launch_summary_move_relearn_runtime.py";
    static const char binder_suffix[] =
        "/scripts/pokemon_move_history_build_manifest.py";
    size_t index;
    if (command[0] == NULL || command[1] == NULL || command[2] == NULL
        || command[3] == NULL || command[4] == NULL || command[5] == NULL
        || command[6] == NULL
        || strcmp(command[0], inventory->alias->path) != 0
        || strcmp(command[1], "-I") != 0
        || strcmp(command[2], "-S") != 0
        || strcmp(command[3], "-B") != 0
        || strcmp(command[4], "-X") != 0
        || strcmp(command[5], "pycache_prefix=/dev/null") != 0
        || (!has_path_suffix(command[6], launcher_suffix)
            && !has_path_suffix(command[6], binder_suffix)))
        return -1;
    for (index = 0; index < inventory->count; index++) {
        const InventoryRecord *record = &inventory->items[index];
        if (record->kind == 'F' && strcmp(record->path, command[6]) == 0)
            return 0;
    }
    return -1;
}

static int child_exec(const Inventory *inventory, const Options *options,
    const char *self_path, char **command, int ready_fd, int go_fd) {
    char ready_text[64], go_text[64];
    char bootstrap_text[PATH_MAX + 64], inventory_text[PATH_MAX + 64];
    char self_sha_text[128], inventory_sha_text[128];
    char self_hex[65], inventory_hex[65];
    char *environment[12];
    int index = 0;
    if (set_inheritable(ready_fd) != 0 || set_inheritable(go_fd) != 0)
        return -1;
    snprintf(ready_text, sizeof(ready_text),
        "SUMMARY_MOVE_RELEARN_BOOTSTRAP_READY_FD=%d", ready_fd);
    snprintf(go_text, sizeof(go_text),
        "SUMMARY_MOVE_RELEARN_BOOTSTRAP_GO_FD=%d", go_fd);
    digest_hex(options->self_digest, self_hex);
    digest_hex(options->inventory_digest, inventory_hex);
    snprintf(bootstrap_text, sizeof(bootstrap_text),
        "SUMMARY_MOVE_RELEARN_BOOTSTRAP_PATH=%s", self_path);
    snprintf(inventory_text, sizeof(inventory_text),
        "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_PATH=%s",
        options->inventory_path);
    snprintf(self_sha_text, sizeof(self_sha_text),
        "SUMMARY_MOVE_RELEARN_BOOTSTRAP_SELF_SHA256=%s", self_hex);
    snprintf(inventory_sha_text, sizeof(inventory_sha_text),
        "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_SHA256=%s", inventory_hex);
    environment[index++] = "PATH=/usr/bin:/bin";
    environment[index++] = "LC_ALL=C";
    environment[index++] = "SDL_AUDIODRIVER=dummy";
    environment[index++] = "PYTHONHASHSEED=0";
    environment[index++] = "SUMMARY_MOVE_RELEARN_BOOTSTRAP_PROTOCOL=" PROTOCOL_VERSION;
    environment[index++] = ready_text;
    environment[index++] = go_text;
    environment[index++] = bootstrap_text;
    environment[index++] = self_sha_text;
    environment[index++] = inventory_text;
    environment[index++] = inventory_sha_text;
    environment[index] = NULL;
    execve(inventory->alias->path, command, environment);
    return -1;
}

static int supervise_child(Inventory *inventory, Options *options,
    const char *self_path, char **command, int queue) {
    int ready_pipe[2] = {-1, -1}, go_pipe[2] = {-1, -1};
    ChildState child = {0};
    int failed = 0, flags, setup_complete = 0;
    struct timespec delay = {0, 10000000};
    if (pipe(ready_pipe) != 0 || pipe(go_pipe) != 0)
        goto cleanup;
    flags = fcntl(ready_pipe[0], F_GETFL);
    if (flags < 0 || fcntl(ready_pipe[0], F_SETFL, flags | O_NONBLOCK) != 0)
        goto cleanup;
#ifdef F_SETNOSIGPIPE
    if (fcntl(go_pipe[1], F_SETNOSIGPIPE, 1) != 0)
        goto cleanup;
#else
#error "Darwin F_SETNOSIGPIPE is required"
#endif
    child.pid = fork();
    if (child.pid < 0)
        goto cleanup;
    if (child.pid == 0) {
        close(ready_pipe[0]);
        close(go_pipe[1]);
        if (child_exec(inventory, options, self_path, command,
                ready_pipe[1], go_pipe[0]) != 0)
            _exit(126);
    }
    child.owned = 1;
    setup_complete = 1;
    close(ready_pipe[1]);
    ready_pipe[1] = -1;
    close(go_pipe[0]);
    go_pipe[0] = -1;
    if (exact_read(ready_pipe[0], READY_MESSAGE,
            options->ready_timeout_seconds, queue, &child) != 0
        || !monitor_clean(queue)
        || reauthenticate_inventory(inventory) != 0
        || !monitor_clean(queue)
        || exact_write(go_pipe[1], GO_MESSAGE) != 0)
        failed = 1;
    close(ready_pipe[0]);
    ready_pipe[0] = -1;
    close(go_pipe[1]);
    go_pipe[1] = -1;
    if (failed) {
        if (terminate_and_reap(&child) != 0)
            failed = 1;
    } else {
        while (!child.terminal) {
            int polled = poll_child(&child);
            if (polled < 0 || child.stopped || !monitor_clean(queue)) {
                failed = 1;
                if (terminate_and_reap(&child) != 0)
                    failed = 1;
                break;
            }
            if (!child.terminal)
                (void)nanosleep(&delay, NULL);
        }
    }
    if (!monitor_clean(queue) || reauthenticate_inventory(inventory) != 0
        || !monitor_clean(queue))
        failed = 1;
    if (failed || !child.terminal || !WIFEXITED(child.status)
        || WEXITSTATUS(child.status) != 0) {
        errno = EAUTH;
        failed = 1;
    }

cleanup:
    if (ready_pipe[0] >= 0)
        close(ready_pipe[0]);
    if (ready_pipe[1] >= 0)
        close(ready_pipe[1]);
    if (go_pipe[0] >= 0)
        close(go_pipe[0]);
    if (go_pipe[1] >= 0)
        close(go_pipe[1]);
    if (child.owned && terminate_and_reap(&child) != 0)
        failed = 1;
    return setup_complete && !failed ? 0 : -1;
}

int main(int argc, char **argv) {
    Options options;
    ResultTargets result_targets = {0};
    Inventory inventory = {0};
    unsigned char *inventory_data = NULL;
    unsigned char actual_inventory_digest[32];
    unsigned char compiled_inventory_digest[32];
    unsigned char self_anchor_digest[32];
    uint64_t inventory_size;
    uint64_t self_anchor_size;
    struct stat inventory_metadata;
    struct stat self_metadata;
    char self_path[PATH_MAX];
    int self_fd = -1;
    int inventory_fd = -1, queue = -1;
    size_t index;
    int success = 0;
    int targets_valid;

    targets_valid = collect_result_targets(argc, argv, &result_targets) == 0;
    if (invalidate_results(&result_targets) != 0) {
        free(result_targets.paths);
        return 1;
    }
    if (!targets_valid) {
        fprintf(stderr, "native bootstrap: invalid arguments\n");
        free(result_targets.paths);
        return 2;
    }
    if (argc == 2 && strcmp(argv[1], "--self-test-event-backlog") == 0) {
        int self_test = event_backlog_self_test() == 0 ? 0 : 1;
        free(result_targets.paths);
        return self_test;
    }
    if (parse_options(argc, argv, &options) != 0) {
        fprintf(stderr, "native bootstrap: invalid arguments\n");
        free(result_targets.paths);
        return 2;
    }
    if (options.print_self_record) {
        int printed = self_record(NULL, 0, 1) == 0 ? 0 : 1;
        free(result_targets.paths);
        return printed;
    }
    if (parse_digest(compiled_inventory_sha256,
            compiled_inventory_digest) != 0
        || memcmp(compiled_inventory_digest, options.inventory_digest, 32) != 0) {
        fprintf(stderr, "native bootstrap: compiled inventory pin differs\n");
        goto cleanup;
    }
    if (self_record(options.self_digest, 1, 0) != 0
        || executable_path(self_path) != 0) {
        fprintf(stderr, "native bootstrap: externally pinned self differs\n");
        goto cleanup;
    }
    inventory_fd = canonical_regular_open(options.inventory_path,
        &inventory_metadata);
    if (inventory_fd < 0
        || digest_fd(inventory_fd, &inventory_size, actual_inventory_digest) != 0
        || memcmp(actual_inventory_digest, options.inventory_digest, 32) != 0
        || read_bounded_fd(inventory_fd, &inventory_data, &index) != 0
        || index != inventory_size
        || parse_inventory(inventory_data, index, &inventory) != 0) {
        fprintf(stderr, "native bootstrap: inventory authentication failed\n");
        goto cleanup;
    }
    self_fd = canonical_regular_open(self_path, &self_metadata);
    if (self_fd < 0
        || digest_fd(self_fd, &self_anchor_size, self_anchor_digest) != 0
        || memcmp(self_anchor_digest, options.self_digest, 32) != 0
        || append_anchor(&inventory, options.inventory_path, inventory_size,
            options.inventory_digest) != 0
        || append_anchor(&inventory, self_path, self_anchor_size,
            options.self_digest) != 0
        || require_descriptor_capacity(inventory.count) != 0
        || validate_parent_records(&inventory) != 0) {
        fprintf(stderr, "native bootstrap: trust-anchor retention failed\n");
        goto cleanup;
    }
    close(self_fd);
    self_fd = -1;
    for (index = 0; index < inventory.count; index++) {
        if (authenticate_record(&inventory.items[index]) != 0) {
            fprintf(stderr, "native bootstrap: closure differs: %s\n",
                inventory.items[index].path);
            goto cleanup;
        }
    }
    if (validate_exec_chain(&inventory) != 0) {
        fprintf(stderr, "native bootstrap: Python exec alias chain differs\n");
        goto cleanup;
    }
    if (validate_python_command(&inventory,
            &argv[options.command_index]) != 0) {
        fprintf(stderr, "native bootstrap: Python invocation policy differs\n");
        goto cleanup;
    }
    queue = kqueue();
    if (queue < 0 || register_monitors(queue, &inventory) != 0
        || reauthenticate_inventory(&inventory) != 0 || !monitor_clean(queue)) {
        fprintf(stderr, "native bootstrap: closure monitor setup failed\n");
        goto cleanup;
    }
    if (supervise_child(&inventory, &options, self_path,
            &argv[options.command_index], queue) != 0) {
        fprintf(stderr, "native bootstrap: authenticated child failed\n");
        goto cleanup;
    }
    success = 1;

cleanup:
    if (!success && invalidate_results(&result_targets) != 0)
        success = 0;
    if (queue >= 0)
        close(queue);
    if (inventory_fd >= 0)
        close(inventory_fd);
    if (self_fd >= 0)
        close(self_fd);
    for (index = 0; index < inventory.count; index++) {
        if (inventory.items[index].fd >= 0)
            close(inventory.items[index].fd);
        free(inventory.items[index].path);
    }
    free(inventory.items);
    free(inventory_data);
    free(result_targets.paths);
    return success ? 0 : 1;
}

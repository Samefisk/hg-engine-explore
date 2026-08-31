#include "../../../include/overworld_behavior_resolver.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HOST_TRACE_CAPACITY 96

extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;

static void print_usage(const char *program)
{
    fprintf(stderr,
        "usage: %s [--blob FILE] [--species N] [--level N] [--terrain N] "
        "[--shiny 0|1] [--groups MASK] [--condition-terrain-mask MASK] "
        "[--forced-override-mask MASK] [--behavior-class auto|N]\n",
        program);
}

static int parse_u32(const char *text, u32 *value)
{
    char *end = NULL;
    unsigned long parsed;

    errno = 0;
    parsed = strtoul(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0' || parsed > 0xFFFFFFFFul) {
        return 0;
    }
    *value = (u32)parsed;
    return 1;
}

static void print_hex(const void *bytes, size_t size)
{
    static const char digits[] = "0123456789abcdef";
    const unsigned char *cursor = (const unsigned char *)bytes;
    size_t i;

    for (i = 0; i < size; i++) {
        putchar(digits[cursor[i] >> 4]);
        putchar(digits[cursor[i] & 15]);
    }
}

static void *read_file(const char *path, u32 *sizeOut)
{
    FILE *file;
    long size;
    void *bytes;

    file = fopen(path, "rb");
    if (file == NULL) {
        return NULL;
    }
    if (fseek(file, 0, SEEK_END) != 0
        || (size = ftell(file)) < 0
        || size > 0xFFFFFFFFl
        || fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return NULL;
    }
    bytes = malloc(size == 0 ? 1u : (size_t)size);
    if (bytes == NULL
        || (size != 0 && fread(bytes, 1, (size_t)size, file) != (size_t)size)) {
        free(bytes);
        fclose(file);
        return NULL;
    }
    fclose(file);
    *sizeOut = (u32)size;
    return bytes;
}

int main(int argc, char **argv)
{
    const char *blobPath = NULL;
    BehaviorResolveRequest request;
    BehaviorResolveResult result;
    BehaviorResolutionStep traceSteps[HOST_TRACE_CAPACITY];
    BehaviorResolutionTrace trace;
    BehaviorResolveStatus status;
    const void *blobBytes;
    u32 blobSize;
    int ownsBlob = 0;
    int i;

    memset(&request, 0, sizeof(request));
    request.context.level = 1;
    request.context.terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    request.behaviorClass = BEHAVIOR_RESOLVER_CLASS_AUTO;
    for (i = 1; i < argc; i++) {
        const char *option = argv[i];
        const char *value;
        u32 parsed;

        if (i + 1 >= argc) {
            print_usage(argv[0]);
            return 2;
        }
        value = argv[++i];
        if (strcmp(option, "--blob") == 0) {
            blobPath = value;
            continue;
        }
        if (strcmp(option, "--behavior-class") == 0
            && strcmp(value, "auto") == 0) {
            request.behaviorClass = BEHAVIOR_RESOLVER_CLASS_AUTO;
            continue;
        }
        if (!parse_u32(value, &parsed)) {
            fprintf(stderr, "invalid value for %s: %s\n", option, value);
            return 2;
        }
        if (strcmp(option, "--species") == 0 && parsed <= 0xFFFFu) {
            request.context.species = (u16)parsed;
        } else if (strcmp(option, "--level") == 0 && parsed <= 0xFFu) {
            request.context.level = (u8)parsed;
        } else if (strcmp(option, "--terrain") == 0 && parsed <= 0xFFu) {
            request.context.terrain = (u8)parsed;
        } else if (strcmp(option, "--shiny") == 0 && parsed <= 0xFFu) {
            request.context.shiny = (u8)parsed;
        } else if (strcmp(option, "--groups") == 0) {
            request.context.groupFlags = parsed;
        } else if (strcmp(option, "--condition-terrain-mask") == 0
            && parsed <= 0xFFFFu) {
            request.context.conditionTerrainMask = (u16)parsed;
        } else if (strcmp(option, "--forced-override-mask") == 0) {
            request.forcedOverrideMask = parsed;
        } else if (strcmp(option, "--behavior-class") == 0
            && parsed <= 0xFFu) {
            request.behaviorClass = (u8)parsed;
        } else {
            fprintf(stderr, "unknown option or out-of-range value: %s %s\n",
                option, value);
            return 2;
        }
    }
    if (blobPath != NULL) {
        blobBytes = read_file(blobPath, &blobSize);
        if (blobBytes == NULL) {
            fprintf(stderr, "could not read behavior blob: %s\n", blobPath);
            return 2;
        }
        ownsBlob = 1;
    } else {
        blobBytes = &gOverworldWildBehaviorDataBlob;
        blobSize = sizeof(gOverworldWildBehaviorDataBlob);
    }
    trace.steps = traceSteps;
    trace.capacity = HOST_TRACE_CAPACITY;
    trace.count = 0;
    trace.dropped = 0;
    trace.reserved = 0;
    status = BehaviorResolver_Resolve(
        blobBytes,
        blobSize,
        &request,
        &result,
        &trace);
    if (ownsBlob) {
        free((void *)blobBytes);
    }

    printf("{\"status\":%u,\"behaviorClass\":%u,\"behaviorLimitKey\":%u,",
        (unsigned)status,
        (unsigned)result.behaviorClass,
        (unsigned)result.behaviorLimitKey);
    printf("\"speciesClassRuleIndex\":%u,\"matchedClassRuleMask\":%u,",
        (unsigned)result.speciesClassRuleIndex,
        (unsigned)result.matchedClassRuleMask);
    printf("\"matchedOverrideMask\":%u,\"forcedOverrideMask\":%u,",
        (unsigned)result.matchedOverrideMask,
        (unsigned)result.forcedOverrideMask);
    printf("\"conditionalOverrideMask\":%u,\"appliedOverrideMask\":%u,",
        (unsigned)result.conditionalOverrideMask,
        (unsigned)result.appliedOverrideMask);
    printf("\"fingerprint\":%u,\"profileHex\":\"",
        (unsigned)result.fingerprint);
    print_hex(&result.profile, sizeof(result.profile));
    printf("\",\"primitivesHex\":\"");
    print_hex(&result.primitives, sizeof(result.primitives));
    printf("\",\"traceDropped\":%u,\"trace\":[", (unsigned)trace.dropped);
    for (i = 0; i < trace.count; i++) {
        const BehaviorResolutionStep *step = &trace.steps[i];

        if (i != 0) {
            putchar(',');
        }
        printf("{\"sourceIndex\":%u,\"lane\":%u,\"kind\":%u,\"flags\":%u,"
               "\"profileHex\":\"",
            (unsigned)step->sourceIndex,
            (unsigned)step->lane,
            (unsigned)step->kind,
            (unsigned)step->flags);
        print_hex(&step->profile, sizeof(step->profile));
        printf("\"}");
    }
    printf("]}\n");
    return status == BEHAVIOR_RESOLVE_OK
            || status == BEHAVIOR_RESOLVE_TRACE_TRUNCATED
        ? 0
        : 1;
}

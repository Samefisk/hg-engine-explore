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
        "usage: %s [--blob FILE] [--batch] [--species N] [--level N] [--terrain N] "
        "[--shiny 0|1] [--groups MASK] [--condition-terrain-mask MASK] "
        "[--forced-override-mask MASK] [--behavior-class auto|N] "
        "[--condition-input legacy|explicit] [--active-conditional-mask MASK] "
        "[--target-kind N] [--target-actor-slot N] "
        "[--target-actor-generation N] [--target-field-epoch N] "
        "[--target-map-generation N] [--target-encounter-generation N] "
        "[--target-actor-reserved N] [--winning-condition-id N] "
        "[--target-source-application N] [--resolved-target-condition-id N]\n"
        "batch input: species level terrain shiny groups condition-mask "
        "forced-mask behavior-class active-conditional-mask condition-input "
        "target-kind target-slot target-generation field-epoch map-generation "
        "encounter-generation actor-reserved winning-condition-id "
        "target-source-application resolved-target-condition-id\n",
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

static int resolve_and_print(
    const void *blobBytes,
    u32 blobSize,
    const BehaviorResolveRequest *request)
{
    BehaviorResolveResult result;
    BehaviorResolutionStep traceSteps[HOST_TRACE_CAPACITY];
    BehaviorResolutionTrace trace;
    BehaviorResolveStatus status;
    int i;

    trace.steps = traceSteps;
    trace.capacity = HOST_TRACE_CAPACITY;
    trace.count = 0;
    trace.dropped = 0;
    trace.reserved = 0;
    status = BehaviorResolver_Resolve(
        blobBytes,
        blobSize,
        request,
        &result,
        &trace);

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
    printf("\",\"resolvedTarget\":{\"kind\":%u,\"actorSlot\":%u,"
           "\"actorGeneration\":%u,\"fieldEpoch\":%u,"
           "\"mapGeneration\":%u,\"encounterGeneration\":%u},",
        (unsigned)result.resolvedTarget.kind,
        (unsigned)result.resolvedTarget.actorSlot,
        (unsigned)result.resolvedTarget.actorGeneration,
        (unsigned)result.resolvedTarget.fieldEpoch,
        (unsigned)result.resolvedTarget.mapGeneration,
        (unsigned)result.resolvedTarget.encounterGeneration);
    printf("\"winningConditionId\":%u,\"targetSourceApplication\":%u,"
           "\"resolvedTargetConditionId\":%u,",
        (unsigned)result.winningConditionId,
        (unsigned)result.targetSourceApplication,
        (unsigned)result.resolvedTargetConditionId);
    printf("\"traceDropped\":%u,\"trace\":[", (unsigned)trace.dropped);
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

static int run_batch(const void *blobBytes, u32 blobSize)
{
    char line[512];
    int failed = 0;

    while (fgets(line, sizeof(line), stdin) != NULL) {
        unsigned long values[20];
        char extra;
        BehaviorResolveRequest request;
        int parsed;

        parsed = sscanf(line,
                "%lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu "
                "%lu %lu %lu %lu %lu %lu %lu %c",
                &values[0], &values[1], &values[2], &values[3],
                &values[4], &values[5], &values[6], &values[7],
                &values[8], &values[9], &values[10], &values[11],
                &values[12], &values[13], &values[14], &values[15],
                &values[16], &values[17], &values[18], &values[19], &extra);
        if ((parsed != 8 && parsed != 20)
            || values[0] > 0xFFFFul
            || values[1] > 0xFFul
            || values[2] > 0xFFul
            || values[3] > 0xFFul
            || values[4] > 0xFFFFFFFFul
            || values[5] > 0xFFFFul
            || values[6] > 0xFFFFFFFFul
            || values[7] > 0xFFul
            || (parsed == 20
                && (values[8] > 0xFFFFFFFFul
                    || values[9] > 0xFFul
                    || values[10] > 0xFFul
                    || values[11] > 0xFFFFul
                    || values[12] > 0xFFFFul
                    || values[13] > 0xFFFFul
                    || values[14] > 0xFFFFul
                    || values[15] > 0xFFFFul
                    || values[16] > 0xFFFFul
                    || values[17] > 0xFFFFul
                    || values[18] > 0xFFul
                    || values[19] > 0xFFFFul))) {
            fprintf(stderr, "invalid batch request: %s", line);
            return 2;
        }
        memset(&request, 0, sizeof(request));
        request.context.species = (u16)values[0];
        request.context.level = (u8)values[1];
        request.context.terrain = (u8)values[2];
        request.context.shiny = (u8)values[3];
        request.context.groupFlags = (u32)values[4];
        request.context.conditionTerrainMask = (u16)values[5];
        request.forcedOverrideMask = (u32)values[6];
        request.behaviorClass = (u8)values[7];
        if (parsed == 20) {
            request.activeConditionalMask = (u32)values[8];
            request.conditionInputMode = (u8)values[9];
            request.resolvedTarget.kind = (u8)values[10];
            request.resolvedTarget.actorSlot = (u16)values[11];
            request.resolvedTarget.actorGeneration = (u16)values[12];
            request.resolvedTarget.fieldEpoch = (u16)values[13];
            request.resolvedTarget.mapGeneration = (u16)values[14];
            request.resolvedTarget.encounterGeneration = (u16)values[15];
            request.resolvedTarget.actorReserved = (u16)values[16];
            request.winningConditionId = (u16)values[17];
            request.targetSourceApplication = (u8)values[18];
            request.resolvedTargetConditionId = (u16)values[19];
        }
        if (resolve_and_print(blobBytes, blobSize, &request) != 0) {
            failed = 1;
        }
    }
    if (ferror(stdin)) {
        fprintf(stderr, "could not read batch input\n");
        return 2;
    }
    return failed;
}

int main(int argc, char **argv)
{
    const char *blobPath = NULL;
    BehaviorResolveRequest request;
    const void *blobBytes;
    u32 blobSize;
    int ownsBlob = 0;
    int batch = 0;
    int resultCode;
    int i;

    memset(&request, 0, sizeof(request));
    request.context.level = 1;
    request.context.terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    request.behaviorClass = BEHAVIOR_RESOLVER_CLASS_AUTO;
    for (i = 1; i < argc; i++) {
        const char *option = argv[i];
        const char *value;
        u32 parsed;

        if (strcmp(option, "--batch") == 0) {
            batch = 1;
            continue;
        }
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
        if (strcmp(option, "--condition-input") == 0) {
            if (strcmp(value, "legacy") == 0) {
                request.conditionInputMode =
                    BEHAVIOR_RESOLVE_CONDITIONS_LEGACY;
            } else if (strcmp(value, "explicit") == 0) {
                request.conditionInputMode =
                    BEHAVIOR_RESOLVE_CONDITIONS_EXPLICIT;
            } else {
                fprintf(stderr, "invalid condition input: %s\n", value);
                return 2;
            }
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
        } else if (strcmp(option, "--active-conditional-mask") == 0) {
            request.activeConditionalMask = parsed;
        } else if (strcmp(option, "--target-kind") == 0
            && parsed <= 0xFFu) {
            request.resolvedTarget.kind = (u8)parsed;
        } else if (strcmp(option, "--target-actor-slot") == 0
            && parsed <= 0xFFFFu) {
            request.resolvedTarget.actorSlot = (u16)parsed;
        } else if (strcmp(option, "--target-actor-generation") == 0
            && parsed <= 0xFFFFu) {
            request.resolvedTarget.actorGeneration = (u16)parsed;
        } else if (strcmp(option, "--target-field-epoch") == 0
            && parsed <= 0xFFFFu) {
            request.resolvedTarget.fieldEpoch = (u16)parsed;
        } else if (strcmp(option, "--target-map-generation") == 0
            && parsed <= 0xFFFFu) {
            request.resolvedTarget.mapGeneration = (u16)parsed;
        } else if (strcmp(option, "--target-encounter-generation") == 0
            && parsed <= 0xFFFFu) {
            request.resolvedTarget.encounterGeneration = (u16)parsed;
        } else if (strcmp(option, "--target-actor-reserved") == 0
            && parsed <= 0xFFFFu) {
            request.resolvedTarget.actorReserved = (u16)parsed;
        } else if (strcmp(option, "--winning-condition-id") == 0
            && parsed <= 0xFFFFu) {
            request.winningConditionId = (u16)parsed;
        } else if (strcmp(option, "--target-source-application") == 0
            && parsed <= 0xFFu) {
            request.targetSourceApplication = (u8)parsed;
        } else if (strcmp(option, "--resolved-target-condition-id") == 0
            && parsed <= 0xFFFFu) {
            request.resolvedTargetConditionId = (u16)parsed;
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
    resultCode = batch
        ? run_batch(blobBytes, blobSize)
        : resolve_and_print(blobBytes, blobSize, &request);
    if (ownsBlob) {
        free((void *)blobBytes);
    }
    return resultCode;
}

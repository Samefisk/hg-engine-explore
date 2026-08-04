#include <stdint.h>
#define TYPES_H
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int8_t s8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0

#include "../include/overworld_wild_behavior_data.h"
#define OWBD_VALIDATION_TEST_ALLOW_DYNAMIC_CHECKSUM
#define OWBD_VALIDATION_ENABLE_BASELINE_ASSERTIONS
#include "overworld_wild_behavior_v40_validation_shared.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct OwbdMemoryReader { const u8 *data; u32 size; } OwbdMemoryReader;

static BOOL OwbdMemoryRead(void *context, u32 offset, u32 size, void *dest)
{
    OwbdMemoryReader *reader = context;
    u8 *out = dest;
    u32 i;
    if (offset > reader->size || size > reader->size - offset) return FALSE;
    for (i = 0; i < size; i++) out[i] = reader->data[offset + i];
    return TRUE;
}

static int OwbdApplyOperatorForConformance(
    int kind, int field, int operatorKind, int before, int delta, int bound)
{
    static const u8 stateMax[28] = {
        11, 7, 9, 4, 64, 2, 15, 15, 1, 12, 12, 255, 64, 15,
        64, 255, 32, 255, 32, 4, 8, 1, 1, 2, 32, 255, 2, 15,
    };
    static const u8 controllerMax[8] = { 0, 2, 255, 64, 64, 5, 100, 64 };
    static const u8 spawnMax[6] = { 0, 3, 16, 8, 8, 64 };
    int minimum, maximum, added;
    if (kind == 4 && field >= 1 && field <= 27 && field != 22) {
        minimum = field == 3;
        maximum = stateMax[field];
    } else if (kind == 5 && field >= 1 && field <= 7) {
        minimum = 0; maximum = controllerMax[field];
    } else if (kind == 7 && field >= 1 && field <= 5) {
        minimum = field == 3 || field == 4; maximum = spawnMax[field];
    } else if (kind == 9 && field == 1) {
        minimum = 0; maximum = 10;
    } else if (kind == 11 && field == 1) {
        if (bound != 0 || before < 0 || before > 255) return -1;
        if (operatorKind == OWBD_CANDIDATE_TIMER_SET)
            return delta >= 0 && delta <= 255 ? delta : -1;
        if (operatorKind != OWBD_CANDIDATE_TIMER_ADD || delta < -32 || delta > 32) return -1;
        added = before + delta;
        if (added < 0) added = 0;
        return added > 64 ? 64 : added;
    } else return -1;
    if (!OwbdModifierPayloadValid((u8)kind, (u8)field, (u8)operatorKind, (s8)delta, (u8)bound)
        || !OwbdStaticValueValid((u8)kind, (u8)field, (u8)before)) return -1;
    added = before + delta;
    if (added < minimum) added = minimum;
    if (added > maximum) added = maximum;
    switch (operatorKind) {
    case 1: return delta & 0xFF;
    case 2: return added;
    case 3: return before > (delta & 0xFF) ? before : delta & 0xFF;
    case 4: return before < (delta & 0xFF) ? before : delta & 0xFF;
    case 5: return added > bound ? added : bound;
    case 6: return added < bound ? added : bound;
    default: return -1;
    }
}

int main(int argc, char **argv)
{
    FILE *file;
    u8 *data, *workspace;
    long size;
    BOOL valid;
    BOOL baseline = FALSE;
    OwbdMemoryReader reader;
    if (argc == 8 && !strcmp(argv[1], "--operator")) {
        int result = OwbdApplyOperatorForConformance(
            atoi(argv[2]), atoi(argv[3]), atoi(argv[4]), atoi(argv[5]),
            atoi(argv[6]), atoi(argv[7]));
        if (result < 0) return 2;
        printf("%d\n", result);
        return 0;
    }
    if (argc == 3 && !strcmp(argv[1], "--baseline")) {
        baseline = TRUE;
        argv++;
        argc--;
    }
    if (argc != 2 || (file = fopen(argv[1], "rb")) == NULL) return 2;
    fseek(file, 0, SEEK_END); size = ftell(file); rewind(file);
    data = malloc((size_t)size);
    workspace = malloc(OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE);
    if (!data || !workspace || fread(data, 1, (size_t)size, file) != (size_t)size) return 2;
    fclose(file); reader.data = data; reader.size = (u32)size;
    valid = baseline
        ? OwbdValidateBaselineStream(OwbdMemoryRead, &reader, (u32)size,
            workspace, OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE)
        : OwbdValidateStream(OwbdMemoryRead, &reader, (u32)size, workspace,
            OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE);
    free(workspace); free(data);
    return valid ? 0 : 1;
}

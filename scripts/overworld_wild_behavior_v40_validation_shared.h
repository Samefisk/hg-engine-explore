#ifndef OVERWORLD_WILD_BEHAVIOR_V40_VALIDATION_SHARED_H
#define OVERWORLD_WILD_BEHAVIOR_V40_VALIDATION_SHARED_H

typedef BOOL (*OwbdReadCallback)(void *context, u32 offset, u32 size, void *dest);

typedef struct OwbdSectionSpec {
    u8 stride;
    u8 count;
} OwbdSectionSpec;

#if defined(OWBD_VALIDATION_DEFINE_RESIDENT_HELPERS)
#define OWBD_RESIDENT_DATA __attribute__((section(".owbd_resident_tables"), used))
#define OWBD_RESIDENT_CODE __attribute__((section(".owbd_resident_helpers"), noinline, used))
#elif defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
#define OWBD_RESIDENT_DATA extern
#define OWBD_RESIDENT_CODE extern
#else
#define OWBD_RESIDENT_DATA static
#define OWBD_RESIDENT_CODE static
#endif

#define OwbdOwnerValid(id) ((u16)((id) - 0x8102u) < OWBD_OWNER_COUNT)

enum {
    OWBD_S_BODY, OWBD_S_IDENTITY, OWBD_S_CONTROLLER, OWBD_S_NODE,
    OWBD_S_CLASS_PROFILE, OWBD_S_GENERIC_ASSIGN, OWBD_S_SPECIES_ASSIGN,
    OWBD_S_OVERRIDE, OWBD_S_MEMBER, OWBD_S_OVERRIDE_ACTION,
    OWBD_S_SPAWN, OWBD_S_POPULATION, OWBD_S_HOOK, OWBD_S_OWNER,
    OWBD_S_DEFINITION, OWBD_S_TRANSITION, OWBD_S_GUARD, OWBD_S_OPERATION,
    OWBD_S_TRANSITION_ACTION, OWBD_S_RECOVERY, OWBD_S_IMPORT,
    OWBD_S_APPLICABILITY, OWBD_S_TIRED_TRANSLATION, OWBD_S_SEMANTIC_ID,
    OWBD_S_COUNT
};

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
extern const OwbdSectionSpec sOwbdSpecs[OWBD_S_COUNT];
#else
OWBD_RESIDENT_DATA const OwbdSectionSpec sOwbdSpecs[OWBD_S_COUNT] = {
    { 32, OWBD_STATE_BODY_COUNT }, { 8, OWBD_PROFILE_IDENTITY_COUNT },
    { 24, OWBD_CONTROLLER_COUNT }, { 12, OWBD_CONTROLLER_NODE_COUNT },
    { 72, OWBD_CLASS_PROFILE_COUNT }, { 20, OWBD_CLASS_RULE_COUNT },
    { 8, OWBD_SPECIES_CLASS_RULE_COUNT }, { 28, OWBD_OVERRIDE_SOURCE_COUNT },
    { 2, OWBD_OVERRIDE_MEMBER_COUNT }, { 12, OWBD_OVERRIDE_ACTION_COUNT },
    { 12, OWBD_SPAWN_POLICY_COUNT }, { 10, OWBD_POPULATION_POLICY_COUNT },
    { 8, OWBD_HOOK_SET_COUNT }, { 6, OWBD_OWNER_COUNT },
    { 36, OWBD_OVERRIDE_DEFINITION_COUNT }, { 24, OWBD_TRANSITION_COUNT },
    { 12, OWBD_TRANSITION_GUARD_COUNT }, { 18, OWBD_TRANSITION_OPERATION_COUNT },
    { 10, OWBD_TRANSITION_ACTION_COUNT }, { 8, OWBD_RECOVERY_ACTION_COUNT },
    { 24, OWBD_IMPORT_RECIPE_COUNT }, { 16, OWBD_APPLICABILITY_COUNT },
    { 24, OWBD_TIRED_TRANSLATION_COUNT }, { 8, OWBD_SEMANTIC_ID_COUNT },
};
#endif

#define OWBD_SHARED_ID_COUNT 740u
#define OWBD_SHARED_CRC_CHUNK 256u

typedef struct OwbdSharedContext {
    OwbdReadCallback read;
    void *readContext;
    u32 size;
    u8 header[216];
    u16 *ids;
    u16 idBase[OWBD_S_COUNT];
} OwbdSharedContext;

static u16 OwbdLe16(const u8 *p) { return (u16)(p[0] | ((u16)p[1] << 8)); }
static u32 OwbdLe32(const u8 *p) { return (u32)OwbdLe16(p) | ((u32)OwbdLe16(p + 2) << 16); }

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
u32 OwbdCrcByte(u32 crc, u8 value);
#elif !defined(OWBD_VALIDATION_EXTERNAL_INTEGRITY)
OWBD_RESIDENT_CODE u32 OwbdCrcByte(u32 crc, u8 value)
{
    int bit;
    crc ^= value;
    for (bit = 0; bit < 8; bit++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    return crc;
}
#endif

static const u8 *OwbdDesc(const OwbdSharedContext *ctx, int section)
{
    return ctx->header + 24 + section * 8;
}

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
BOOL OwbdBoundedRead(const OwbdSharedContext *ctx, u32 offset, u32 size, void *dest);
#else
OWBD_RESIDENT_CODE BOOL OwbdBoundedRead(const OwbdSharedContext *ctx, u32 offset, u32 size, void *dest)
{
    return offset <= ctx->size && size <= ctx->size - offset
        && ctx->read(ctx->readContext, offset, size, dest);
}
#endif

static BOOL OwbdReadRecord(const OwbdSharedContext *ctx, int section, int index, u8 *record)
{
    const u8 *d = OwbdDesc(ctx, section);
    u16 count = OwbdLe16(d + 4), stride = OwbdLe16(d + 6);
    if (index < 0 || index >= count) return FALSE;
    return OwbdBoundedRead(ctx, OwbdLe32(d) + (u32)index * stride, stride, record);
}

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
BOOL OwbdHasId(const OwbdSharedContext *ctx, int section, u16 id);
#else
OWBD_RESIDENT_CODE BOOL OwbdHasId(const OwbdSharedContext *ctx, int section, u16 id)
{
    int i;
    if (!id || section < 0 || section >= OWBD_S_COUNT
        || section == OWBD_S_CLASS_PROFILE || section == OWBD_S_MEMBER) return FALSE;
    for (i = 0; i < sOwbdSpecs[section].count; i++)
        if (ctx->ids[ctx->idBase[section] + i] == id) return TRUE;
    return FALSE;
}
#endif

static BOOL OwbdReferenceOwner(u16 *references, u16 owner)
{
    if (!OwbdOwnerValid(owner)) return FALSE;
    *references |= 1u << (owner - 0x8102);
    return TRUE;
}

static BOOL OwbdSemanticIdMatches(const OwbdSharedContext *ctx, u16 id, u8 kind, u8 ordinal)
{
    int i;
    for (i = 0; i < OWBD_SEMANTIC_ID_COUNT; i++) {
        u8 r[8];
        if (!OwbdReadRecord(ctx, OWBD_S_SEMANTIC_ID, i, r)) return FALSE;
        if (OwbdLe16(r) == id) return r[2] == kind && (!ordinal || r[3] == ordinal);
    }
    return FALSE;
}

#define OwbdSemanticIdHasKind(ctx, id, kind) OwbdSemanticIdMatches(ctx, id, kind, 0)

static BOOL OwbdIdentityHasRole(const OwbdSharedContext *ctx, u16 id, u8 role, BOOL requireStateKind)
{
    int i, j;
    for (i = 0; i < OWBD_PROFILE_IDENTITY_COUNT; i++) {
        u8 q[8]; if (!OwbdReadRecord(ctx, OWBD_S_IDENTITY, i, q)) return FALSE;
        if (OwbdLe16(q) == id && OwbdSemanticIdMatches(ctx, OwbdLe16(q + 4), 1, role))
            for (j = 0; j < OWBD_STATE_BODY_COUNT; j++) {
                u8 b[32]; if (!OwbdReadRecord(ctx, OWBD_S_BODY, j, b)) return FALSE;
                if (OwbdLe16(b) == OwbdLe16(q + 2))
                    return b[2] == role && (!requireStateKind || b[4] != 0);
            }
    }
    return FALSE;
}

#ifndef OWBD_VALIDATION_EXTERNAL_INTEGRITY
static BOOL OwbdChecksum(OwbdSharedContext *ctx, u8 *buffer)
{
    u32 crc = ~0u, offset = 0;
    while (offset < ctx->size) {
        u32 count = ctx->size - offset, i;
        if (count > OWBD_SHARED_CRC_CHUNK) count = OWBD_SHARED_CRC_CHUNK;
        if (!OwbdBoundedRead(ctx, offset, count, buffer)) return FALSE;
        for (i = 0; i < count; i++) {
            u32 value = offset + i >= 16 && offset + i < 20 ? 0 : buffer[i];
            crc = OwbdCrcByte(crc, value);
        }
        offset += count;
    }
    return ~crc == OwbdLe32(ctx->header + 16);
}
#endif

static BOOL OwbdLoadStableIds(OwbdSharedContext *ctx)
{
    u16 cursor = 0;
    int section;
    for (section = 0; section < OWBD_S_COUNT; section++) {
        int i, prior;
        ctx->idBase[section] = cursor;
        if (section == OWBD_S_CLASS_PROFILE || section == OWBD_S_MEMBER) continue;
        for (i = 0; i < sOwbdSpecs[section].count; i++) {
            u8 record[72];
            u16 id;
            if (!OwbdReadRecord(ctx, section, i, record) || !(id = OwbdLe16(record))) return FALSE;
            for (prior = 0; prior < cursor; prior++) if (ctx->ids[prior] == id) return FALSE;
            ctx->ids[cursor++] = id;
        }
    }
    return cursor == OWBD_SHARED_ID_COUNT;
}

static BOOL OwbdMatchValid(const u8 *match)
{
    u8 terrain = match[6], minimum = match[7], maximum = match[8];
    return (terrain <= 3 || terrain == 0xFF) && (minimum == 0 || maximum == 0 || minimum <= maximum)
        && (match[9] == 0 || match[9] == 1 || match[9] == 0xFF)
        && (match[10] <= 3 || match[10] == 0xFD || match[10] == 0xFF) && match[11] == 0;
}

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
extern const u8 sOwbdStateValueMax[28];
extern const u32 sOwbdNumericFieldMasks[4];
#else
OWBD_RESIDENT_DATA const u8 sOwbdStateValueMax[28] = {
    11, 7, 9, 4, 64, 2, 15, 15, 1, 12, 12, 255, 64, 15,
    64, 255, 32, 255, 32, 4, 8, 1, 1, 2, 32, 255, 2, 15
};
OWBD_RESIDENT_DATA const u32 sOwbdNumericFieldMasks[4] = { 0x031FFE18, 0x000000D8, 0x00000038, 0x00000002 };
#endif

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
extern const u8 sOwbdGroupOrdinals[6];
extern const u16 sOwbdImportExpectedOwner[3];
extern const u16 sOwbdImportExpectedRecovery[3];
extern const u16 sOwbdImportExpectedSource[3];
extern const u8 sOwbdImportExpectedRole[3];
extern const u8 sOwbdImportExpectedLifetime[3];
extern const u16 sOwbdOverrideProvenance[3];
#else
OWBD_RESIDENT_DATA const u8 sOwbdGroupOrdinals[6] = { 1, 2, 3, 6, 7, 11 };
OWBD_RESIDENT_DATA const u16 sOwbdImportExpectedOwner[3] = { 0x8109, 0x810B, 0x810A };
OWBD_RESIDENT_DATA const u16 sOwbdImportExpectedRecovery[3] = { 0, 0xA011, 0xA00F };
OWBD_RESIDENT_DATA const u16 sOwbdImportExpectedSource[3] = { 0, 0x500B, 0x500A };
OWBD_RESIDENT_DATA const u8 sOwbdImportExpectedRole[3] = { 5, 6, 4 };
OWBD_RESIDENT_DATA const u8 sOwbdImportExpectedLifetime[3] = { 1, 3, 2 };
OWBD_RESIDENT_DATA const u16 sOwbdOverrideProvenance[3] = { 0x5002, 0x5003, 0x5007 };
#endif

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
BOOL OwbdStaticValueValid(u8 kind, u8 field, u8 value);
#else
OWBD_RESIDENT_CODE BOOL OwbdStaticValueValid(u8 kind, u8 field, u8 value);
#endif

static BOOL OwbdStateValuesValid(const u8 *v)
{
    int i;
    if (v[0] > 11 || v[0] == 9 || v[9] > v[10]) return FALSE;
    for (i = 1; i < 28; i++) if (!OwbdStaticValueValid(4, i, v[i])) return FALSE;
    return TRUE;
}

#define OWBD_NODE_MATCH_TIRED_CANDIDATE (~(u32)0)
static BOOL OwbdNodeBindingMatches(const OwbdSharedContext *ctx, u16 controller, u16 node, u32 selector)
{
    u16 profile = (u16)selector;
    int i;
    for (i = 0; i < OWBD_CONTROLLER_NODE_COUNT; i++) {
        u8 r[12];
        if (!OwbdReadRecord(ctx, OWBD_S_NODE, i, r)) return FALSE;
        if (OwbdLe16(r) == node) {
            if (OwbdLe16(r + 2) != controller) return FALSE;
            if (selector == OWBD_NODE_MATCH_TIRED_CANDIDATE)
                return r[8] == OWBD_ROLE_TIRED && !(r[9] & OWBD_NODE_FLAG_BASE);
            if (!profile) return !(r[9] & 1);
            return OwbdIdentityHasRole(ctx, profile, r[8], TRUE);
        }
    }
    return FALSE;
}

#if !defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
OWBD_RESIDENT_CODE BOOL OwbdStaticValueValid(u8 kind, u8 field, u8 value)
{
    if (kind == 5) {
        if (field == 1) return value <= 2;
        if (field == 2) return value <= 10 || value == 0xFF;
        if (field == 3 || field == 7) return value <= 64;
        if (field == 4) return value <= 64;
        if (field == 5) return value <= 5;
        return value <= 100;
    }
    if (kind == 7) return field == 1 ? value <= 3 : field == 2 ? value <= 16
        : field == 3 || field == 4 ? value >= 1 && value <= 8 : value <= 64;
    if (kind == 9) return value <= 10;
    if (field == 2 && value == 7) value = 0xFF;
    if ((u8)(field - 6) <= 1 && value > 5 && value < 15) value = 0xFF;
    return field >= 1 && field <= 27 && value <= sOwbdStateValueMax[field];
}
#endif

#if defined(OWBD_VALIDATION_USE_RESIDENT_HELPERS)
BOOL OwbdModifierPayloadValid(u8 kind, u8 field, u8 op, s8 delta, u8 bound);
#else
OWBD_RESIDENT_CODE BOOL OwbdModifierPayloadValid(u8 kind, u8 field, u8 op, s8 delta, u8 bound)
{
    int index = kind == 4 ? 0 : kind == 5 ? 1 : kind == 7 ? 2 : kind == 9 ? 3 : -1;
    BOOL numeric;
    if (index < 0 || field == 0 || field >= 32 || op < 1 || op > 6) return FALSE;
    numeric = (sOwbdNumericFieldMasks[index] & (1u << field)) != 0;
    if (!numeric && op != OWBD_OPERATOR_SET) return FALSE;
    if (op < OWBD_OPERATOR_ADD_AT_LEAST && bound) return FALSE;
    if (op == OWBD_OPERATOR_ADD || op >= OWBD_OPERATOR_ADD_AT_LEAST) {
        if (delta < -32 || delta > 32) return FALSE;
    } else if (!OwbdStaticValueValid(kind, field, (u8)delta)) return FALSE;
    return op < OWBD_OPERATOR_ADD_AT_LEAST || OwbdStaticValueValid(kind, field, bound);
}
#endif

static BOOL OwbdStaticActionValid(const OwbdSharedContext *ctx, const u8 *a, BOOL assignment)
{
    u8 kind = a[2], field = a[4], op = a[5], bound = a[7], roleMask = a[8];
    u16 reference = OwbdLe16(a + 4), controller = OwbdLe16(a + 10);
    int delta = (signed char)a[6];
    if (a[3] || kind < 1 || kind > 11) return FALSE;
    if (assignment) return kind == 1 && OwbdHasId(ctx, OWBD_S_CONTROLLER, reference)
        && !OwbdLe16(a + 6) && !OwbdLe16(a + 8) && !OwbdLe16(a + 10);
    switch (kind) {
    case 2:
        return OwbdHasId(ctx, OWBD_S_CONTROLLER, reference)
            && OwbdNodeBindingMatches(ctx, reference, OwbdLe16(a + 6), OwbdLe16(a + 8))
            && !OwbdLe16(a + 10);
    case 3:
        return OwbdHasId(ctx, OWBD_S_CONTROLLER, reference)
            && OwbdNodeBindingMatches(ctx, reference, OwbdLe16(a + 6), 0)
            && !OwbdLe16(a + 8) && !OwbdLe16(a + 10);
    case 4:
        return field >= 1 && field <= 27 && field != 22
            && !a[9] && roleMask && !(roleMask & ~7)
            && (!controller || OwbdHasId(ctx, OWBD_S_CONTROLLER, controller))
            && OwbdModifierPayloadValid(kind, field, op, (s8)delta, bound);
    case 5:
        return field >= 1 && field <= 7 && !a[9] && !roleMask && !controller
            && OwbdModifierPayloadValid(kind, field, op, (s8)delta, bound);
    case 6: case 8: case 10:
        return ((kind == 6 && OwbdHasId(ctx, OWBD_S_SPAWN, reference))
            || (kind == 8 && OwbdHasId(ctx, OWBD_S_POPULATION, reference))
            || (kind == 10 && OwbdHasId(ctx, OWBD_S_HOOK, reference)))
            && !OwbdLe16(a + 6) && !OwbdLe16(a + 8) && !OwbdLe16(a + 10);
    case 7:
        return field >= 1 && field <= 5 && !a[9] && !roleMask && !controller
            && OwbdModifierPayloadValid(kind, field, op, (s8)delta, bound);
    case 9:
        return field == 1 && !roleMask && !controller && !a[9]
            && OwbdModifierPayloadValid(kind, field, op, (s8)delta, bound);
    case 11:
        return OwbdHasId(ctx, OWBD_S_CONTROLLER, reference)
            && OwbdNodeBindingMatches(ctx, reference, OwbdLe16(a + 6),
                                      OWBD_NODE_MATCH_TIRED_CANDIDATE)
            && (a[8] == OWBD_CANDIDATE_TIMER_SET
                || (a[8] == OWBD_CANDIDATE_TIMER_ADD
                    && (s8)a[9] >= OWBD_CANDIDATE_TIMER_ADD_MIN
                    && (s8)a[9] <= OWBD_CANDIDATE_TIMER_ADD_MAX))
            && !OwbdLe16(a + 10);
    default:
        return FALSE;
    }
}

static BOOL OwbdValidateRecords(OwbdSharedContext *ctx)
{
    int i, j;
    u16 cursor, ownerReferences = 0;
    for (i = 0; i < OWBD_SEMANTIC_ID_COUNT; i++) {
        u8 r[8]; u8 kind = i < 7 ? 1 : i < 10 ? 2 : 3;
        u8 ordinal = i < 7 ? i + 1 : i < 10 ? i - 6 : sOwbdGroupOrdinals[i - 10];
        if (!OwbdReadRecord(ctx, OWBD_S_SEMANTIC_ID, i, r) || r[2] != kind
            || r[3] != ordinal || OwbdLe16(r + 4) || OwbdLe16(r + 6)) return FALSE;
    }
    for (i = 0; i < OWBD_STATE_BODY_COUNT; i++) {
        u8 r[32];
        if (!OwbdReadRecord(ctx, OWBD_S_BODY, i, r) || r[2] < 1 || r[2] > 7 || r[3] != 28
            || !OwbdStateValuesValid(r + 4)
            || r[26] != (r[2] == 2 && r[4] == 3 && r[6] != 1)) return FALSE;
    }
    for (i = 0; i < OWBD_PROFILE_IDENTITY_COUNT; i++) {
        u8 r[8]; int k; u8 bodyRole = 0;
        if (!OwbdReadRecord(ctx, OWBD_S_IDENTITY, i, r) || !OwbdHasId(ctx, OWBD_S_BODY, OwbdLe16(r + 2))
            || !OwbdSemanticIdHasKind(ctx, OwbdLe16(r + 4), 1)) return FALSE;
        for (k = 0; k < OWBD_STATE_BODY_COUNT; k++) { u8 b[32]; if (!OwbdReadRecord(ctx, OWBD_S_BODY, k, b)) return FALSE; if (OwbdLe16(b) == OwbdLe16(r + 2)) bodyRole = b[2]; }
        if (!OwbdSemanticIdMatches(ctx, OwbdLe16(r + 4), 1, bodyRole)) return FALSE;
        if (r[6] > 15 || r[7] > OWBD_CONTROLLER_COUNT
            || ((r[6] == 0 || r[6] == 14) != (r[7] == 0))) return FALSE;
    }
    cursor = 0;
    for (i = 0; i < OWBD_CONTROLLER_COUNT; i++) {
        u8 r[24]; u16 controller, count; int baseCount = 0;
        if (!OwbdReadRecord(ctx, OWBD_S_CONTROLLER, i, r) || OwbdLe16(r + 2) != OwbdLe16(r)
            || OwbdLe16(r + 4) != cursor
            || !(count = OwbdLe16(r + 6)) || count > OWBD_CONTROLLER_NODE_COUNT - cursor
            || !OwbdHasId(ctx, OWBD_S_SPAWN, OwbdLe16(r + 8))
            || !OwbdHasId(ctx, OWBD_S_POPULATION, OwbdLe16(r + 10))
            || !OwbdHasId(ctx, OWBD_S_HOOK, OwbdLe16(r + 12)) || r[22] || r[23]) return FALSE;
        for (j = 1; j <= 7; j++) if (!OwbdStaticValueValid(5, j, r[13 + j])) return FALSE;
        controller = OwbdLe16(r);
        for (j = 0; j < count; j++) {
            u8 n[12]; int k;
            if (!OwbdReadRecord(ctx, OWBD_S_NODE, cursor + j, n) || OwbdLe16(n + 2) != controller
                || !OwbdHasId(ctx, OWBD_S_IDENTITY, OwbdLe16(n + 4)) || n[8] < 1 || n[8] > 7
                || (n[9] & ~7) || OwbdLe16(n + 10)
                || n[9] != (n[8] == 1 ? 1 : n[8] == 2 || n[8] == 3 ? 0 : n[8] == 7 ? 6 : 2)
                || ((n[8] == 7) != OwbdSemanticIdHasKind(ctx, OwbdLe16(n + 6), 2))) return FALSE;
            if (!OwbdIdentityHasRole(ctx, OwbdLe16(n + 4), n[8], TRUE)) return FALSE;
            if (n[8] >= 4) {
                u16 expectedProfile = n[8] == 5 ? 0x220A
                    : n[8] == 7 ? 0x2210 + i
                    : i == 0 ? (n[8] == 4 ? 0x220C : 0x220B)
                    : 0x2250 + (i - 1) * 2 + (n[8] == 4);
                if (OwbdLe16(n + 4) != expectedProfile) return FALSE;
            }
            if (n[9] & 1) { if (n[8] != 1 || n[9] != 1) return FALSE; baseCount++; }
            for (k = 0; k < j; k++) { u8 p[12]; if (!OwbdReadRecord(ctx, OWBD_S_NODE, cursor + k, p) || p[8] == n[8]) return FALSE; }
        }
        if (baseCount != 1) return FALSE;
        cursor += count;
    }
    if (cursor != OWBD_CONTROLLER_NODE_COUNT) return FALSE;
    for (i = 0; i < OWBD_CLASS_PROFILE_COUNT; i++) {
        u8 r[72];
        if (!OwbdReadRecord(ctx, OWBD_S_CLASS_PROFILE, i, r)
            || r[9] < 1 || r[9] > 4 || r[10] < 1 || r[10] > 4 || r[11] < 1 || r[11] > 4) return FALSE;
    }
    for (i = 0; i < OWBD_CLASS_RULE_COUNT; i++) {
        u8 r[20], a[12];
        if (!OwbdReadRecord(ctx, OWBD_S_GENERIC_ASSIGN, i, r) || !OwbdMatchValid(r + 2)
            || OwbdLe16(r + 14) >= 3 || OwbdLe16(r + 16) != 0x1001 + i
            || OwbdLe16(r + 18)
            || !OwbdReadRecord(ctx, OWBD_S_OVERRIDE_ACTION, OwbdLe16(r + 14), a)
            || !OwbdStaticActionValid(ctx, a, TRUE)) return FALSE;
    }
    for (i = 0; i < OWBD_SPECIES_CLASS_RULE_COUNT; i++) {
        u8 r[8], a[12];
        if (!OwbdReadRecord(ctx, OWBD_S_SPECIES_ASSIGN, i, r) || !OwbdLe16(r + 2)
            || OwbdLe16(r + 4) >= 3 || OwbdLe16(r + 6) != 0x2003 + i
            || !OwbdReadRecord(ctx, OWBD_S_OVERRIDE_ACTION, OwbdLe16(r + 4), a)
            || !OwbdStaticActionValid(ctx, a, TRUE)) return FALSE;
        for (j = 0; j < i; j++) { u8 p[8]; if (!OwbdReadRecord(ctx, OWBD_S_SPECIES_ASSIGN, j, p) || OwbdLe16(p + 2) == OwbdLe16(r + 2)) return FALSE; }
    }
    {
        u16 memberCursor = 0, actionCursor = 3;
        for (i = 0; i < OWBD_OVERRIDE_SOURCE_COUNT; i++) {
            u8 r[28]; u16 memberCount, actionCount;
            if (!OwbdReadRecord(ctx, OWBD_S_OVERRIDE, i, r) || OwbdLe16(r + 2) != OwbdLe16(r)
                || !OwbdMatchValid(r + 4)
                || OwbdLe16(r + 16) != memberCursor || OwbdLe16(r + 20) != actionCursor
                || r[24] > 2 || r[25] != i + 1 || OwbdLe16(r + 26) != 0x4000 + i) return FALSE;
            memberCount = OwbdLe16(r + 18); actionCount = OwbdLe16(r + 22);
            if (memberCount > OWBD_OVERRIDE_MEMBER_COUNT - memberCursor
                || actionCount > OWBD_OVERRIDE_ACTION_COUNT - actionCursor
                || (r[24] == 1 && !memberCount)) return FALSE;
            for (j = 0; j < memberCount; j++) {
                u8 m[2]; int prior;
                if (!OwbdReadRecord(ctx, OWBD_S_MEMBER, memberCursor + j, m) || !OwbdLe16(m)) return FALSE;
                for (prior = 0; prior < j; prior++) { u8 p[2]; if (!OwbdReadRecord(ctx, OWBD_S_MEMBER, memberCursor + prior, p) || OwbdLe16(p) == OwbdLe16(m)) return FALSE; }
            }
            for (j = 0; j < actionCount; j++) {
                u8 a[12];
                if (!OwbdReadRecord(ctx, OWBD_S_OVERRIDE_ACTION, actionCursor + j, a)
                    || !OwbdStaticActionValid(ctx, a, FALSE)) return FALSE;
            }
            memberCursor += memberCount; actionCursor += actionCount;
        }
        if (memberCursor != OWBD_OVERRIDE_MEMBER_COUNT || actionCursor != OWBD_OVERRIDE_ACTION_COUNT) return FALSE;
    }
    for (i = 0; i < OWBD_SPAWN_POLICY_COUNT; i++) {
        u8 r[12];
        if (!OwbdReadRecord(ctx, OWBD_S_SPAWN, i, r) || OwbdLe16(r + 2) != OwbdLe16(r)
            || !OwbdSemanticIdHasKind(ctx, OwbdLe16(r + 4), 1) || r[8] > r[9] || r[11]) return FALSE;
        for (j = 1; j <= 5; j++) if (!OwbdStaticValueValid(7, j, r[5 + j])) return FALSE;
    }
    for (i = 0; i < OWBD_POPULATION_POLICY_COUNT; i++) {
        u8 r[10];
        if (!OwbdReadRecord(ctx, OWBD_S_POPULATION, i, r) || OwbdLe16(r + 2) != OwbdLe16(r)
            || !OwbdSemanticIdMatches(ctx, OwbdLe16(r + 4), 3, sOwbdGroupOrdinals[i])
            || (i < 3 ? !OwbdSemanticIdMatches(ctx, OwbdLe16(r + 6), 1, i + 1)
                      : OwbdLe16(r + 6) != sOwbdOverrideProvenance[i - 3])
            || !OwbdStaticValueValid(9, 1, r[8]) || r[9]) return FALSE;
        for (j = 0; j < i; j++) { u8 p[10]; if (!OwbdReadRecord(ctx, OWBD_S_POPULATION, j, p) || (OwbdLe16(p + 4) == OwbdLe16(r + 4) && p[8] != r[8])) return FALSE; }
    }
    for (i = 0; i < OWBD_HOOK_SET_COUNT; i++) { u8 r[8]; if (!OwbdReadRecord(ctx, OWBD_S_HOOK, i, r) || OwbdLe16(r + 2) != OwbdLe16(r) || r[4] > 1 || r[5] > 1 || r[6] > 1 || r[5] != r[6] || (r[4] && r[5]) || r[7]) return FALSE; }
    for (i = 0; i < OWBD_OWNER_COUNT; i++) { u8 r[6]; if (!OwbdReadRecord(ctx, OWBD_S_OWNER, i, r) || OwbdLe16(r) != 0x8102 + i || OwbdLe16(r + 2) != OwbdLe16(r) || r[4] > 1 || r[5]) return FALSE; }
    for (i = 0; i < OWBD_OVERRIDE_DEFINITION_COUNT; i++) {
        u8 r[36]; u16 controller, node, owner, recovery, applicability; BOOL applicationMatches = FALSE;
        if (!OwbdReadRecord(ctx, OWBD_S_DEFINITION, i, r) || OwbdLe16(r + 2) != OwbdLe16(r)
            || !(applicability = OwbdLe16(r + 12)) || !OwbdHasId(ctx, OWBD_S_APPLICABILITY, applicability)
            || OwbdLe16(r + 14) > 0xFF
            || r[16] < 1 || r[16] > 2 || r[17] > 5 || r[18] < 1 || r[18] > 2
            || r[20] < 1 || r[20] > 3 || r[21] < 1 || r[21] > 3 || r[22] > 2 || r[23] > 3
            || r[24] > 3 || r[25] > 1 || r[27] > 1 || r[29] > 1 || r[30] > 1
            || r[31] > 1 || r[32] > 1 || r[33] > 1 || r[34] || r[35]) return FALSE;
        controller = OwbdLe16(r + 4); node = OwbdLe16(r + 6); owner = OwbdLe16(r + 8);
        recovery = OwbdLe16(r + 10);
        if ((r[29] != 0) != (owner != 0) || (owner && !OwbdReferenceOwner(&ownerReferences, owner))) return FALSE;
        if ((r[27] != 0) != (r[28] != 0)) return FALSE;
        if (r[18] == 2) {
            if (controller || node || r[19] < 1 || r[19] > 7) return FALSE;
        } else {
            BOOL nodeMatches = FALSE;
            if (!OwbdHasId(ctx, OWBD_S_CONTROLLER, controller) || !OwbdHasId(ctx, OWBD_S_NODE, node) || r[19]) return FALSE;
            for (j = 0; j < OWBD_CONTROLLER_NODE_COUNT; j++) { u8 n[12]; if (!OwbdReadRecord(ctx, OWBD_S_NODE, j, n)) return FALSE; if (OwbdLe16(n) == node && OwbdLe16(n + 2) == controller) nodeMatches = TRUE; }
            if (!nodeMatches) return FALSE;
            if (r[32] || r[33] != (r[28] != 0)) return FALSE;
        }
        if ((r[22] == 0) != (r[23] == 0) || (r[23] == 0) != (r[26] == 0)
            || (r[24] != 0 && r[23] == 0) || (r[25] != 0) != (recovery != 0)) return FALSE;
        if (r[28] && (!r[29] || r[28] > 3 || owner != (r[28] == 1 ? 0x8107 : r[28] == 2 ? 0x8106 : 0x8108)
            || !OwbdHasId(ctx, OWBD_S_TRANSITION, recovery))) return FALSE;
        if (!r[28] && owner && (OwbdLe16(r) != 0x7004 || owner != 0x8105 || r[18] != 2 || r[19] != 3)) return FALSE;
        if (!r[28] && OwbdLe16(r) == 0x7004 && (!r[29] || owner != 0x8105)) return FALSE;
        if (!r[28] && recovery && !OwbdHasId(ctx, OWBD_S_TRANSITION, recovery)) return FALSE;
        for (j = 0; j < OWBD_APPLICABILITY_COUNT; j++) {
            u8 a[16]; if (!OwbdReadRecord(ctx, OWBD_S_APPLICABILITY, j, a)) return FALSE;
            if (OwbdLe16(a) == applicability
                && (r[16] != 1 || !(OwbdLe16(a + 2) & 12))
                && (r[18] == 2 || OwbdLe16(a + 8) == controller)) applicationMatches = TRUE;
        }
        if (!applicationMatches) return FALSE;
        if (recovery) {
            BOOL backlink = FALSE;
            for (j = 0; j < OWBD_TRANSITION_COUNT; j++) {
                u8 t[24]; if (!OwbdReadRecord(ctx, OWBD_S_TRANSITION, j, t)) return FALSE;
                if (OwbdLe16(t) == recovery && OwbdLe16(t + 2) == OwbdLe16(r)
                    && (!owner || OwbdLe16(t + 4) == owner)) backlink = TRUE;
            }
            if (!backlink) return FALSE;
        }
    }
    {
        u16 guardCursor = 0, operationCursor = 0, actionCursor = 0, recoveryCursor = 0;
        for (i = 0; i < OWBD_TRANSITION_COUNT; i++) {
            u8 r[24]; u16 tid, count, definitionOwner = 0; int k;
            if (!OwbdReadRecord(ctx, OWBD_S_TRANSITION, i, r) || !OwbdHasId(ctx, OWBD_S_DEFINITION, OwbdLe16(r + 2))
                || !OwbdReferenceOwner(&ownerReferences, OwbdLe16(r + 4)) || OwbdLe16(r + 6) != guardCursor
                || OwbdLe16(r + 10) != operationCursor || OwbdLe16(r + 14) != actionCursor
                || r[18] < 1 || r[18] > 13 || !r[19] || (r[19] & ~0x7F) || r[20] != recoveryCursor
                || OwbdLe16(r + 22) != (i < 17 ? 0x2000 + i : 0x3000 + i - 17)) return FALSE;
            for (k = 0; k < OWBD_OVERRIDE_DEFINITION_COUNT; k++) { u8 d[36]; if (!OwbdReadRecord(ctx, OWBD_S_DEFINITION, k, d)) return FALSE; if (OwbdLe16(d) == OwbdLe16(r + 2)) definitionOwner = OwbdLe16(d + 8); }
            if (definitionOwner && definitionOwner != OwbdLe16(r + 4)) return FALSE;
            tid = OwbdLe16(r); count = OwbdLe16(r + 8);
            if (count > OWBD_TRANSITION_GUARD_COUNT - guardCursor) return FALSE;
            guardCursor += count;
            count = OwbdLe16(r + 12);
            if (count > OWBD_TRANSITION_OPERATION_COUNT - operationCursor) return FALSE;
            operationCursor += count;
            count = OwbdLe16(r + 16);
            if (count > OWBD_TRANSITION_ACTION_COUNT - actionCursor) return FALSE;
            actionCursor += count;
            if (r[21] > OWBD_RECOVERY_ACTION_COUNT - recoveryCursor) return FALSE;
            recoveryCursor += r[21];
            for (j = 0; j < OwbdLe16(r + 8); j++) {
                u8 g[12]; u16 reference;
                if (!OwbdReadRecord(ctx, OWBD_S_GUARD, OwbdLe16(r + 6) + j, g) || OwbdLe16(g + 2) != tid
                    || g[4] < 1 || g[4] > 8 || g[5] > 1 || g[7] || OwbdLe16(g + 10)) return FALSE;
                reference = OwbdLe16(g + 8);
                switch (g[4]) {
                case 1: if (g[6] || reference) return FALSE; break;
                case 2: if (g[6] < 1 || g[6] > 7 || reference) return FALSE; break;
                case 3: if (g[6] || !OwbdHasId(ctx, OWBD_S_NODE, reference)) return FALSE; break;
                case 4: case 5: if (g[6] || !OwbdReferenceOwner(&ownerReferences, reference)) return FALSE; break;
                case 6: if (g[6] < 1 || g[6] > 3 || reference) return FALSE; break;
                case 7: if (g[6] > 100 || reference) return FALSE; break;
                case 8: if (g[6] < 1 || g[6] > 13 || reference) return FALSE; break;
                }
            }
            for (j = 0; j < OwbdLe16(r + 12); j++) { u8 o[18]; if (!OwbdReadRecord(ctx, OWBD_S_OPERATION, OwbdLe16(r + 10) + j, o) || OwbdLe16(o + 2) != tid) return FALSE; }
            for (j = 0; j < OwbdLe16(r + 16); j++) { u8 a[10]; if (!OwbdReadRecord(ctx, OWBD_S_TRANSITION_ACTION, OwbdLe16(r + 14) + j, a) || OwbdLe16(a + 2) != tid) return FALSE; }
            for (j = 0; j < r[21]; j++) { u8 q[8]; if (!OwbdReadRecord(ctx, OWBD_S_RECOVERY, r[20] + j, q) || OwbdLe16(q + 2) != tid || OwbdLe16(q + 4) != OwbdLe16(r + 4)) return FALSE; }
        }
        if (guardCursor != OWBD_TRANSITION_GUARD_COUNT || operationCursor != OWBD_TRANSITION_OPERATION_COUNT
            || actionCursor != OWBD_TRANSITION_ACTION_COUNT || recoveryCursor != OWBD_RECOVERY_ACTION_COUNT) return FALSE;
    }
    for (i = 0; i < OWBD_TRANSITION_OPERATION_COUNT; i++) {
        u8 r[18], ownerMatches = 0, requiredOwnerMatches;
        u16 definition, owner, replacement, policy, instance;
        if (!OwbdReadRecord(ctx, OWBD_S_OPERATION, i, r) || !OwbdHasId(ctx, OWBD_S_TRANSITION, OwbdLe16(r + 2))
            || r[14] < 1 || r[14] > 6 || r[15] < 1 || r[15] > 2 || r[16] > 1 || r[17]) return FALSE;
        definition = OwbdLe16(r + 4); owner = OwbdLe16(r + 6); replacement = OwbdLe16(r + 8);
        policy = OwbdLe16(r + 10); instance = OwbdLe16(r + 12);
        switch (r[14]) {
        case 1:
            if (!OwbdHasId(ctx, OWBD_S_DEFINITION, definition)
                || replacement || policy || instance != definition || r[16]) return FALSE;
            break;
        case 2:
            if (!OwbdHasId(ctx, OWBD_S_DEFINITION, definition)
                || !OwbdHasId(ctx, OWBD_S_DEFINITION, replacement) || policy || instance != definition || r[16]) return FALSE;
            break;
        case 3:
            if (!OwbdHasId(ctx, OWBD_S_DEFINITION, definition)
                || replacement || policy || instance || r[16] != 1) return FALSE;
            break;
        case 4:
            if (!OwbdHasId(ctx, OWBD_S_DEFINITION, definition)
                || replacement || policy || instance || r[16]) return FALSE;
            break;
        case 5:
            if (definition || replacement || policy || instance || r[16]) return FALSE;
            break;
        case 6:
            if (definition || owner || replacement || !policy || instance || r[16]) return FALSE;
            break;
        }
        if ((r[14] <= 5) != (owner != 0) || (owner && !OwbdReferenceOwner(&ownerReferences, owner))) return FALSE;
        if (r[14] <= 4) {
            requiredOwnerMatches = r[14] == 2 ? 3 : 1;
            for (j = 0; j < OWBD_OVERRIDE_DEFINITION_COUNT; j++) {
                u8 d[36]; u16 id, requiredOwner;
                if (!OwbdReadRecord(ctx, OWBD_S_DEFINITION, j, d)) return FALSE;
                id = OwbdLe16(d); requiredOwner = OwbdLe16(d + 8);
                if (!requiredOwner || requiredOwner == owner) {
                    if (id == definition) ownerMatches |= 1;
                    if (id == replacement) ownerMatches |= 2;
                }
            }
            if ((ownerMatches & requiredOwnerMatches) != requiredOwnerMatches) return FALSE;
        }
    }
    for (i = 0; i < OWBD_TRANSITION_ACTION_COUNT; i++) { u8 r[10]; if (!OwbdReadRecord(ctx, OWBD_S_TRANSITION_ACTION, i, r) || !OwbdHasId(ctx, OWBD_S_TRANSITION, OwbdLe16(r + 2)) || r[4] < 1 || r[4] > 4 || r[5] < 1 || r[5] > 8 || OwbdLe16(r + 6) || OwbdLe16(r + 8)) return FALSE; }
    for (i = 0; i < OWBD_RECOVERY_ACTION_COUNT; i++) { u8 r[8]; if (!OwbdReadRecord(ctx, OWBD_S_RECOVERY, i, r) || !OwbdHasId(ctx, OWBD_S_TRANSITION, OwbdLe16(r + 2)) || !OwbdReferenceOwner(&ownerReferences, OwbdLe16(r + 4)) || r[6] < 1 || r[6] > 4 || r[7] > 1) return FALSE; }
    for (i = 0; i < OWBD_IMPORT_RECIPE_COUNT; i++) {
        u8 r[24]; u16 controller, node, profile; u8 role, flags; BOOL nodeMatches = FALSE;
        if (!OwbdReadRecord(ctx, OWBD_S_IMPORT, i, r) || !OwbdReferenceOwner(&ownerReferences, OwbdLe16(r + 2))
            || !OwbdHasId(ctx, OWBD_S_IDENTITY, OwbdLe16(r + 8))
            || r[21] < 1 || r[21] > 3 || (flags = r[22]) > 1 || r[23]) return FALSE;
        controller = OwbdLe16(r + 4); node = OwbdLe16(r + 6);
        profile = OwbdLe16(r + 8); role = r[20];
        if (!OwbdIdentityHasRole(ctx, profile, role, !flags)) return FALSE;
        if (!flags) {
            int kind = i % 3, controllerIndex = i / 3;
            if (i >= 9 || controller != 0x3001 + controllerIndex
                || OwbdLe16(r + 2) != sOwbdImportExpectedOwner[kind] || OwbdLe16(r + 10) != sOwbdImportExpectedRecovery[kind]
                || OwbdLe16(r + 12) != sOwbdImportExpectedSource[kind] || role != sOwbdImportExpectedRole[kind]
                || r[21] != sOwbdImportExpectedLifetime[kind] || OwbdLe16(r + 18) != 0xFFFF) return FALSE;
            for (j = 0; j < OWBD_CONTROLLER_NODE_COUNT; j++) { u8 n[12]; if (!OwbdReadRecord(ctx, OWBD_S_NODE, j, n)) return FALSE; if (OwbdLe16(n) == node && OwbdLe16(n + 2) == controller && OwbdLe16(n + 4) == profile && n[8] == role) nodeMatches = TRUE; }
            if (!nodeMatches) return FALSE;
            if (!sOwbdImportExpectedSource[kind]) { if (OwbdLe16(r + 14) || OwbdLe16(r + 16)) return FALSE; }
            else { u8 o[28]; if (!OwbdReadRecord(ctx, OWBD_S_OVERRIDE, sOwbdImportExpectedSource[kind] - 0x5001, o)
                || OwbdLe16(o + 20) != OwbdLe16(r + 14) || OwbdLe16(o + 22) != OwbdLe16(r + 16)) return FALSE; }
        } else if (i < 9 || OwbdLe16(r + 2) != 0x8109 || controller || node
            || OwbdLe16(r + 10) || OwbdLe16(r + 12) || OwbdLe16(r + 14)
            || OwbdLe16(r + 16) || OwbdLe16(r + 18) || r[21] != 1
            || role != i - 8) return FALSE;
        for (j = 0; j < i; j++) {
            u8 p[24]; if (!OwbdReadRecord(ctx, OWBD_S_IMPORT, j, p)) return FALSE;
            if (p[22] == flags && OwbdLe16(p + 4) == controller && p[20] == role) return FALSE;
        }
    }
    for (i = 0; i < OWBD_APPLICABILITY_COUNT; i++) {
        u8 r[16]; u16 flags, controller, profile; int claims = 0;
        if (!OwbdReadRecord(ctx, OWBD_S_APPLICABILITY, i, r) || !(flags = OwbdLe16(r + 2))
            || (flags & ~0xF) || r[13] || OwbdLe16(r + 14)) return FALSE;
        controller = OwbdLe16(r + 8); profile = OwbdLe16(r + 10);
        if (((flags & 1) == 0) != (OwbdLe32(r + 4) == 0)
            || ((flags & 2) ? !OwbdHasId(ctx, OWBD_S_CONTROLLER, controller) : controller != 0)
            || ((flags & 4) ? !OwbdHasId(ctx, OWBD_S_IDENTITY, profile) : profile != 0)
            || ((flags & 8) ? (r[12] < 1 || r[12] > 7) : r[12] != 0)) return FALSE;
        for (j = 0; j < OWBD_OVERRIDE_DEFINITION_COUNT; j++) { u8 d[36]; if (!OwbdReadRecord(ctx, OWBD_S_DEFINITION, j, d)) return FALSE; if (OwbdLe16(d + 12) == OwbdLe16(r)) claims++; }
        if (claims != 1) return FALSE;
    }
    for (i = 0; i < OWBD_TIRED_TRANSLATION_COUNT; i++) {
        u8 r[24], d[36]; int origin = i / 6 + 1, controllerIndex = (i / 2) % 3, bound = i & 1;
        u16 controller = 0x3001 + controllerIndex;
        u16 definition = bound ? 0x7004 + origin : 0x700B + (origin - 1) * 3 + controllerIndex;
        u16 recovery = bound ? 0xA003 + origin * 2 : 0xA012 + (origin - 1) * 3 + controllerIndex;
        u16 profile = bound ? 0x2203 + controllerIndex * 3 : 0x2210 + controllerIndex;
        if (!OwbdReadRecord(ctx, OWBD_S_TIRED_TRANSLATION, i, r)
            || r[2] != origin || r[3] != bound || OwbdLe16(r + 4) != controller
            || OwbdLe16(r + 6) != profile || OwbdLe16(r + 8) != definition
            || OwbdLe16(r + 10) != recovery || r[16] != 1 || r[17] != 1
            || r[18] != 2 || r[19] != 1 || OwbdLe16(r + 20) || OwbdLe16(r + 22)
            || !OwbdIdentityHasRole(ctx, profile, bound ? 3 : 7, TRUE)
            || !OwbdReadRecord(ctx, OWBD_S_DEFINITION, definition - 0x7001, d)
            || !d[27] || d[28] != origin || OwbdLe16(d + 10) != recovery) return FALSE;
        if (bound) {
            if (OwbdLe16(r + 12) || OwbdLe16(r + 14) || d[18] != 2 || d[19] != 3
                || OwbdLe16(d + 4) || OwbdLe16(d + 6)) return FALSE;
        } else if (OwbdLe16(r + 12) != controller || OwbdLe16(r + 14) != 0x3107 + controllerIndex * 7
            || d[18] != 1 || d[19] || OwbdLe16(d + 4) != controller
            || OwbdLe16(d + 6) != OwbdLe16(r + 14)) return FALSE;
    }
    return ownerReferences == (1u << OWBD_OWNER_COUNT) - 1;
}

static BOOL OwbdValidateStream(OwbdReadCallback read, void *readContext, u32 size, void *workspace, u32 workspaceSize)
{
    OwbdSharedContext ctx;
    u32 cursor;
    int section;
    if (!read || !workspace || workspaceSize < OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE
        || size != OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE) return FALSE;
    ctx.read = read; ctx.readContext = readContext; ctx.size = size;
    if (!OwbdBoundedRead(&ctx, 0, sizeof(ctx.header), ctx.header)
        || OwbdLe32(ctx.header) != OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC
        || OwbdLe16(ctx.header + 4) != OVERWORLD_WILD_BEHAVIOR_DATA_VERSION
        || OwbdLe16(ctx.header + 6) != sizeof(ctx.header) || OwbdLe32(ctx.header + 8) != size
        || OwbdLe32(ctx.header + 12) != (OWBD_BLOB_FLAG_NAMES_ARE_HASHES | OWBD_BLOB_FLAG_AUTHORED_SOURCE)
#if !defined(OWBD_VALIDATION_TEST_ALLOW_DYNAMIC_CHECKSUM) && !defined(OWBD_VALIDATION_EXTERNAL_INTEGRITY)
        || OwbdLe32(ctx.header + 16) != OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM
#endif

#undef OWBD_RESIDENT_DATA
#undef OWBD_RESIDENT_CODE
        || OwbdLe32(ctx.header + 20) != OVERWORLD_WILD_BEHAVIOR_DATA_SCHEMA_FINGERPRINT
#ifndef OWBD_VALIDATION_EXTERNAL_INTEGRITY
        || !OwbdChecksum(&ctx, workspace)
#endif
        ) return FALSE;
    cursor = sizeof(ctx.header);
    for (section = 0; section < OWBD_S_COUNT; section++) {
        const u8 *d = OwbdDesc(&ctx, section);
        u32 offset = OwbdLe32(d), bytes, aligned; u8 pad;
        if (OwbdLe16(d + 4) != sOwbdSpecs[section].count || OwbdLe16(d + 6) != sOwbdSpecs[section].stride
            || offset != cursor || (offset & 3) || offset > size
            || sOwbdSpecs[section].count > (size - offset) / sOwbdSpecs[section].stride) return FALSE;
        bytes = (u32)sOwbdSpecs[section].count * sOwbdSpecs[section].stride;
        cursor = offset + bytes; aligned = (cursor + 3) & ~3u;
        while (cursor < aligned) { if (!OwbdBoundedRead(&ctx, cursor, 1, &pad) || pad) return FALSE; cursor++; }
    }
    if (cursor != size) return FALSE;
    ctx.ids = workspace;
    return OwbdLoadStableIds(&ctx) && OwbdValidateRecords(&ctx);
}

#endif

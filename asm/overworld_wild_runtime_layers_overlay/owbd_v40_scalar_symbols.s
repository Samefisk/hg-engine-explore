/*
 * Typed absolute imports for the single boot-resident Task-5 v40 scalar
 * domain implementation in overlay 155.  Overlay 155 already imports the
 * overlay-158 lifecycle API, so this fixed shard avoids a circular link.
 * Package/source gates compare every address and type with linked overlay 155.
 */
    .syntax unified

    .global sOwbdStateValueMax
    .type sOwbdStateValueMax, %object
    .set sOwbdStateValueMax, 0x023BDEB0

    .global sOwbdNumericFieldMasks
    .type sOwbdNumericFieldMasks, %object
    .set sOwbdNumericFieldMasks, 0x023BDECC

    .global OwbdStaticValueValid
    .type OwbdStaticValueValid, %function
    .thumb_set OwbdStaticValueValid, 0x023BDF91

    .global OwbdModifierPayloadValid
    .type OwbdModifierPayloadValid, %function
    .thumb_set OwbdModifierPayloadValid, 0x023BE035

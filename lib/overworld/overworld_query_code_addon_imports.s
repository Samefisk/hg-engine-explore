.syntax unified
.thumb
/* Pinned boot-resident Thumb shims. No unloadable-overlay code imports. */
.global memset
.thumb_func
.thumb_set memset, 0x023DEEA2
.global memcpy
.thumb_func
.thumb_set memcpy, 0x023DEEBE
.global __aeabi_uidivmod
.thumb_func
.thumb_set __aeabi_uidivmod, 0x023DEE4C

.global OverworldConditionPublication_InitResult
.thumb_func
.thumb_set OverworldConditionPublication_InitResult, 0x01FF9A48

.global OverworldConditionPublication_FoldResult
.thumb_func
.thumb_set OverworldConditionPublication_FoldResult, 0x01FF9C94

.global OverworldConditionPublication_BlobValid
.thumb_func
.thumb_set OverworldConditionPublication_BlobValid, 0x01FFA39C

.global OverworldConditionPublication_CapturePrior
.thumb_func
.thumb_set OverworldConditionPublication_CapturePrior, 0x023C2F74

/* Current loaded Field/Helper owners are proved before this synchronous borrow. */
.global OverworldConditionSubject_Populate
.thumb_func
.thumb_set OverworldConditionSubject_Populate, 0x02208200
.global OverworldConditionVisibility_PlayerX
.thumb_func
.thumb_set OverworldConditionVisibility_PlayerX, 0x0205C67C
.global OverworldConditionVisibility_PlayerY
.thumb_func
.thumb_set OverworldConditionVisibility_PlayerY, 0x0205C688
.global OverworldConditionVisibility_TraceBlocked
.thumb_func
.thumb_set OverworldConditionVisibility_TraceBlocked, 0x023C7EA8

/* Existing boot-resident packed slice merge; real ABS32 keeps Thumb bit. */
.global OverworldBehaviorPackedOptions_Apply
.thumb_func
.thumb_set OverworldBehaviorPackedOptions_Apply, 0x01FFD2CC

.nds
.thumb

// VBlank task queue capacity.
//
// InitSystemForTheGame places gSystem.vblankTaskQueue with 32 slots in the main
// arena. Field map init (FieldMap_InitFieldEffectsAndObjects) first loads the
// default field-effect renderers, which queue 32 RenderModel_BindTexturesOnVBlank
// tasks, and then MapObjectRender_InitQueue adds its persistent texture-transfer
// task to the same queue. When no VBlank interrupt drains the bind tasks in
// between (deterministic on MAP_R45 after a script warp), that 33rd create
// returns NULL. The map then runs without map-object texture transfers, and the
// next field exit calls SysTask_Destroy(NULL) in MapObjectRender_DestroyQueue:
// an ARM9 data abort at 0x0201F958 (lr 0x021FA919).
//
// Give the queue 64 slots. The extra 32 * (sizeof(SysTask) + sizeof(SysTask *))
// = 1024 bytes come from the main arena gap below resident overlay 158
// (arena lo after boot ~0x023B592C, overlay 158 at 0x023B65C0: 3220 bytes,
// minus up to 252 bytes of random heap pre-padding).
.open "base/arm9.bin", 0x02000000

// SysTaskQueue_GetArenaSize(32) for the VBlank queue
.org 0x0201A240
    mov r0, #64

// SysTaskQueue_PlacementNew(32, ...) for the VBlank queue
.org 0x0201A252
    mov r0, #64

.close

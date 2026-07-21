.nds
.thumb

// FieldSystem_Control normally calls FieldInput_Update here.  Route that one
// call through overlay 131 so a short Y tap can remain the registered-item
// shortcut while a held Y is reserved for the custom follower selector.
.open "base/arm9.bin", 0x02000000

.if readu32("base/arm9.bin", 0x0003E182) != 0xFBD1F1A8
    .error "FieldSystem_Control FieldInput_Update call changed"
.endif

.org 0x0203E182
    bl 0x023C8010

.close

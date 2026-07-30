.text
.align 1
.force_thumb
.syntax unified

.global memset
.thumb_func
.type memset, %function
memset:
    push {lr}
    blx 0x020E5B44
    pop {pc}
.size memset, . - memset

.global memcpy
.thumb_func
.type memcpy, %function
memcpy:
    push {lr}
    blx 0x020E5AD8
    pop {pc}
.size memcpy, . - memcpy

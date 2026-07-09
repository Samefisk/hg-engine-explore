.text
.align 1
.force_thumb
.syntax unified

.global __aeabi_idiv
.thumb_func
.type __aeabi_idiv,function
__aeabi_idiv:
.global __aeabi_idivmod
.thumb_func
.type __aeabi_idivmod,function
__aeabi_idivmod:
    push {lr}
    blx 0x020F2998
    pop {pc}
.size __aeabi_idiv, . - __aeabi_idiv
.size __aeabi_idivmod, . - __aeabi_idivmod

.global __aeabi_uidiv
.thumb_func
.type __aeabi_uidiv,function
__aeabi_uidiv:
.global __aeabi_uidivmod
.thumb_func
.type __aeabi_uidivmod,function
__aeabi_uidivmod:
    push {lr}
    blx 0x020F2BA4
    pop {pc}
.size __aeabi_uidiv, . - __aeabi_uidiv
.size __aeabi_uidivmod, . - __aeabi_uidivmod

.global __gnu_thumb1_case_uqi
.thumb_func
.type __gnu_thumb1_case_uqi,function
__gnu_thumb1_case_uqi:
    push {r1}
    mov r1, lr
    lsrs r1, r1, #1
    lsls r1, r1, #1
    ldrb r1, [r1, r0]
    lsls r1, r1, #1
    add lr, lr, r1
    pop {r1}
    bx lr
.size __gnu_thumb1_case_uqi, . - __gnu_thumb1_case_uqi

.global __gnu_thumb1_case_uhi
.thumb_func
.type __gnu_thumb1_case_uhi,function
__gnu_thumb1_case_uhi:
    push {r0, r1}
    mov r1, lr
    lsrs r1, r1, #1
    lsls r0, r0, #1
    lsls r1, r1, #1
    ldrh r1, [r1, r0]
    lsls r1, r1, #1
    add lr, lr, r1
    pop {r0, r1}
    bx lr
.size __gnu_thumb1_case_uhi, . - __gnu_thumb1_case_uhi

.global memset
.thumb_func
.type memset,function
memset:
    push {lr}
    blx 0x020E5B44
    pop {pc}
.size memset, . - memset

.global memcpy
.thumb_func
.type memcpy,function
memcpy:
    push {lr}
    blx 0x020E5AD8
    pop {pc}
.size memcpy, . - memcpy

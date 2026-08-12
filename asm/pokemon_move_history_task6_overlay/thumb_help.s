    .text
    .align 1
    .force_thumb
    .syntax unified

    .global __aeabi_idiv
    .global __aeabi_idivmod
    .thumb_func
    .type __aeabi_idiv, %function
    .type __aeabi_idivmod, %function
__aeabi_idiv:
__aeabi_idivmod:
    push {lr}
    blx 0x020F2998
    pop {pc}
    .size __aeabi_idiv, . - __aeabi_idiv
    .size __aeabi_idivmod, . - __aeabi_idivmod

    .global __aeabi_uidiv
    .global __aeabi_uidivmod
    .thumb_func
    .type __aeabi_uidiv, %function
    .type __aeabi_uidivmod, %function
__aeabi_uidiv:
__aeabi_uidivmod:
    push {lr}
    blx 0x020F2BA4
    pop {pc}
    .size __aeabi_uidiv, . - __aeabi_uidiv
    .size __aeabi_uidivmod, . - __aeabi_uidivmod

    .global memset
    .thumb_func
    .type memset, %function
memset:
    push {lr}
    blx 0x020E5B44
    pop {pc}
    .size memset, . - memset

    .global __aeabi_lmul
    .thumb_func
    .type __aeabi_lmul, %function
__aeabi_lmul:
    push {lr}
    blx 0x020F2948
    pop {pc}
    .size __aeabi_lmul, . - __aeabi_lmul

    .global __aeabi_ldivmod
    .thumb_func
    .type __aeabi_ldivmod, %function
__aeabi_ldivmod:
    push {lr}
    blx 0x020F2750
    pop {pc}
    .size __aeabi_ldivmod, . - __aeabi_ldivmod

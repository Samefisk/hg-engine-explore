/* Artifact link base only. Runtime owns an ordinary World-heap allocation;
 * the package rebases validated local pointers to that actual allocation. */
OUTPUT_ARCH(arm)
SECTIONS {
    . = 0x02080000;
    .text : {
        KEEP(*(.query_addon_entry))
        ASSERT(ABSOLUTE(.) == 0x020800C4, "query addon entry size changed");
        *(EXCLUDE_FILE (*overworld_return_move_wild.o *overworld_condition_moving_notice_native.o *overworld_behavior_resolver.o *overworld_behavior_resolver_query_call.o *overworld_cargo_query_wild.o *overworld_entry_route.o *overworld_prepared_movement.o *overworld_hop_clearance_native.o *overworld_behavior_condition_runtime.o) .text*)
        *(EXCLUDE_FILE (*overworld_return_move_wild.o *overworld_condition_moving_notice_native.o *overworld_behavior_resolver.o *overworld_behavior_resolver_query_call.o *overworld_cargo_query_wild.o *overworld_entry_route.o *overworld_prepared_movement.o *overworld_hop_clearance_native.o *overworld_behavior_condition_runtime.o) .rodata*)
        . = ALIGN(4);
        __query_cargo_code_end = ABSOLUTE(.);
        ASSERT(ABSOLUTE(.) <= 0x02088800, "query addon Cargo prefix exceeds its cap");
        *overworld_return_move_wild.o(.text*)
        *overworld_return_move_wild.o(.rodata*)
        *overworld_behavior_condition_runtime.o(.text* .rodata*)
        *overworld_condition_moving_notice_native.o(.text*)
        *overworld_condition_moving_notice_native.o(.rodata*)
        *overworld_behavior_resolver.o(.text*)
        *overworld_behavior_resolver.o(.rodata*)
        *overworld_behavior_resolver.o(.overworld_actor_*_constants)
        *overworld_behavior_resolver.o(.overworld_condition_adapter_constants)
        *overworld_behavior_resolver_query_call.o(.text*)
        *overworld_behavior_resolver_query_call.o(.rodata*)
        KEEP(*(.query_pickup_handoff))
        KEEP(*(.query_native_observation))
        . = ALIGN(4);
        __query_return_code_end = ABSOLUTE(.);
        __query_entry_code_begin = ABSOLUTE(.);
        /* One existing loaded Query owner. These coupled adapters use the
         * existing Cargo graph and sole Hop clearance reducer, not a loader. */
        *overworld_cargo_query_wild.o(.text* .rodata*)
        *overworld_entry_route.o(.text* .rodata*)
        *overworld_prepared_movement.o(.text* .rodata*)
        *overworld_hop_clearance_native.o(.text* .rodata*)
        . = ALIGN(4);
        __query_entry_code_end = ABSOLUTE(.);
        /* Root replaces this heap image guard only after the full ARM size,
         * package cost and current Field free-heap admission are measured. */
        ASSERT(SIZEOF(.text) <= 0x10C38, "query addon image exceeds its cap");
    }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0,
           "query addon must use caller-owned mutable storage")
}

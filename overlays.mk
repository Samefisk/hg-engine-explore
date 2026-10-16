# macros for overlay definition that automatically grab everything that we need from the folders provided
CODE_BUILD_DIRS += $(BUILD)
THUMB_HELP := $(BUILD)/thumb_help.o
LINKED_OUTPUTS = build/linked.o
OVERWORLD_QUERY_CODE_ADDON_DIR := $(BUILD)/overworld_query_code_addon
OVERWORLD_QUERY_CODE_ADDON_OBJS := \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_target_bindings.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_pickup_route.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_pickup_route_native.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_pickup_route_wild.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_cargo_query.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_cargo_query_wild.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_entry_route.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_prepared_movement.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_hop_clearance_native.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_pickup_landing_wild.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_cargo_read_wild.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_contact_geometry.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_throw_away_aim.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_throw_away_wild.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_throw_held_wild.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_throw_observation_query.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_player_damage_condition.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_behavior_condition_runtime.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_condition_moving_notice_native.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_query_code_addon_entry.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_query_code_addon_imports.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_return_move_wild.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_behavior_resolver.o \
	$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_behavior_resolver_query_call.o
OVERWORLD_QUERY_CODE_ADDON_ELF := $(OVERWORLD_QUERY_CODE_ADDON_DIR)/image.elf
OVERWORLD_QUERY_CODE_ADDON_BIN := $(OVERWORLD_QUERY_CODE_ADDON_DIR)/query.bin
OVERWORLD_QUERY_CODE_ADDON_RECEIPT := $(OVERWORLD_QUERY_CODE_ADDON_DIR)/package.json
OVERWORLD_QUERY_CODE_ADDON_HEADER := $(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_query_code_addon_package.h
OVERWORLD_QUERY_CODE_ADDON_TARGET := $(BUILD)/a028/9_21
CODE_BUILD_DIRS += $(OVERWORLD_QUERY_CODE_ADDON_DIR)
LINKED_OUTPUTS += $(OVERWORLD_QUERY_CODE_ADDON_ELF)
OVERLAY_OUTPUTS += $(OVERWORLD_QUERY_CODE_ADDON_BIN) \
	$(OVERWORLD_QUERY_CODE_ADDON_RECEIPT) $(OVERWORLD_QUERY_CODE_ADDON_HEADER)
NARC_FILES += $(OVERWORLD_QUERY_CODE_ADDON_BIN)

# Ordinary World-heap code. Only its authenticated local ABS32 words move;
# long calls retain typed fixed imports. No static RAM or SDK overlay added.
$(OVERWORLD_QUERY_CODE_ADDON_DIR)/%.o: lib/overworld/%.c $(BUILD)/.compile-config \
		overlays.mk | $(OVERWORLD_QUERY_CODE_ADDON_DIR) venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) \
		-mcpu=arm946e-s -mtune=arm946e-s -march=armv5te \
		-mlong-calls -fno-jump-tables -I$(INCLUDE_SUBDIR) -c $< -o $@

$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_behavior_condition_runtime.o: \
		lib/overworld/overworld_behavior_condition_runtime.c \
		lib/overworld/overworld_behavior_conditions.c lib/overworld/overworld_vision.c \
		$(BUILD)/.compile-config overlays.mk | $(OVERWORLD_QUERY_CODE_ADDON_DIR) venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) \
		-mcpu=arm946e-s -mtune=arm946e-s -march=armv5te \
		-mlong-calls -fno-jump-tables -ffunction-sections \
		-DOVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME=1 \
		-DOVERWORLD_BEHAVIOR_CONDITION_RELOCATABLE_CODE=1 \
		-I$(INCLUDE_SUBDIR) -c $< -o $@

$(OVERWORLD_QUERY_CODE_ADDON_DIR)/overworld_query_code_addon_imports.o: \
		lib/overworld/overworld_query_code_addon_imports.s $(BUILD)/.compile-config \
		| $(OVERWORLD_QUERY_CODE_ADDON_DIR) toolchain-preflight
	$(AS) $(ASFLAGS) $< -o $@

$(OVERWORLD_QUERY_CODE_ADDON_ELF): $(OVERWORLD_QUERY_CODE_ADDON_OBJS) \
		lib/overworld/overworld_query_code_addon.ld
	@rm -f $@.tmp
	$(LD) --emit-relocs -T lib/overworld/overworld_query_code_addon.ld \
		-o $@.tmp $(OVERWORLD_QUERY_CODE_ADDON_OBJS) && mv $@.tmp $@

$(OVERWORLD_QUERY_CODE_ADDON_BIN): $(OVERWORLD_QUERY_CODE_ADDON_ELF) \
		tools/overworld/pack_query_code_addon.py | venv
	$(PYTHON) tools/overworld/pack_query_code_addon.py $< $@ \
		--receipt $(OVERWORLD_QUERY_CODE_ADDON_RECEIPT) --header $(OVERWORLD_QUERY_CODE_ADDON_HEADER)

$(OVERWORLD_QUERY_CODE_ADDON_RECEIPT) $(OVERWORLD_QUERY_CODE_ADDON_HEADER): $(OVERWORLD_QUERY_CODE_ADDON_BIN)
	@test -f $@ || $(PYTHON) tools/overworld/pack_query_code_addon.py \
		$(OVERWORLD_QUERY_CODE_ADDON_ELF) $(OVERWORLD_QUERY_CODE_ADDON_BIN) \
		--receipt $(OVERWORLD_QUERY_CODE_ADDON_RECEIPT) --header $(OVERWORLD_QUERY_CODE_ADDON_HEADER)

$(BUILD)/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o: $(OVERWORLD_QUERY_CODE_ADDON_HEADER)

-include $(OVERWORLD_QUERY_CODE_ADDON_OBJS:.o=.d)
OVERWORLD_FIELD_CAPSULE_OBJS := \
	$(BUILD)/overworld_field_capsule/overworld_actor_appearance.o \
	$(BUILD)/overworld_field_capsule/overworld_actor_appearance_native.o \
	$(BUILD)/overworld_field_capsule/overworld_appearance_policy.o \
	$(BUILD)/overworld_field_capsule/overworld_condition_subject_native.o \
	$(BUILD)/overworld_field_capsule/overworld_world_effect_delivery.o
CODE_BUILD_DIRS += $(BUILD)/overworld_field_capsule
LINKED_OUTPUTS += $(BUILD)/overworld_field_capsule_linked.o
OVERLAY_OUTPUTS += $(BUILD)/output_overworld_field_capsule.bin

# Stock overlay 1 already owns this physical reservation. It is not another
# SDK overlay or synthetic-overlay table entry. The Field parent owns its lifetime.
$(BUILD)/overworld_field_capsule/%.o: lib/overworld/%.c $(BUILD)/.compile-config \
		| $(BUILD)/overworld_field_capsule venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) \
		-mcpu=arm946e-s -mtune=arm946e-s -march=armv5te \
		-I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_field_capsule/overworld_condition_subject_native.o: \
		lib/overworld/overworld_condition_subject_native.c $(BUILD)/.compile-config overlays.mk \
		| $(BUILD)/overworld_field_capsule venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_field_condition.o: $(BUILD)/overworld_follower_selector_overlay_linked.o \
        $(BUILD)/overworld_wild_spawns_overlay_linked.o \
		$(BUILD)/overworld_mount_overlay_linked.o \
		$(BUILD)/player_health_overlay_linked.o \
		$(BUILD)/pokemon_move_history_overlay_linked.o \
		scripts/pack_overworld_field_capsule.py scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_field_capsule.py --build-dir $(BUILD) --objcopy $(OBJCOPY)

# Field131 hosts this one fully linked private read callback in its data gap.
$(BUILD)/overworld_field_cargo_observation.o: $(BUILD)/overworld_wild_spawns_overlay_linked.o \
		scripts/pack_overworld_field_capsule.py scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_field_capsule.py --build-dir $(BUILD) --objcopy $(OBJCOPY) --cargo-only

$(BUILD)/field_linked.o: $(BUILD)/overworld_field_cargo_observation.o

$(BUILD)/overworld_field_capsule_linked.o: $(OVERWORLD_FIELD_CAPSULE_OBJS) \
		$(BUILD)/overworld_field_condition.o rom_gen.ld lib/overworld/overworld_field_capsule.ld
	@rm -f $@.tmp
	$(LD) rom_gen.ld -T lib/overworld/overworld_field_capsule.ld -o $@.tmp \
		$(OVERWORLD_FIELD_CAPSULE_OBJS) $(BUILD)/overworld_field_condition.o && mv $@.tmp $@

# Final payload copy only: HP ELF never depends on this Field leaf.
$(BUILD)/output_overworld_field_capsule.bin: $(BUILD)/overworld_field_capsule_linked.o \
        $(BUILD)/output_player_health_overlay.bin scripts/pack_overworld_field_capsule.py \
        scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_field_capsule.py --build-dir $(BUILD) --appearance-release-only
	$(OBJCOPY) -O binary --remove-section=.overworld_appearance_release \
		--remove-section=.overworld_appearance_rest_policy $< $@

-include $(OVERWORLD_FIELD_CAPSULE_OBJS:.o=.d)
$(BUILD)/overworld_actor_slam_jump.o: $(BUILD)/overworld_wild_spawns_overlay_linked.o \
        scripts/pack_overworld_actor_slam_jump.py scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_actor_slam_jump.py --build-dir $(BUILD) --as $(AS)

OVERWORLD_ACTOR_SYSTEM_PORTABLE_OBJS := \
	$(BUILD)/overworld_actor_slam_jump.o \
	$(BUILD)/overworld_actor_rest_tint.o \
	$(BUILD)/overworld_actor_system_overlay/overworld_behavior_condition_adapter.o \
	$(BUILD)/overworld_actor_system_overlay/overworld_behavior_resolver.o \
	$(BUILD)/overworld_actor_system_overlay/overworld_motion_model.o \
	$(BUILD)/overworld_actor_system_overlay/overworld_actor_transition_model.o \
	$(BUILD)/overworld_actor_system_overlay/overworld_population_model.o \
	$(BUILD)/overworld_emote_slots.o \
	$(BUILD)/overworld_emote_slots_admission.o \
	$(BUILD)/overworld_emote_slots_imports.o

# One-way Field source -> boot Actor copy; Field never depends on Actor link.
$(BUILD)/overworld_actor_rest_tint.o: $(BUILD)/overworld_field_capsule_linked.o \
		scripts/pack_overworld_field_capsule.py scripts/pack_overworld_combat_capsules.py \
		scripts/verify_pokemon_move_history_capture.py | venv toolchain-preflight
	$(PYTHON) scripts/pack_overworld_field_capsule.py --build-dir $(BUILD) \
		--rest-policy-only --as $(AS)
# Private three-slot admission around the existing stock model owner.
$(BUILD)/overworld_emote_slots.o: lib/overworld/overworld_emote_slots.c \
        include/overworld_emote_slots_internal.h $(BUILD)/.compile-config overlays.mk \
        | $(BUILD) venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) $(OVERWORLD_ACTOR_SYSTEM_OVERLAY_CFLAGS) \
		-I$(INCLUDE_SUBDIR) -c $< -o $@.tmp
	$(OBJCOPY) --redefine-sym memset=OverworldEmoteSlots_StockMemset $@.tmp $@
	@rm -f $@.tmp

$(BUILD)/overworld_emote_slots_admission.o: lib/overworld/overworld_emote_slots_admission.s \
        $(BUILD)/.compile-config overlays.mk | $(BUILD) venv toolchain-preflight
	$(AS) $(ASFLAGS) $< -o $@

$(BUILD)/overworld_emote_slots_imports.o: lib/overworld/overworld_emote_slots_imports.s \
        $(BUILD)/.compile-config overlays.mk | $(BUILD) venv toolchain-preflight
	$(AS) $(ASFLAGS) $< -o $@

-include $(BUILD)/overworld_emote_slots.d

OVERWORLD_CHAIN_PUBLICATION_OBJS := $(BUILD)/overworld_mount_chain_overlay/overworld_condition_publication_native.o

$(OVERWORLD_CHAIN_PUBLICATION_OBJS): lib/overworld/overworld_condition_publication_native.c \
        $(BUILD)/.compile-config overlays.mk | $(BUILD)/overworld_mount_chain_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) \
		-DOVERWORLD_CONDITION_PUBLICATION_CHAIN=1 -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_follower_selector_overlay/overworld_condition_publication_native.o: \
        lib/overworld/overworld_condition_publication_native.c $(BUILD)/.compile-config overlays.mk \
        | $(BUILD)/overworld_follower_selector_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) \
		-DOVERWORLD_CONDITION_PUBLICATION_SELECTOR=1 -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_follower_selector_overlay/overworld_condition_publication_imports.o: \
        lib/overworld/overworld_condition_publication_imports.s $(BUILD)/.compile-config overlays.mk \
        | $(BUILD)/overworld_follower_selector_overlay toolchain-preflight
	$(AS) $(ASFLAGS) $< -o $@

-include $(OVERWORLD_CHAIN_PUBLICATION_OBJS:.o=.d)

OVERWORLD_FOLLOWER_SELECTOR_PORTABLE_OBJS := \
	$(BUILD)/overworld_follower_selector_overlay/overworld_vision.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_cache.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_service.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_field.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_condition_delegate.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_throw_observation_native.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_throw_binding_native.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_cache_imports.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_condition_publication_native.o \
	$(BUILD)/overworld_follower_selector_overlay/overworld_condition_publication_imports.o \
	$(BUILD)/overworld_notice_callers.o
OVERWORLD_TASK6_PORTABLE_OBJS := \
	$(BUILD)/pokemon_move_history_task6_overlay/overworld_role_controller.o
PLAYER_HEALTH_OVERLAY_OBJS := \
	$(BUILD)/player_health_overlay/player_health.o \
	$(BUILD)/player_health_overlay/player_health_model.o \
	$(BUILD)/player_health_overlay/player_health_recovery.o \
	$(BUILD)/player_health_overlay/player_health_save.o \
	$(BUILD)/player_health_overlay/player_health_contact.o \
	$(BUILD)/player_health_overlay/player_health_presentation.o

PLAYER_HEALTH_OVERLAY_OBJS += $(BUILD)/player_health_overlay/player_health_pokemon.o \
	$(BUILD)/overworld_combat_capsules.o

# Fully linked Wild read-only getter uses Helper151's existing private filler.
$(BUILD)/overworld_throw_height.o: $(BUILD)/overworld_wild_spawns_overlay_linked.o \
        scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_combat_capsules.py --build-dir $(BUILD) \
		--objcopy $(OBJCOPY) --throw-height-only

# Private Wild leaves use existing Selector152 filler without a link cycle.
$(BUILD)/overworld_notice_callers.o: $(BUILD)/overworld_wild_spawns_overlay_linked.o \
        scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_combat_capsules.py --build-dir $(BUILD) \
		--objcopy $(OBJCOPY) --notice-callers-only

# Link role adapters with their private dependencies, then retain only their
# resident code bytes in overlay 161. Their original overlay files stay fixed.
$(BUILD)/overworld_combat_capsules.o: $(BUILD)/overworld_wild_spawns_overlay_linked.o \
		$(BUILD)/overworld_mount_overlay_linked.o scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_combat_capsules.py --build-dir $(BUILD) --objcopy $(OBJCOPY)

# Mount links its unchanged private leaves once; boot Action/Chain retain them.
$(BUILD)/overworld_mount_private_leaves.o: $(BUILD)/overworld_mount_overlay_linked.o \
		scripts/pack_overworld_combat_capsules.py | venv
	$(PYTHON) scripts/pack_overworld_combat_capsules.py --build-dir $(BUILD) \
		--objcopy $(OBJCOPY) --mount-leaves-only

OVERWORLD_ACTOR_SYSTEM_OVERLAY_CFLAGS := -fno-tree-dominator-opts -mcpu=arm946e-s -mtune=arm946e-s -march=armv5te
OVERWORLD_WILD_RUNTIME_OVERLAY_CFLAGS := -mcpu=arm946e-s -mtune=arm946e-s -march=armv5te
OVERWORLD_WILD_SPAWNS_OVERLAY_CFLAGS := -frename-registers -fno-inline-small-functions -finline-functions-called-once -fno-partial-inlining -fno-short-enums -fno-tree-dominator-opts -fno-tree-forwprop -fno-tree-loop-ivcanon -fno-tree-loop-im -fmove-loop-invariants -fno-ipa-sra -fno-expensive-optimizations -fno-early-inlining -fno-schedule-insns2 -fno-ipa-pta -ftree-tail-merge -fno-tree-bit-ccp -fjump-tables -finline-limit=0 -mcpu=arm946e-s -mtune=arm946e-s -march=armv5te
OVERWORLD_ACTOR_HOP_PLANNER_CFLAGS := -mcpu=arm946e-s -mtune=arm946e-s -march=armv5te
OVERWORLD_WILD_HELPER_OVERLAY_CFLAGS := -fno-tree-dominator-opts -frename-registers -mcpu=arm946e-s -mtune=arm946e-s -march=armv5te
FIELD_ENEMY_PARTY_CFLAGS := -fconserve-stack
FIELD_MAP_TELEPORT_CFLAGS := -fno-tree-forwprop
OVERWORLD_WILD_SPAWNS_OVERLAY_LDFLAGS :=
OVERWORLD_WILD_HELPER_OVERLAY_LDFLAGS := --wrap=memset --wrap=__gnu_thumb1_case_uqi --wrap=__gnu_thumb1_case_uhi

INDIVIDUAL := individual
OVERLAYS := $(filter-out $(INDIVIDUAL) $(shell cd $(C_SUBDIR); ls *.*),$(shell cd $(C_SUBDIR); ls))

INDIVIDUAL_OVERLAYS = $(basename $(notdir $(wildcard $(C_SUBDIR)/$(INDIVIDUAL)/*.c)))

$(BUILD)/overworld_actor_system_overlay/overworld_behavior_resolver.o: \
		lib/overworld/overworld_behavior_resolver_actor_stub.c $(BUILD)/.compile-config \
		| $(BUILD)/overworld_actor_system_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -fno-tree-forwprop \
		-fno-inline-small-functions -fno-expensive-optimizations \
		-mcpu=arm946e-s -mtune=arm946e-s -march=armv5te \
		-I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_actor_system_overlay/overworld_behavior_condition_adapter.o: \
		lib/overworld/overworld_behavior_condition_adapter.c $(BUILD)/.compile-config \
		| $(BUILD)/overworld_actor_system_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -ffunction-sections \
		-fno-tree-forwprop -fno-tree-dominator-opts \
		-fno-inline-small-functions -frename-registers \
		-mcpu=arm946e-s -mtune=arm946e-s -march=armv5te \
		-I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_field.o: $(OVERWORLD_QUERY_CODE_ADDON_HEADER)

$(BUILD)/overworld_follower_selector_overlay/overworld_behavior_condition_runtime.o: \
		lib/overworld/overworld_behavior_condition_runtime.c \
		lib/overworld/overworld_behavior_conditions.c \
		lib/overworld/overworld_vision.c $(BUILD)/.compile-config \
		| $(BUILD)/overworld_follower_selector_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -ffunction-sections \
		-fno-tree-forwprop -fno-inline-small-functions \
		-fno-tree-sink -fno-tree-coalesce-vars -fno-ipa-pure-const \
		-mcpu=arm946e-s -mtune=arm946e-s -march=armv5te \
		-frename-registers -fno-tree-dominator-opts \
		-fno-tree-tail-merge -fno-ipa-sra -fexpensive-optimizations \
		-fno-schedule-insns2 -fno-tree-bit-ccp -fno-if-conversion \
		-fno-tree-fre -fno-code-hoisting -fno-tree-reassoc \
		-fno-tree-pre -fno-expensive-optimizations \
		-DOVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME=1 \
		-I$(INCLUDE_SUBDIR) -c $< -o $@

OVERWORLD_FOLLOWER_SELECTOR_QUERY_C_OBJS := $(filter-out \
    $(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_cache_imports.o,\
    $(filter $(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon%.o,\
        $(OVERWORLD_FOLLOWER_SELECTOR_PORTABLE_OBJS)))

$(OVERWORLD_FOLLOWER_SELECTOR_QUERY_C_OBJS): $(BUILD)/overworld_follower_selector_overlay/%.o: \
        lib/overworld/%.c $(BUILD)/.compile-config overlays.mk \
		| $(BUILD)/overworld_follower_selector_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -ffunction-sections \
		-mcpu=arm946e-s -mtune=arm946e-s -march=armv5te \
		-I$(INCLUDE_SUBDIR) -I$(OVERWORLD_QUERY_CODE_ADDON_DIR) -c $< -o $@

$(BUILD)/overworld_follower_selector_overlay/overworld_vision.o: lib/overworld/overworld_vision.c \
		$(BUILD)/.compile-config | $(BUILD)/overworld_follower_selector_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -ffunction-sections \
		-I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_follower_selector_overlay/overworld_throw_observation_native.o: \
		lib/overworld/overworld_throw_observation_native.c $(BUILD)/.compile-config overlays.mk \
		| $(BUILD)/overworld_follower_selector_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_follower_selector_overlay/overworld_throw_binding_native.o: \
		lib/overworld/overworld_throw_binding_native.c $(BUILD)/.compile-config overlays.mk \
		| $(BUILD)/overworld_follower_selector_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_follower_selector_overlay/overworld_query_code_addon_cache_imports.o: \
		lib/overworld/overworld_query_code_addon_cache_imports.s $(BUILD)/.compile-config \
		| $(BUILD)/overworld_follower_selector_overlay toolchain-preflight
	$(AS) $(ASFLAGS) $< -o $@

$(BUILD)/overworld_actor_system_overlay/overworld_motion_model.o: \
		lib/overworld/overworld_motion_model.c $(BUILD)/.compile-config overlays.mk \
		| $(BUILD)/overworld_actor_system_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -ffunction-sections -I$(INCLUDE_SUBDIR) -Isrc/pokemon_move_history_task6_overlay -c $< -o $@

$(BUILD)/overworld_actor_system_overlay/overworld_actor_transition_model.o: \
		lib/overworld/overworld_actor_transition_model.c $(BUILD)/.compile-config \
		| $(BUILD)/overworld_actor_system_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/overworld_actor_system_overlay/overworld_population_model.o: \
		lib/overworld/overworld_population_model.c $(BUILD)/.compile-config \
		| $(BUILD)/overworld_actor_system_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/pokemon_move_history_task6_overlay/overworld_role_controller.o: \
		lib/overworld/overworld_role_controller.c $(BUILD)/.compile-config \
		| $(BUILD)/pokemon_move_history_task6_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -ffunction-sections \
		-I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/player_health_overlay/player_health.o: src/player_health.c \
		$(BUILD)/.compile-config | $(BUILD)/player_health_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/player_health_overlay/player_health_model.o: \
		lib/overworld/player_health_model.c $(BUILD)/.compile-config \
		| $(BUILD)/player_health_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/player_health_overlay/player_health_recovery.o: \
		src/player_health_recovery.c $(BUILD)/.compile-config \
		| $(BUILD)/player_health_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/player_health_overlay/player_health_save.o: \
		src/player_health_save.c $(BUILD)/.compile-config \
		| $(BUILD)/player_health_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/player_health_overlay/player_health_contact.o: \
		src/player_health_contact.c $(BUILD)/.compile-config \
		| $(BUILD)/player_health_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/player_health_overlay/player_health_presentation.o: \
		src/player_health_presentation.c $(BUILD)/.compile-config \
		| $(BUILD)/player_health_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

$(BUILD)/player_health_overlay/player_health_pokemon.o: \
		src/player_health_pokemon.c $(BUILD)/.compile-config \
		| $(BUILD)/player_health_overlay venv toolchain-preflight
	$(CC) -MMD -MF $(basename $@).d $(CFLAGS) -I$(INCLUDE_SUBDIR) -c $< -o $@

-include $(BUILD)/overworld_actor_system_overlay/overworld_behavior_resolver.d
-include $(BUILD)/overworld_actor_system_overlay/overworld_behavior_condition_adapter.d
-include $(OVERWORLD_FOLLOWER_SELECTOR_PORTABLE_OBJS:.o=.d)
-include $(BUILD)/overworld_actor_system_overlay/overworld_motion_model.d
-include $(BUILD)/overworld_actor_system_overlay/overworld_actor_transition_model.d
-include $(BUILD)/overworld_actor_system_overlay/overworld_population_model.d
-include $(BUILD)/pokemon_move_history_task6_overlay/overworld_role_controller.d
-include $(BUILD)/player_health_overlay/player_health.d
-include $(BUILD)/player_health_overlay/player_health_model.d
-include $(BUILD)/player_health_overlay/player_health_recovery.d
-include $(BUILD)/player_health_overlay/player_health_save.d
-include $(BUILD)/player_health_overlay/player_health_contact.d
-include $(BUILD)/player_health_overlay/player_health_presentation.d
-include $(BUILD)/player_health_overlay/player_health_pokemon.d

# everything is expanded because it was not working for me otherwise
# this is aggressively defined but works.  in order to add a new overlay, you just have to add to the top now.
define OVERLAY_DEFINE

LDFLAGS_$1 = rom_gen.ld -T $(C_SUBDIR)/$1/linker.ld

$1_LINK = $(BUILD)/$1_linked.o
$1_OUTPUT = $(BUILD)/output_$1.bin
OVERLAY_OUTPUTS += $(BUILD)/output_$1.bin
LINKED_OUTPUTS += $(BUILD)/$1_linked.o
CODE_BUILD_DIRS += $(BUILD)/$1

$1_C_SRCS := $(wildcard $(C_SUBDIR)/$1/*.c)
ALL_C_SRCS += $(wildcard $(C_SUBDIR)/$1/*.c)
$1_C_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c))
$1_ASM_SRCS := $(wildcard $(ASM_SUBDIR)/$1/*.s)
ALL_ASM_SRCS += $(wildcard $(ASM_SUBDIR)/$1/*.s)
$1_ASM_OBJS := $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s))
$1_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_actor_system_overlay,$1),$(OVERWORLD_ACTOR_SYSTEM_PORTABLE_OBJS)) $(if $(filter overworld_mount_chain_overlay,$1),$(OVERWORLD_CHAIN_PUBLICATION_OBJS)) $(if $(filter overworld_mount_action_overlay overworld_mount_chain_overlay,$1),$(BUILD)/overworld_mount_private_leaves.o) $(if $(filter overworld_follower_selector_overlay,$1),$(OVERWORLD_FOLLOWER_SELECTOR_PORTABLE_OBJS)) $(if $(filter pokemon_move_history_task6_overlay,$1),$(OVERWORLD_TASK6_PORTABLE_OBJS)) $(if $(filter player_health_overlay,$1),$(PLAYER_HEALTH_OVERLAY_OBJS)) $(if $(filter field,$1),$(BUILD)/overworld_field_cargo_observation.o) $(if $(filter overworld_wild_helper_overlay,$1),$(BUILD)/overworld_throw_height.o) $(if $(filter field overworld_actor_system_overlay overworld_mount_overlay overworld_mount_chain_overlay overworld_mount_action_overlay overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_follower_release_overlay2 overworld_follower_selector_overlay overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay player_health_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP))


$(BUILD)/$1_linked.o:$(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_actor_system_overlay,$1),$(OVERWORLD_ACTOR_SYSTEM_PORTABLE_OBJS)) $(if $(filter overworld_mount_chain_overlay,$1),$(OVERWORLD_CHAIN_PUBLICATION_OBJS)) $(if $(filter overworld_mount_action_overlay overworld_mount_chain_overlay,$1),$(BUILD)/overworld_mount_private_leaves.o) $(if $(filter overworld_follower_selector_overlay,$1),$(OVERWORLD_FOLLOWER_SELECTOR_PORTABLE_OBJS)) $(if $(filter pokemon_move_history_task6_overlay,$1),$(OVERWORLD_TASK6_PORTABLE_OBJS)) $(if $(filter player_health_overlay,$1),$(PLAYER_HEALTH_OVERLAY_OBJS)) $(if $(filter field,$1),$(BUILD)/overworld_field_cargo_observation.o) $(if $(filter overworld_wild_helper_overlay,$1),$(BUILD)/overworld_throw_height.o) $(if $(filter field overworld_actor_system_overlay overworld_mount_overlay overworld_mount_chain_overlay overworld_mount_action_overlay overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_follower_release_overlay2 overworld_follower_selector_overlay overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay player_health_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP)) rom_gen.ld $(C_SUBDIR)/$1/linker.ld
	@rm -f $(BUILD)/$1_linked.o.tmp
	$(LD) rom_gen.ld -T $(C_SUBDIR)/$1/linker.ld $(if $(filter overworld_wild_spawns_overlay,$1),$(OVERWORLD_WILD_SPAWNS_OVERLAY_LDFLAGS),$(if $(filter overworld_wild_helper_overlay,$1),$(OVERWORLD_WILD_HELPER_OVERLAY_LDFLAGS),)) -o $(BUILD)/$1_linked.o.tmp $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_actor_system_overlay,$1),$(OVERWORLD_ACTOR_SYSTEM_PORTABLE_OBJS)) $(if $(filter overworld_mount_chain_overlay,$1),$(OVERWORLD_CHAIN_PUBLICATION_OBJS)) $(if $(filter overworld_mount_action_overlay overworld_mount_chain_overlay,$1),$(BUILD)/overworld_mount_private_leaves.o) $(if $(filter overworld_follower_selector_overlay,$1),$(OVERWORLD_FOLLOWER_SELECTOR_PORTABLE_OBJS)) $(if $(filter pokemon_move_history_task6_overlay,$1),$(OVERWORLD_TASK6_PORTABLE_OBJS)) $(if $(filter player_health_overlay,$1),$(PLAYER_HEALTH_OVERLAY_OBJS)) $(if $(filter field,$1),$(BUILD)/overworld_field_cargo_observation.o) $(if $(filter overworld_wild_helper_overlay,$1),$(BUILD)/overworld_throw_height.o) $(if $(filter field overworld_actor_system_overlay overworld_mount_overlay overworld_mount_chain_overlay overworld_mount_action_overlay overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_follower_release_overlay2 overworld_follower_selector_overlay overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay player_health_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP)) && mv $(BUILD)/$1_linked.o.tmp $(BUILD)/$1_linked.o

$(BUILD)/output_$1.bin:$(BUILD)/$1_linked.o $(if $(filter overworld_wild_spawns_overlay overworld_mount_overlay overworld_actor_system_overlay,$1),overlays.mk)
	$(OBJCOPY) -O binary $(if $(filter overworld_wild_spawns_overlay,$1),--remove-section=.overworld_actor_slam_jump --remove-section=.overworld_actor_pickup_cancel --remove-section=.overworld_wild_notice_callers --remove-section=.overworld_wild_combat --remove-section=.overworld_wild_combat_tail --remove-section=.overworld_wild_carrier_hit --remove-section=.overworld_field_wild_walk_output --remove-section=.overworld_field_wild_policy_init --remove-section=.overworld_field_wild_route_base_y --remove-section=.overworld_field_wild_hop_support --remove-section=.overworld_field_wild_cargo_observation --remove-section=.overworld_wild_throw_height --remove-section=.overworld_wild_teleport_read --remove-section=.overworld_wild_cleanup_task --remove-section=.overworld_wild_cleanup_hop_request --remove-section=.overworld_wild_cleanup_progress --remove-section=.overworld_wild_cleanup_spawn --remove-section=.overworld_wild_cleanup_presentation) $(if $(filter overworld_mount_overlay,$1),--remove-section=.overworld_mount_combat --remove-section=.overworld_mount_combat_tail --remove-section=.overworld_field_mount_hop_tick --remove-section=.overworld_mount_private_terrain_idle --remove-section=.overworld_mount_private_inspect) $(if $(filter overworld_actor_system_overlay,$1),--remove-section=.overworld_emote_initialize --remove-section=.overworld_emote_release --remove-section=.overworld_emote_destroy) $(if $(filter player_health_overlay,$1),--remove-section=.overworld_field_walk_input_tuning) $(if $(filter pokemon_move_history_overlay,$1),--remove-section=.overworld_field_spawn_orphans) $(if $(filter overworld_follower_selector_overlay,$1),--remove-section=.overworld_throw_binding_refresh) $(BUILD)/$1_linked.o $(BUILD)/output_$1.bin

endef
$(foreach overlay, $(OVERLAYS), $(eval $(call OVERLAY_DEFINE,$(overlay))))


CODE_BUILD_DIRS += $(BUILD)/$(INDIVIDUAL)

rom_gen_battle.ld: $(battle_LINK) $(battle_OUTPUT) rom_gen.ld | venv
	cp rom_gen.ld rom_gen_battle.ld
	$(PYTHON) scripts/generate_ld.py rom_gen_battle.ld $(battle_LINK)


define INDIVIDUAL_OVERLAY_DEFINE

LDFLAGS_$1 = rom_gen_battle.ld -T $(C_SUBDIR)/$(INDIVIDUAL)/$1.ld

$1_LINK = $(BUILD)/$1_linked.o
$1_OUTPUT = $(BUILD)/output_$1.bin
OVERLAY_OUTPUTS += $(BUILD)/output_$1.bin
LINKED_OUTPUTS += $(BUILD)/$1_linked.o

$1_C_SRCS := $(C_SUBDIR)/$(INDIVIDUAL)/$1.c
ALL_C_SRCS += $(C_SUBDIR)/$(INDIVIDUAL)/$1.c
$1_C_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c)
$1_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c) $(THUMB_HELP)

$(BUILD)/$1_linked.o:$(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c) $(THUMB_HELP) rom_gen_battle.ld $(C_SUBDIR)/$(INDIVIDUAL)/linker/$1.ld
	@rm -f $(BUILD)/$1_linked.o.tmp
	$(LD) rom_gen_battle.ld -T $(C_SUBDIR)/$(INDIVIDUAL)/linker/$1.ld -o $(BUILD)/$1_linked.o.tmp $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c) $(THUMB_HELP) && mv $(BUILD)/$1_linked.o.tmp $(BUILD)/$1_linked.o

$(BUILD)/output_$1.bin:$(BUILD)/$1_linked.o
	$(OBJCOPY) -O binary $(BUILD)/$1_linked.o $(BUILD)/output_$1.bin

endef
$(foreach overlay, $(INDIVIDUAL_OVERLAYS), $(eval $(call INDIVIDUAL_OVERLAY_DEFINE,$(overlay))))

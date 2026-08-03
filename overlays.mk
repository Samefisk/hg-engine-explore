# macros for overlay definition that automatically grab everything that we need from the folders provided
CODE_BUILD_DIRS += $(BUILD)
THUMB_HELP := $(BUILD)/thumb_help.o
LINKED_OUTPUTS = build/linked.o

OVERWORLD_WILD_SPAWNS_OVERLAY_CFLAGS := -fmerge-all-constants -frename-registers -fno-ipa-pta -fno-expensive-optimizations -fno-tree-dominator-opts -fno-if-conversion -fno-tree-pre -fno-tree-copy-prop -fno-guess-branch-probability -fno-schedule-insns2 -fno-early-inlining -fno-tree-loop-ivcanon -fno-move-loop-invariants -fno-tree-sra -fno-tree-dce -fno-tree-ch -finline-limit=30
OVERWORLD_WILD_HELPER_OVERLAY_CFLAGS := -frename-registers -fno-inline-small-functions -fno-expensive-optimizations
OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_CFLAGS := -fmerge-all-constants -fno-tree-dce -fno-tree-sink -fno-cse-follow-jumps
OVERWORLD_WILD_RUNTIME_LAYERS_OVERLAY_CFLAGS := -frename-registers \
    -fno-tree-dominator-opts -fno-inline-functions-called-once \
    -fno-tree-sra -fno-tree-vrp -fno-ipa-cp \
    -fno-guess-branch-probability -fno-expensive-optimizations \
    -DOW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
OVERWORLD_WILD_RUNTIME_TIMERS_OVERLAY_CFLAGS := -frename-registers \
    -fno-tree-dominator-opts -fno-inline-functions-called-once \
    -fno-tree-sra -fno-tree-vrp -fno-ipa-cp
OVERWORLD_WILD_RUNTIME_SYMBOLS := $(BUILD)/pokemon_move_history_task6_overlay_task7_runtime_symbols.o
OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS := $(BUILD)/overworld_wild_runtime_overlay_catalog_symbols.o
OVERWORLD_WILD_TASK8_SYMBOLS := $(BUILD)/overworld_wild_runtime_layers_overlay_task8_symbols.o
OVERWORLD_WILD_TIMER_SYMBOLS := $(BUILD)/overworld_wild_runtime_timers_overlay_timer_symbols.o
OVERWORLD_WILD_LAYERS_OBJECT := $(BUILD)/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.o
OVERWORLD_WILD_TIMERS_OBJECT := $(BUILD)/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.o
OVERWORLD_WILD_V40_SCALAR_SYMBOLS := $(BUILD)/overworld_wild_runtime_layers_overlay/owbd_v40_scalar_symbols.o
OVERWORLD_WILD_SPAWNS_OVERLAY_LDFLAGS := --just-symbols=$(OVERWORLD_WILD_RUNTIME_SYMBOLS) --just-symbols=$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS) --just-symbols=$(OVERWORLD_WILD_TASK8_SYMBOLS) --just-symbols=$(OVERWORLD_WILD_TIMER_SYMBOLS) --wrap=memcpy --wrap=memset --wrap=__gnu_thumb1_case_uqi --wrap=__gnu_thumb1_case_sqi --wrap=__gnu_thumb1_case_uhi --wrap=__gnu_thumb1_case_shi
OVERWORLD_WILD_HELPER_OVERLAY_LDFLAGS := --wrap=memset --wrap=__gnu_thumb1_case_uqi --wrap=__gnu_thumb1_case_uhi
OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_LDFLAGS := --just-symbols=$(BUILD)/pokemon_move_history_task6_overlay_linked.o --just-symbols=$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS)
POKEMON_MOVE_HISTORY_TASK6_OVERLAY_LDFLAGS := --just-symbols=$(OVERWORLD_WILD_TASK8_SYMBOLS) --wrap=memset
OVERWORLD_WILD_RUNTIME_LAYERS_OVERLAY_LDFLAGS := --just-symbols=$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS) --just-symbols=$(OVERWORLD_WILD_V40_SCALAR_SYMBOLS)

INDIVIDUAL := individual
OVERLAYS := $(filter-out $(INDIVIDUAL) overworld_wild_runtime_overlay overworld_wild_runtime_layers_overlay overworld_wild_runtime_timers_overlay $(shell cd $(C_SUBDIR); ls *.*),$(shell cd $(C_SUBDIR); ls))

INDIVIDUAL_OVERLAYS = $(basename $(notdir $(wildcard $(C_SUBDIR)/$(INDIVIDUAL)/*.c)))

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
$1_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_wild_runtime_layers_overlay,$1),$(OVERWORLD_WILD_LAYERS_OBJECT),) $(if $(filter overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_wild_behavior_validator_overlay overworld_wild_runtime_overlay overworld_wild_runtime_layers_overlay overworld_follower_release_overlay2 overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP))


$(BUILD)/$1_linked.o:$(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_wild_runtime_layers_overlay,$1),$(OVERWORLD_WILD_LAYERS_OBJECT),) $(if $(filter overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_wild_behavior_validator_overlay overworld_wild_runtime_overlay overworld_wild_runtime_layers_overlay overworld_follower_release_overlay2 overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP)) rom_gen.ld $(C_SUBDIR)/$1/linker.ld
	$(LD) rom_gen.ld -T $(C_SUBDIR)/$1/linker.ld $(if $(filter overworld_wild_spawns_overlay,$1),$(OVERWORLD_WILD_SPAWNS_OVERLAY_LDFLAGS),$(if $(filter overworld_wild_helper_overlay,$1),$(OVERWORLD_WILD_HELPER_OVERLAY_LDFLAGS),$(if $(filter overworld_wild_behavior_validator_overlay,$1),$(OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_LDFLAGS),$(if $(filter pokemon_move_history_task6_overlay,$1),$(POKEMON_MOVE_HISTORY_TASK6_OVERLAY_LDFLAGS),$(if $(filter overworld_wild_runtime_layers_overlay,$1),$(OVERWORLD_WILD_RUNTIME_LAYERS_OVERLAY_LDFLAGS),))))) -o $(BUILD)/$1_linked.o $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_wild_runtime_layers_overlay,$1),$(OVERWORLD_WILD_LAYERS_OBJECT),) $(if $(filter overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_wild_behavior_validator_overlay overworld_wild_runtime_overlay overworld_wild_runtime_layers_overlay overworld_follower_release_overlay2 overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP))

$(BUILD)/output_$1.bin:$(BUILD)/$1_linked.o $(if $(filter overworld_wild_spawns_overlay overworld_wild_behavior_validator_overlay overworld_wild_runtime_overlay overworld_wild_runtime_layers_overlay,$1),scripts/verify_overworld_wild_overlay_size.py,)
	$(OBJCOPY) -O binary $(BUILD)/$1_linked.o $(BUILD)/output_$1.bin
	$(if $(filter overworld_wild_spawns_overlay,$1),$(PYTHON_NO_VENV) scripts/verify_overworld_wild_overlay_size.py $(BUILD)/$1_linked.o --binary $(BUILD)/output_$1.bin --overlay 149,)
	$(if $(filter overworld_wild_behavior_validator_overlay,$1),$(PYTHON_NO_VENV) scripts/verify_overworld_wild_overlay_size.py $(BUILD)/$1_linked.o --binary $(BUILD)/output_$1.bin --overlay 156,)
	$(if $(filter overworld_wild_runtime_overlay,$1),$(PYTHON_NO_VENV) scripts/verify_overworld_wild_overlay_size.py $(BUILD)/$1_linked.o --binary $(BUILD)/output_$1.bin --overlay 157,)
	$(if $(filter overworld_wild_runtime_layers_overlay,$1),$(PYTHON_NO_VENV) scripts/verify_overworld_wild_overlay_size.py $(BUILD)/$1_linked.o --binary $(BUILD)/output_$1.bin --overlay 158,)

endef
$(foreach overlay, $(OVERLAYS), $(eval $(call OVERLAY_DEFINE,$(overlay))))

# The resident runtime split is intentionally explicit: overlay 157 owns the
# validated catalog, overlay 158 owns mutation/composition, and overlay 159
# owns the public timer scheduler surface.
overworld_wild_runtime_overlay_LINK = $(BUILD)/overworld_wild_runtime_overlay_linked.o
overworld_wild_runtime_overlay_OUTPUT = $(BUILD)/output_overworld_wild_runtime_overlay.bin
overworld_wild_runtime_layers_overlay_LINK = $(BUILD)/overworld_wild_runtime_layers_overlay_linked.o
overworld_wild_runtime_layers_overlay_OUTPUT = $(BUILD)/output_overworld_wild_runtime_layers_overlay.bin
overworld_wild_runtime_timers_overlay_LINK = $(BUILD)/overworld_wild_runtime_timers_overlay_linked.o
overworld_wild_runtime_timers_overlay_OUTPUT = $(BUILD)/output_overworld_wild_runtime_timers_overlay.bin
OVERLAY_OUTPUTS += $(overworld_wild_runtime_overlay_OUTPUT) $(overworld_wild_runtime_layers_overlay_OUTPUT) $(overworld_wild_runtime_timers_overlay_OUTPUT)
LINKED_OUTPUTS += $(overworld_wild_runtime_overlay_LINK) $(overworld_wild_runtime_layers_overlay_LINK) $(overworld_wild_runtime_timers_overlay_LINK)
CODE_BUILD_DIRS += $(BUILD)/overworld_wild_runtime_overlay $(BUILD)/overworld_wild_runtime_layers_overlay $(BUILD)/overworld_wild_runtime_timers_overlay
ALL_C_SRCS += $(C_SUBDIR)/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c
ALL_C_SRCS += $(C_SUBDIR)/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.c
ALL_C_SRCS += $(C_SUBDIR)/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.c
ALL_ASM_SRCS += $(ASM_SUBDIR)/overworld_wild_runtime_layers_overlay/owbd_v40_scalar_symbols.s

$(overworld_wild_runtime_overlay_LINK): \
    $(BUILD)/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.o \
    $(OVERWORLD_WILD_V40_SCALAR_SYMBOLS) \
    rom_gen.ld src/overworld_wild_runtime_overlay/linker.ld
	$(LD) rom_gen.ld -T src/overworld_wild_runtime_overlay/linker.ld \
		--just-symbols=$(OVERWORLD_WILD_V40_SCALAR_SYMBOLS) -o $@ $<

$(overworld_wild_runtime_overlay_OUTPUT): $(overworld_wild_runtime_overlay_LINK) scripts/verify_overworld_wild_overlay_size.py
	$(OBJCOPY) -O binary $< $@
	$(PYTHON_NO_VENV) scripts/verify_overworld_wild_overlay_size.py $< --binary $@ --overlay 157

$(overworld_wild_runtime_layers_overlay_LINK): \
    $(OVERWORLD_WILD_LAYERS_OBJECT) $(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS) \
    $(OVERWORLD_WILD_V40_SCALAR_SYMBOLS) \
    rom_gen.ld src/overworld_wild_runtime_layers_overlay/linker.ld
	$(LD) rom_gen.ld -T src/overworld_wild_runtime_layers_overlay/linker.ld \
		--just-symbols=$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS) \
		--just-symbols=$(OVERWORLD_WILD_V40_SCALAR_SYMBOLS) \
		-o $@ $(OVERWORLD_WILD_LAYERS_OBJECT)

$(overworld_wild_runtime_layers_overlay_OUTPUT): $(overworld_wild_runtime_layers_overlay_LINK) \
    $(overworld_wild_runtime_overlay_LINK) \
    $(BUILD)/pokemon_move_history_task6_overlay_linked.o \
    $(BUILD)/pokemon_move_history_task6_overlay/overworld_wild_behavior_support.o \
    $(OVERWORLD_WILD_TASK8_SYMBOLS) \
    $(OVERWORLD_WILD_RUNTIME_SYMBOLS) \
    $(BUILD)/overworld_wild_spawns_overlay_linked.o \
    $(OVERWORLD_WILD_V40_SCALAR_SYMBOLS) \
    scripts/verify_overworld_wild_overlay_size.py
	$(OBJCOPY) -O binary $< $@
	$(PYTHON_NO_VENV) scripts/verify_overworld_wild_overlay_size.py $< \
		--binary $@ --overlay 158 \
		--task5-owner $(BUILD)/pokemon_move_history_task6_overlay_linked.o \
		--lifecycle-consumer $(BUILD)/pokemon_move_history_task6_overlay_linked.o \
		--lifecycle-object $(BUILD)/pokemon_move_history_task6_overlay/overworld_wild_behavior_support.o \
		--scalar-shard $(OVERWORLD_WILD_V40_SCALAR_SYMBOLS) \
		--catalog-owner $(overworld_wild_runtime_overlay_LINK) \
		--task8-carrier $(OVERWORLD_WILD_TASK8_SYMBOLS) \
		--runtime-carrier $(OVERWORLD_WILD_RUNTIME_SYMBOLS) \
		--spawns-consumer $(BUILD)/overworld_wild_spawns_overlay_linked.o

$(overworld_wild_runtime_timers_overlay_LINK): \
    $(OVERWORLD_WILD_TIMERS_OBJECT) $(OVERWORLD_WILD_TASK8_SYMBOLS) \
    rom_gen.ld src/overworld_wild_runtime_timers_overlay/linker.ld
	$(LD) rom_gen.ld -T src/overworld_wild_runtime_timers_overlay/linker.ld \
		--just-symbols=$(OVERWORLD_WILD_TASK8_SYMBOLS) \
		-o $@ $(OVERWORLD_WILD_TIMERS_OBJECT)

$(overworld_wild_runtime_timers_overlay_OUTPUT): $(overworld_wild_runtime_timers_overlay_LINK) \
    $(overworld_wild_runtime_layers_overlay_LINK) \
    $(OVERWORLD_WILD_TASK8_SYMBOLS) \
    $(OVERWORLD_WILD_TIMER_SYMBOLS) \
    scripts/verify_overworld_wild_overlay_size.py
	$(OBJCOPY) -O binary $< $@
	$(PYTHON_NO_VENV) scripts/verify_overworld_wild_overlay_size.py $< \
		--binary $@ --overlay 159 \
		--layers-owner $(overworld_wild_runtime_layers_overlay_LINK) \
		--task8-carrier $(OVERWORLD_WILD_TASK8_SYMBOLS) \
		--timer-carrier $(OVERWORLD_WILD_TIMER_SYMBOLS)

$(BUILD)/overworld_wild_behavior_validator_overlay_linked.o: \
    $(BUILD)/pokemon_move_history_task6_overlay_linked.o \
    $(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS)

$(BUILD)/pokemon_move_history_task6_overlay_linked.o: \
    $(OVERWORLD_WILD_TASK8_SYMBOLS)

$(BUILD)/overworld_wild_spawns_overlay_linked.o: \
    $(OVERWORLD_WILD_RUNTIME_SYMBOLS) \
    $(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS) \
    $(OVERWORLD_WILD_TASK8_SYMBOLS) \
    $(OVERWORLD_WILD_TIMER_SYMBOLS)

$(OVERWORLD_WILD_TASK8_SYMBOLS): \
    $(BUILD)/overworld_wild_runtime_layers_overlay_linked.o
	$(OBJCOPY) --strip-all \
		--keep-symbol=OverworldWildRuntime_HandleSlotGenerationWrap \
		--keep-symbol=OverworldWildRuntime_ClearSlotStorage \
		--keep-symbol=OverworldWildRuntime_InitializeStorage \
		--keep-symbol=OverworldWildRuntime_BindPrivateIdentity \
		--keep-symbol=OverworldWildRuntime_ApplyStackDelta \
		--keep-symbol=OverworldWildRuntime_Apply \
		--keep-symbol=OverworldWildRuntime_Replace \
		--keep-symbol=OverworldWildRuntime_Remove \
		--keep-symbol=OverworldWildRuntime_RemoveOwner \
		--keep-symbol=OverworldWildRuntime_ClearAllForSlot \
		--keep-symbol=OverworldWildRuntime_PrimeEffectiveCache \
		--keep-symbol=OverworldWildRuntime_GetEffectiveCache \
		--keep-symbol=OverworldWildRuntime_GetCapabilityMask \
		--keep-symbol=OverworldWildRuntime_GetProvenance \
		--keep-symbol=OverworldWildRuntime_ValidateTimerQueryInternal \
		--keep-symbol=OverworldWildRuntime_TimerExpiryTagInternal \
		--keep-symbol=OverworldWildRuntime_PreflightTimerExpiryInternal \
		--keep-symbol=OverworldWildRuntime_MakeTimerRemovalHandleInternal \
		--keep-symbol=OverworldWildRuntime_GetLayerCount \
		--keep-symbol=OverworldWildRuntime_GetLayerByIndex \
		--keep-symbol=OverworldWildRuntime_FindLayer \
		$< $@

$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS): \
    $(BUILD)/overworld_wild_runtime_overlay_linked.o
	$(OBJCOPY) --strip-all \
		--keep-symbol=OverworldWildBehavior_LoadValidatedBundle \
		--keep-symbol=OverworldWildBehavior_ReleaseValidatedBundle \
		--keep-symbol=OverworldWildBehavior_FreeValidatedBundle \
		--keep-symbol=OverworldWildRuntime_CopyInstalledDefinition \
		--keep-symbol=OverworldWildRuntime_ResolveInstalledTimerDefinition \
		--keep-symbol=OverworldWildRuntime_CopyInstalledCatalogIdentity \
		--keep-symbol=OverworldWildRuntime_MarkResidentCold \
		--keep-symbol=OverworldWildRuntime_CopyInstalledStaticComposition \
		--keep-symbol=OverworldWildRuntime_CopyInstalledStaticCache \
		--keep-symbol=OverworldWildRuntime_ResolveRetainedStaticCache \
		--keep-symbol=OverworldWildRuntime_ApplicabilityMatchesStaticCache \
		--keep-symbol=OverworldWildRuntime_ValidateStaticCache \
		--keep-symbol=OverworldWildRuntime_CopyInstalledResolvedNode \
		--keep-symbol=OverworldWildRuntime_CopyResolvedCachedNode \
		--keep-symbol=OverworldWildRuntime_CopyInstalledModifierOperations \
		--keep-symbol=OverworldWildRuntime_CountInstalledTiredTranslations \
		$< $@

$(BUILD)/overworld_wild_runtime_layers_overlay_linked.o: \
    $(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS)

$(OVERWORLD_WILD_TIMER_SYMBOLS): \
    $(BUILD)/overworld_wild_runtime_timers_overlay_linked.o
	$(OBJCOPY) --strip-all \
		--keep-symbol=OverworldWildRuntime_GetTimerCount \
		--keep-symbol=OverworldWildRuntime_GetTimerByIndex \
		--keep-symbol=OverworldWildRuntime_SetTimerPresentationGate \
		--keep-symbol=OverworldWildRuntime_TickCandidateTimers \
		--keep-symbol=OverworldWildRuntime_TickFrameTimers \
		--keep-symbol=OverworldWildRuntime_TickCompletedMovementTimers \
		--keep-symbol=OverworldWildRuntime_GetPendingTimerExpiryCount \
		--keep-symbol=OverworldWildRuntime_GetPendingTimerExpiryByIndex \
		--keep-symbol=OverworldWildRuntime_CommitTimerExpiry \
		$< $@

$(OVERWORLD_WILD_RUNTIME_SYMBOLS): \
    $(BUILD)/pokemon_move_history_task6_overlay_linked.o
	$(OBJCOPY) --strip-all \
		--keep-symbol=OverworldWildRuntime_Init \
		--keep-symbol=OverworldWildRuntime_DestructivelyInvalidateSlot \
		$< $@


CODE_BUILD_DIRS += $(BUILD)/$(INDIVIDUAL)

rom_gen_battle.ld:$(battle_LINK) $(battle_OUTPUT) rom_gen.ld
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

$(BUILD)/$1_linked.o:$(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c) $(THUMB_HELP) rom_gen_battle.ld
	$(LD) rom_gen_battle.ld -T $(C_SUBDIR)/$(INDIVIDUAL)/linker/$1.ld -o $(BUILD)/$1_linked.o $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c) $(THUMB_HELP)

$(BUILD)/output_$1.bin:$(BUILD)/$1_linked.o
	$(OBJCOPY) -O binary $(BUILD)/$1_linked.o $(BUILD)/output_$1.bin

endef
$(foreach overlay, $(INDIVIDUAL_OVERLAYS), $(eval $(call INDIVIDUAL_OVERLAY_DEFINE,$(overlay))))

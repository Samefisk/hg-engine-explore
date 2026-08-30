# macros for overlay definition that automatically grab everything that we need from the folders provided
CODE_BUILD_DIRS += $(BUILD)
THUMB_HELP := $(BUILD)/thumb_help.o
LINKED_OUTPUTS = build/linked.o

OVERWORLD_WILD_SPAWNS_OVERLAY_CFLAGS := -frename-registers -fno-inline-small-functions -fno-short-enums -fno-tree-dominator-opts -fno-tree-forwprop -fno-tree-loop-ivcanon
OVERWORLD_WILD_HELPER_OVERLAY_CFLAGS := -frename-registers -fno-inline-small-functions
OVERWORLD_WILD_SPAWNS_OVERLAY_LDFLAGS := --wrap=memcpy --wrap=memset --wrap=__gnu_thumb1_case_uqi --wrap=__gnu_thumb1_case_uhi --wrap=__gnu_thumb1_case_shi
OVERWORLD_WILD_HELPER_OVERLAY_LDFLAGS := --wrap=memset --wrap=__gnu_thumb1_case_uqi --wrap=__gnu_thumb1_case_uhi

INDIVIDUAL := individual
OVERLAYS := $(filter-out $(INDIVIDUAL) $(shell cd $(C_SUBDIR); ls *.*),$(shell cd $(C_SUBDIR); ls))

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
$1_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_follower_release_overlay2 overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP))


$(BUILD)/$1_linked.o:$(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_follower_release_overlay2 overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP)) rom_gen.ld
	$(LD) rom_gen.ld -T $(C_SUBDIR)/$1/linker.ld $(if $(filter overworld_wild_spawns_overlay,$1),$(OVERWORLD_WILD_SPAWNS_OVERLAY_LDFLAGS),$(if $(filter overworld_wild_helper_overlay,$1),$(OVERWORLD_WILD_HELPER_OVERLAY_LDFLAGS),)) -o $(BUILD)/$1_linked.o $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(wildcard $(C_SUBDIR)/$1/*.c)) $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(wildcard $(ASM_SUBDIR)/$1/*.s)) $(if $(filter overworld_wild_spawns_overlay overworld_wild_helper_overlay overworld_follower_release_overlay2 overworld_follower_selector_icons_overlay2 pokemon_move_history_overlay pokemon_move_history_task6_overlay summary_move_relearn_overlay,$1),,$(THUMB_HELP))

$(BUILD)/output_$1.bin:$(BUILD)/$1_linked.o
	$(OBJCOPY) -O binary $(BUILD)/$1_linked.o $(BUILD)/output_$1.bin

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

$(BUILD)/$1_linked.o:$(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c) $(THUMB_HELP) rom_gen_battle.ld
	$(LD) rom_gen_battle.ld -T $(C_SUBDIR)/$(INDIVIDUAL)/linker/$1.ld -o $(BUILD)/$1_linked.o $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SUBDIR)/$(INDIVIDUAL)/$1.c) $(THUMB_HELP)

$(BUILD)/output_$1.bin:$(BUILD)/$1_linked.o
	$(OBJCOPY) -O binary $(BUILD)/$1_linked.o $(BUILD)/output_$1.bin

endef
$(foreach overlay, $(INDIVIDUAL_OVERLAYS), $(eval $(call INDIVIDUAL_OVERLAY_DEFINE,$(overlay))))

# can handle all of these like narcs because a028 is built unconditionally

HIDDEN_ABILITY_TABLE_TARGET := $(BUILD)/a028/9_07
HIDDEN_ABILITY_TABLE_DEPENDENCIES := data/HiddenAbilityTable.c
HIDDEN_ABILITY_TABLE_OBJS := $(patsubst data/%.c,build/%.o,$(HIDDEN_ABILITY_TABLE_DEPENDENCIES))
HIDDEN_ABILITY_TABLE_BIN := $(patsubst data/%.c,build/%.bin,$(HIDDEN_ABILITY_TABLE_DEPENDENCIES))

$(HIDDEN_ABILITY_TABLE_BIN): $(HIDDEN_ABILITY_TABLE_DEPENDENCIES)
	$(CC) $(CFLAGS) -c $< -o $(HIDDEN_ABILITY_TABLE_OBJS)
	$(OBJCOPY) -O binary $(HIDDEN_ABILITY_TABLE_OBJS) $@

NARC_FILES += $(HIDDEN_ABILITY_TABLE_BIN)

BASE_EXPERIENCE_TABLE_TARGET := $(BUILD)/a028/9_08
BASE_EXPERIENCE_TABLE_DEPENDENCIES := data/BaseExperienceTable.c
BASE_EXPERIENCE_TABLE_OBJS := $(patsubst data/%.c,build/%.o,$(BASE_EXPERIENCE_TABLE_DEPENDENCIES))
BASE_EXPERIENCE_TABLE_BIN := $(patsubst data/%.c,build/%.bin,$(BASE_EXPERIENCE_TABLE_DEPENDENCIES))

$(BASE_EXPERIENCE_TABLE_BIN): $(BASE_EXPERIENCE_TABLE_DEPENDENCIES)
	$(CC) $(CFLAGS) -c $< -o $(BASE_EXPERIENCE_TABLE_OBJS)
	$(OBJCOPY) -O binary $(BASE_EXPERIENCE_TABLE_OBJS) $@

NARC_FILES += $(BASE_EXPERIENCE_TABLE_BIN)

SPECIES_TO_OW_GFX_TARGET := $(BUILD)/a028/9_10
SPECIES_TO_OW_GFX_DEPENDENCIES := data/SpeciesToOWGfx.c
SPECIES_TO_OW_GFX_OBJS := $(patsubst data/%.c,build/%.o,$(SPECIES_TO_OW_GFX_DEPENDENCIES))
SPECIES_TO_OW_GFX_BIN := $(patsubst data/%.c,build/%.bin,$(SPECIES_TO_OW_GFX_DEPENDENCIES))

$(SPECIES_TO_OW_GFX_BIN): $(SPECIES_TO_OW_GFX_DEPENDENCIES)
	$(CC) $(CFLAGS) -c $< -o $(SPECIES_TO_OW_GFX_OBJS)
	$(OBJCOPY) -O binary $(SPECIES_TO_OW_GFX_OBJS) $@

NARC_FILES += $(SPECIES_TO_OW_GFX_BIN)


POKEFORMDATATBL_TARGET := $(BUILD)/a028/9_11
POKEFORMDATATBL_DEPENDENCIES := data/PokeFormDataTbl.c
POKEFORMDATATBL_OBJS := $(patsubst data/%.c,build/%.o,$(POKEFORMDATATBL_DEPENDENCIES))
POKEFORMDATATBL_BIN := $(patsubst data/%.c,build/%.bin,$(POKEFORMDATATBL_DEPENDENCIES))

$(POKEFORMDATATBL_BIN): $(POKEFORMDATATBL_DEPENDENCIES)
	$(CC) $(CFLAGS) -c $< -o $(POKEFORMDATATBL_OBJS)
	$(OBJCOPY) -O binary $(POKEFORMDATATBL_OBJS) $@

NARC_FILES += $(POKEFORMDATATBL_BIN)


FORMTOSPECIES_TARGET := $(BUILD)/a028/9_12
FORMTOSPECIES_DEPENDENCIES := data/FormToSpeciesMapping.c
FORMTOSPECIES_OBJS := $(patsubst data/%.c,build/%.o,$(FORMTOSPECIES_DEPENDENCIES))
FORMTOSPECIES_BIN := $(patsubst data/%.c,build/%.bin,$(FORMTOSPECIES_DEPENDENCIES))

$(FORMTOSPECIES_BIN): $(FORMTOSPECIES_DEPENDENCIES)
	$(CC) $(CFLAGS) -c $< -o $(FORMTOSPECIES_OBJS)
	$(OBJCOPY) -O binary $(FORMTOSPECIES_OBJS) $@

NARC_FILES += $(FORMTOSPECIES_BIN)


FORMREVERSION_TARGET := $(BUILD)/a028/9_13
FORMREVERSION_DEPENDENCIES := data/FormReversionMapping.c
FORMREVERSION_OBJS := $(patsubst data/%.c,build/%.o,$(FORMREVERSION_DEPENDENCIES))
FORMREVERSION_BIN := $(patsubst data/%.c,build/%.bin,$(FORMREVERSION_DEPENDENCIES))

$(FORMREVERSION_BIN): $(FORMREVERSION_DEPENDENCIES)
	$(CC) $(CFLAGS) -c $< -o $(FORMREVERSION_OBJS)
	$(OBJCOPY) -O binary $(FORMREVERSION_OBJS) $@

NARC_FILES += $(FORMREVERSION_BIN)


LEARNSETS_INPUT = data/learnsets/learnsets.json
LEARNSET_OUTPUT_DIR := build/learnset
LEARNSETS_HEADER := $(INCLUDE_SUBDIR)/constants/generated/learnsets.h
LEARNSETS_ARMIPS_CONSTANTS := armips/include/generated/levelup.s
MACHINELEARNSET_DEPENDENCIES := $(LEARNSET_OUTPUT_DIR)/MachineMoveLearnsets.c
TUTORLEARNSET_DEPENDENCIES := $(LEARNSET_OUTPUT_DIR)/TutorMoveLearnsets.c
LEVELUPLEARNSET_DEPENDENCIES := $(LEARNSET_OUTPUT_DIR)/LevelupLearnsets.c
EGGLEARNSET_DEPENDENCIES := $(LEARNSET_OUTPUT_DIR)/EggLearnsets.c
LEARNSETS_PRIMARY_OUTPUTS := \
	$(LEARNSETS_HEADER) \
	$(MACHINELEARNSET_DEPENDENCIES) \
	$(LEVELUPLEARNSET_DEPENDENCIES) \
	$(EGGLEARNSET_DEPENDENCIES) \
	$(TUTORLEARNSET_DEPENDENCIES)
LEARNSETS_ATOMIC_OUTPUTS := \
	$(LEARNSETS_PRIMARY_OUTPUTS) \
	$(LEARNSETS_ARMIPS_CONSTANTS)
LEARNSETS_COMPLETION_STAMP := $(LEARNSET_OUTPUT_DIR)/.learnsets-complete
LEARNSETS_GENERATOR_INPUTS := \
	$(LEARNSETS_INPUT) \
	scripts/build_learnsets.py \
	src/item.c \
	src/field/move_tutor.c \
	include/constants/species.h \
	include/constants/moves.h \
	data/FormToSpeciesMapping.c

.PHONY: learnsets-ensure
learnsets-ensure: $(LEARNSETS_GENERATOR_INPUTS) $(VENV_ACTIVATE)
	@echo "generating learnset data..."
	$(PYTHON) scripts/build_learnsets.py \
		--learnsets $(LEARNSETS_INPUT) \
		--machineout $(MACHINELEARNSET_DEPENDENCIES) \
		--levelupout $(LEVELUPLEARNSET_DEPENDENCIES) \
		--eggout $(EGGLEARNSET_DEPENDENCIES) \
		--tutorout $(TUTORLEARNSET_DEPENDENCIES) \
		--constantsout $(LEARNSETS_HEADER) \
		--levelupconstantsout $(LEARNSETS_ARMIPS_CONSTANTS) \
		--completion-stamp $(LEARNSETS_COMPLETION_STAMP)

.DELETE_ON_ERROR: $(LEARNSETS_COMPLETION_STAMP)
$(LEARNSETS_ATOMIC_OUTPUTS) $(LEARNSETS_COMPLETION_STAMP): | learnsets-ensure
	@test -s $@

MACHINELEARNSET_TARGET := $(BUILD)/a028/9_14
MACHINELEARNSET_OBJS := $(patsubst %.c,%.o,$(MACHINELEARNSET_DEPENDENCIES))
MACHINELEARNSET_BIN := $(patsubst $(LEARNSET_OUTPUT_DIR)/%.c,$(BUILD)/%.bin,$(MACHINELEARNSET_DEPENDENCIES))

$(MACHINELEARNSET_BIN): $(MACHINELEARNSET_DEPENDENCIES) $(LEARNSETS_HEADER)
	@echo "writing machine learnsets..."
	$(CC) $(CFLAGS) -c $(MACHINELEARNSET_DEPENDENCIES) -o $(MACHINELEARNSET_OBJS)
	$(OBJCOPY) -O binary $(MACHINELEARNSET_OBJS) $@

NARC_FILES += $(MACHINELEARNSET_BIN)


TUTORLEARNSET_TARGET := $(BUILD)/a028/9_15
TUTORLEARNSET_OBJS := $(patsubst %.c,%.o,$(TUTORLEARNSET_DEPENDENCIES))
TUTORLEARNSET_BIN := $(patsubst $(LEARNSET_OUTPUT_DIR)/%.c,$(BUILD)/%.bin,$(TUTORLEARNSET_DEPENDENCIES))

$(TUTORLEARNSET_BIN): $(TUTORLEARNSET_DEPENDENCIES) $(LEARNSETS_HEADER)
	@echo "writing tutor learnsets..."
	$(CC) $(CFLAGS) -c $(TUTORLEARNSET_DEPENDENCIES) -o $(TUTORLEARNSET_OBJS)
	$(OBJCOPY) -O binary $(TUTORLEARNSET_OBJS) $@

NARC_FILES += $(TUTORLEARNSET_BIN)

MOVE_RELEARN_PARENTS_TARGET := $(BUILD)/a028/9_20
MOVE_RELEARN_PARENTS_SOURCE := $(BUILD)/move_relearn/MoveRelearnParents.c
MOVE_RELEARN_PARENTS_OBJ := $(BUILD)/move_relearn/MoveRelearnParents.o
MOVE_RELEARN_PARENTS_BIN := $(BUILD)/move_relearn/MoveRelearnParents.bin

$(MOVE_RELEARN_PARENTS_SOURCE): scripts/build_move_relearn_parents.py armips/data/evodata.s include/constants/species.h asm/include/species.inc data/PokeFormDataTbl.c data/FormToSpeciesMapping.c
	$(PYTHON_NO_VENV) scripts/build_move_relearn_parents.py \
		--evodata armips/data/evodata.s \
		--species-header include/constants/species.h \
		--armips-species-header asm/include/species.inc \
		--form-data data/PokeFormDataTbl.c \
		--form-to-species data/FormToSpeciesMapping.c \
		--output $@

$(MOVE_RELEARN_PARENTS_BIN): $(MOVE_RELEARN_PARENTS_SOURCE)
	$(CC) $(CFLAGS) -c $< -o $(MOVE_RELEARN_PARENTS_OBJ)
	$(OBJCOPY) -O binary $(MOVE_RELEARN_PARENTS_OBJ) $@

NARC_FILES += $(MOVE_RELEARN_PARENTS_BIN)
REQUIRED_DIRECTORIES += $(BUILD)/move_relearn


LEVELUPLEARNSET_TARGET := $(FILESYS)/a/0/3/3
LEVELUPLEARNSET_DIR := $(BUILD)/a033
LEVELUPLEARNSET_NARC := $(BUILD_NARC)/a033.narc
LEVELUPLEARNSET_OBJS := $(patsubst %.c,%.o,$(LEVELUPLEARNSET_DEPENDENCIES))
LEVELUPLEARNSET_BIN := $(patsubst $(LEARNSET_OUTPUT_DIR)/%.c,$(LEVELUPLEARNSET_DIR)/%.bin,$(LEVELUPLEARNSET_DEPENDENCIES))

.DELETE_ON_ERROR: $(LEVELUPLEARNSET_NARC)
$(LEVELUPLEARNSET_NARC): $(LEARNSETS_HEADER) $(LEVELUPLEARNSET_DEPENDENCIES) $(BUILD_NARC)/a011.narc scripts/filter_levelup_learnsets.py scripts/create_narc_atomic.py tools/narcpy.py include/config.h include/battle.h armips/include/movemacros.s
	@echo "writing levelup moves..."
	$(CC) $(CFLAGS) -c $(LEVELUPLEARNSET_DEPENDENCIES) -o $(LEVELUPLEARNSET_OBJS)
	$(OBJCOPY) -O binary $(LEVELUPLEARNSET_OBJS) $(LEVELUPLEARNSET_BIN)
	$(PYTHON_NO_VENV) scripts/filter_levelup_learnsets.py \
		--learnsets $(LEVELUPLEARNSET_BIN) \
		--move-data-dir $(MOVEDATA_DIR) \
		--constants $(LEARNSETS_HEADER) \
		--config include/config.h \
		--battle-header include/battle.h \
		--move-macros armips/include/movemacros.s
	$(PYTHON) scripts/create_narc_atomic.py \
		--narcpy tools/narcpy.py \
		--source $(LEVELUPLEARNSET_DIR) \
		--output $@

NARC_FILES += $(LEVELUPLEARNSET_NARC)
REQUIRED_DIRECTORIES += $(LEVELUPLEARNSET_DIR)

EGGLEARNSET_TARGET := $(FILESYS)/a/2/2/9
EGGLEARNSET_NARC := $(BUILD_NARC)/a229.narc
EGGLEARNSET_OBJS := $(patsubst %.c,%.o,$(EGGLEARNSET_DEPENDENCIES))
EGGLEARNSET_BIN := $(patsubst $(LEARNSET_OUTPUT_DIR)/%.c,$(BUILD)/a229/%.bin,$(EGGLEARNSET_DEPENDENCIES))

$(EGGLEARNSET_NARC): $(EGGLEARNSET_DEPENDENCIES) $(LEARNSETS_HEADER)
	@echo "writing egg learnsets..."
	$(CC) $(CFLAGS) -c $(EGGLEARNSET_DEPENDENCIES) -o $(EGGLEARNSET_OBJS)
	$(OBJCOPY) -O binary $(EGGLEARNSET_OBJS) $(EGGLEARNSET_BIN)
	$(NARCHIVE) create $@ $(BUILD)/a229/ -nf

NARC_FILES += $(EGGLEARNSET_NARC)
REQUIRED_DIRECTORIES += $(BUILD)/a229 $(LEARNSET_OUTPUT_DIR)

.PHONY: force-test
force-test:

BATTLETESTS_OUTPUT_DIR := build/battle_tests
BATTLETESTS_TARGET := $(BUILD)/a028/9_16
BATTLETESTS_DEPENDENCIES := $(BATTLETESTS_OUTPUT_DIR)/BattleTests.c
BATTLETESTS_HEADER := include/constants/generated/test_battle.h
BATTLETESTS_TEST_FILES := $(shell find data/battle_tests -type f -name '*.c' | LC_ALL=C sort)
BATTLETESTS_FORCE_REGEN := $(if $(strip $(TEST_FILTER)),force-test,)
BATTLETESTS_OBJS := $(patsubst %.c,%.o,$(BATTLETESTS_DEPENDENCIES))
BATTLETESTS_BIN := $(patsubst $(BATTLETESTS_OUTPUT_DIR)/%.c,$(BUILD)/%.bin,$(BATTLETESTS_DEPENDENCIES))

$(BATTLETESTS_HEADER): $(BATTLETESTS_TEST_FILES) $(BATTLETESTS_FORCE_REGEN) $(VENV_ACTIVATE)
	$(PYTHON) scripts/build_tests.py $(TEST_FILTER)

$(BATTLETESTS_DEPENDENCIES): $(BATTLETESTS_HEADER)

$(BATTLETESTS_BIN): $(BATTLETESTS_DEPENDENCIES) $(BATTLETESTS_TEST_FILES) $(BATTLETESTS_HEADER)
	@echo "writing battle tests..."
	$(CC) $(CFLAGS) -c $(BATTLETESTS_DEPENDENCIES) -o $(BATTLETESTS_OBJS)
	$(OBJCOPY) -O binary $(BATTLETESTS_OBJS) $@

NARC_FILES += $(BATTLETESTS_BIN)
REQUIRED_DIRECTORIES += $(BATTLETESTS_OUTPUT_DIR)

OVERWORLD_WILD_BEHAVIOR_DATA_TARGET := $(BUILD)/a028/9_17
OVERWORLD_WILD_BLOB_VALIDATOR := scripts/validate_overworld_wild_blobs.py
OVERWORLD_WILD_BEHAVIOR_DATA_GENERATOR := scripts/generate_overworld_wild_behavior_v40.py
OVERWORLD_WILD_BEHAVIOR_DATA_MODEL := data/OverworldWildBehaviorModelV40.json
OVERWORLD_WILD_BEHAVIOR_DATA_CODEC := scripts/overworld_wild_behavior_model_v40.py
OVERWORLD_WILD_BEHAVIOR_DATA_CODEC_TEST := scripts/test_overworld_wild_behavior_model_v40.py
OVERWORLD_WILD_BEHAVIOR_DATA_FIELD_METADATA := scripts/overworld_wild_behavior_v40_field_metadata.py
OVERWORLD_WILD_BEHAVIOR_DATA_GENERATED := data/OverworldWildBehaviorDataV40.generated.inc
OVERWORLD_WILD_BEHAVIOR_DATA_HOST_VALIDATOR := scripts/overworld_wild_behavior_v40_validator.py
OVERWORLD_WILD_BEHAVIOR_DATA_SHARED_VALIDATOR := scripts/overworld_wild_behavior_v40_validation_shared.h
OVERWORLD_WILD_BEHAVIOR_DATA_TARGET_VALIDATOR := scripts/overworld_wild_behavior_v40_target_validator.c
OVERWORLD_WILD_BEHAVIOR_DATA_MALFORMED := scripts/validate_overworld_wild_behavior_v40_malformed.py
OVERWORLD_WILD_BEHAVIOR_DATA_RESOLVER := scripts/resolve_overworld_wild_behavior_v40.py
OVERWORLD_WILD_BEHAVIOR_DATA_SWAP_VALIDATOR := scripts/verify_overworld_wild_behavior_swap.py
OVERWORLD_WILD_BEHAVIOR_DATA_VIEWER := scripts/overworld_behavior_profile_viewer.py
OVERWORLD_WILD_BEHAVIOR_DATA_DEPENDENCIES := data/OverworldWildBehaviorData.c $(OVERWORLD_WILD_BEHAVIOR_DATA_GENERATED) $(OVERWORLD_WILD_BEHAVIOR_DATA_MODEL) $(OVERWORLD_WILD_BEHAVIOR_DATA_CODEC) $(OVERWORLD_WILD_BEHAVIOR_DATA_CODEC_TEST) include/overworld_wild_behavior_data.h include/config.h include/constants/species.h $(OVERWORLD_WILD_BLOB_VALIDATOR) $(OVERWORLD_WILD_BEHAVIOR_DATA_HOST_VALIDATOR) $(OVERWORLD_WILD_BEHAVIOR_DATA_SHARED_VALIDATOR) $(OVERWORLD_WILD_BEHAVIOR_DATA_TARGET_VALIDATOR) $(OVERWORLD_WILD_BEHAVIOR_DATA_MALFORMED) $(OVERWORLD_WILD_BEHAVIOR_DATA_RESOLVER) $(OVERWORLD_WILD_BEHAVIOR_DATA_FIELD_METADATA) $(OVERWORLD_WILD_BEHAVIOR_DATA_SWAP_VALIDATOR) $(OVERWORLD_WILD_BEHAVIOR_DATA_VIEWER) $(VENV_ACTIVATE)
OVERWORLD_WILD_BEHAVIOR_DATA_OBJ := build/OverworldWildBehaviorData.o
OVERWORLD_WILD_BEHAVIOR_DATA_BIN := build/OverworldWildBehaviorData.bin

$(OVERWORLD_WILD_BEHAVIOR_DATA_GENERATED): $(OVERWORLD_WILD_BEHAVIOR_DATA_GENERATOR) $(OVERWORLD_WILD_BEHAVIOR_DATA_MODEL) $(OVERWORLD_WILD_BEHAVIOR_DATA_CODEC)
	$(PYTHON) $(OVERWORLD_WILD_BEHAVIOR_DATA_GENERATOR) --output $@

$(OVERWORLD_WILD_BEHAVIOR_DATA_BIN): $(OVERWORLD_WILD_BEHAVIOR_DATA_DEPENDENCIES)
	@echo "writing overworld wild behavior data..."
	@mkdir -p $(dir $@)
	$(PYTHON) scripts/overworld_behavior_profile_viewer.py --validate-overrides
	$(PYTHON) $(OVERWORLD_WILD_BEHAVIOR_DATA_CODEC_TEST)
	$(CC) $(CFLAGS) -c data/OverworldWildBehaviorData.c -o $(OVERWORLD_WILD_BEHAVIOR_DATA_OBJ)
	$(OBJCOPY) -O binary $(OVERWORLD_WILD_BEHAVIOR_DATA_OBJ) $@
	$(PYTHON) $(OVERWORLD_WILD_BEHAVIOR_DATA_GENERATOR) --check --raw-output $(BUILD)/OverworldWildBehaviorDataV40.expected.bin
	cmp $(BUILD)/OverworldWildBehaviorDataV40.expected.bin $@
	$(PYTHON) $(OVERWORLD_WILD_BLOB_VALIDATOR) --owbd $@ --owbd-source include/overworld_wild_behavior_data.h
	$(PYTHON) $(OVERWORLD_WILD_BEHAVIOR_DATA_MALFORMED) --blob $@
	$(PYTHON) $(OVERWORLD_WILD_BEHAVIOR_DATA_RESOLVER) --blob $@ --golden-baseline --mutation-self-test
	$(PYTHON) $(OVERWORLD_WILD_BEHAVIOR_DATA_SWAP_VALIDATOR)

NARC_FILES += $(OVERWORLD_WILD_BEHAVIOR_DATA_BIN)

OVERWORLD_WILD_ENCOUNTER_LOOKUP_TARGET := $(BUILD)/a028/9_18
OVERWORLD_WILD_ENCOUNTER_LOOKUP_GENERATOR := scripts/build_overworld_wild_encounter_data.py
OVERWORLD_WILD_ENCOUNTER_LOOKUP_DEPENDENCIES := data/OverworldWildEncounterLookupData.c include/overworld_wild_behavior_data.h include/config.h include/constants/maps.h $(BUILD_NARC)/encounters.narc $(OVERWORLD_WILD_BLOB_VALIDATOR) $(OVERWORLD_WILD_ENCOUNTER_LOOKUP_GENERATOR) $(VENV_ACTIVATE)
OVERWORLD_WILD_ENCOUNTER_LOOKUP_BIN := build/OverworldWildEncounterLookupData.bin

$(OVERWORLD_WILD_ENCOUNTER_LOOKUP_BIN): $(OVERWORLD_WILD_ENCOUNTER_LOOKUP_DEPENDENCIES)
	@echo "writing overworld wild encounter lookup..."
	@mkdir -p $(dir $@)
	$(PYTHON) $(OVERWORLD_WILD_ENCOUNTER_LOOKUP_GENERATOR) --source data/OverworldWildEncounterLookupData.c --maps-header include/constants/maps.h --encounter-narc $(BUILD_NARC)/encounters.narc --output $@
	$(PYTHON) $(OVERWORLD_WILD_BLOB_VALIDATOR) --owed $@ --owed-source include/overworld_wild_behavior_data.h --encounter-narc $(BUILD_NARC)/encounters.narc

NARC_FILES += $(OVERWORLD_WILD_ENCOUNTER_LOOKUP_BIN)

OVERWORLD_WILD_SPAWN_METADATA_TARGET := $(BUILD)/a028/9_19
OVERWORLD_WILD_SPAWN_METADATA_GENERATOR := scripts/build_overworld_wild_spawn_metadata.py
OVERWORLD_WILD_SPAWN_METADATA_FORMAT_HEADER := include/overworld_wild_behavior_data.h
OVERWORLD_WILD_SPAWN_METADATA_DEPENDENCIES := $(BUILD_NARC)/mondata.narc $(BUILD_NARC)/overworld_properties.narc $(BUILD)/a028/9_09 $(SPECIES_TO_OW_GFX_BIN) $(POKEFORMDATATBL_BIN) build/field/overworld_table.o base/overlay/overlay_0001.bin $(OVERWORLD_WILD_SPAWN_METADATA_FORMAT_HEADER) $(OVERWORLD_WILD_SPAWN_METADATA_GENERATOR) $(VENV_ACTIVATE)
OVERWORLD_WILD_SPAWN_METADATA_BIN := build/OverworldWildSpawnMetadata.bin

$(OVERWORLD_WILD_SPAWN_METADATA_BIN): $(OVERWORLD_WILD_SPAWN_METADATA_DEPENDENCIES)
	@echo "writing overworld wild spawn metadata..."
	@mkdir -p $(dir $@)
	$(PYTHON) $(OVERWORLD_WILD_SPAWN_METADATA_GENERATOR) \
		--mondata-narc $(BUILD_NARC)/mondata.narc \
		--overworld-properties-narc $(BUILD_NARC)/overworld_properties.narc \
		--form-counts $(BUILD)/a028/9_09 \
		--base-models $(SPECIES_TO_OW_GFX_BIN) \
		--form-species $(POKEFORMDATATBL_BIN) \
		--render-table build/field/overworld_table.o \
		--render-descriptors base/overlay/overlay_0001.bin \
		--format-header $(OVERWORLD_WILD_SPAWN_METADATA_FORMAT_HEADER) \
		--output $@
	$(PYTHON) $(OVERWORLD_WILD_SPAWN_METADATA_GENERATOR) \
		--mondata-narc $(BUILD_NARC)/mondata.narc \
		--overworld-properties-narc $(BUILD_NARC)/overworld_properties.narc \
		--form-counts $(BUILD)/a028/9_09 \
		--base-models $(SPECIES_TO_OW_GFX_BIN) \
		--form-species $(POKEFORMDATATBL_BIN) \
		--render-table build/field/overworld_table.o \
		--render-descriptors base/overlay/overlay_0001.bin \
		--format-header $(OVERWORLD_WILD_SPAWN_METADATA_FORMAT_HEADER) \
		--verify $@

NARC_FILES += $(OVERWORLD_WILD_SPAWN_METADATA_BIN)

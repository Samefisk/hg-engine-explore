#include "../../include/map_teleport.h"

#include "../../include/config.h"
#include "../../include/constants/maps.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#define MAP_TELEPORT_ENCOUNTER_MAP_SHIFT 0
#define MAP_TELEPORT_ENCOUNTER_MAP_MASK 0x03FFu
#define MAP_TELEPORT_ENCOUNTER_WARP_SHIFT 10
#define MAP_TELEPORT_ENCOUNTER_WARP_MASK 0x003Fu
#define MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT 123

static const u16 sMapTeleportEncounterDestinations[MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT] = {
    0x003Cu, // MAP_T20 warp-id 0 via map 61 warp 0 at 4,14
    0x0021u, // MAP_R29 warp-id 0 via map 134 warp 0 at 5,12
    0x0443u, // MAP_T21 warp-id 1 via map 68 warp 0 at 4,11
    0x0422u, // MAP_R30 warp-id 1 via map 127 warp 0 at 4,8
    0x0023u, // MAP_R31 warp-id 0 via map 97 warp 1 at 10,7
    0x0049u, // MAP_T22 warp-id 0 via map 97 warp 0 at 1,7
    0x009Bu, // MAP_D15R0102 warp-id 0 via map 110 warp 1 at 10,15
    0x009Cu, // MAP_D15R0103 warp-id 0 via map 155 warp 3 at 15,27
    0x0024u, // MAP_R32 warp-id 0 via map 98 warp 0 at 10,7
    0x0871u, // MAP_D24R0101 warp-id 2 via map 98 warp 1 at 1,7
    0x0138u, // MAP_D24R0202 warp-id 0 via map 113 warp 4 at 436,266
    0x013Au, // MAP_D24R0204 warp-id 0 via map 113 warp 5 at 436,309
    0x0063u, // MAP_D25R0101 warp-id 0 via map 36 warp 2 at 462,430
    0x0099u, // MAP_D25R0102 warp-id 0 via map 99 warp 1 at 4,25
    0x109Au, // MAP_D25R0103 warp-id 4 via map 99 warp 4 at 5,3
    0x0025u, // MAP_R33 warp-id 0 via map 99 warp 2 at 27,93
    0x0072u, // MAP_D26R0101 warp-id 0 via map 74 warp 7 at 433,454
    0x00B1u, // MAP_D26R0102 warp-id 0 via map 114 warp 1 at 11,6
    0x00B5u, // MAP_D26R0103 warp-id 0 via map 177 warp 1 at 27,20
    0x0075u, // MAP_D36R0101 warp-id 0 via map 100 warp 1 at 1,7
    0x0026u, // MAP_R34 warp-id 0 via map 171 warp 0 at 5,2
    0x0027u, // MAP_R35 warp-id 0 via map 101 warp 1 at 5,2
    0x0060u, // MAP_D22R0101 warp-id 0 via map 102 warp 1 at 25,2
    0x0828u, // MAP_R36 warp-id 2 via map 103 warp 0 at 5,2
    0x004Eu, // MAP_T27 warp-id 0 via map 7 warp 0 at 15,26
    0x0007u, // MAP_D18R0101 warp-id 0 via map 78 warp 0 at 376,149
    0x00D9u, // MAP_D18R0102 warp-id 0 via map 7 warp 1 at 22,16
    0x014Cu, // MAP_D17R0102 warp-id 0 via map 111 warp 1 at 9,8
    0x014Du, // MAP_D17R0103 warp-id 0 via map 332 warp 1 at 15,25
    0x014Eu, // MAP_D17R0104 warp-id 0 via map 333 warp 1 at 24,8
    0x014Fu, // MAP_D17R0105 warp-id 0 via map 334 warp 1 at 6,8
    0x0150u, // MAP_D17R0106 warp-id 0 via map 335 warp 3 at 13,25
    0x0151u, // MAP_D17R0107 warp-id 0 via map 336 warp 1 at 6,19
    0x0152u, // MAP_D17R0108 warp-id 0 via map 337 warp 1 at 15,26
    0x0D53u, // MAP_D17R0109 warp-id 3 via map 337 warp 2 at 12,16
    0x002Au, // MAP_R38 warp-id 0 via map 172 warp 1 at 1,7
    0x002Bu, // MAP_R39 warp-id 0 via map 214 warp 0 at 6,10
    0x0C4Du, // MAP_T26 warp-id 3 via map 115 warp 0 at 8,17
    0x005Eu, // MAP_W40 warp-id 0 via map 366 warp 0 at 5,12
    0x085Fu, // MAP_W41 warp-id 2 via map 121 warp 0 at 37,25
    0x0C79u, // MAP_D40R0101 warp-id 3 via map 95 warp 0 at 208,341
    0x14F2u, // MAP_D40R0102 warp-id 5 via map 121 warp 1 at 51,22
    0x00F3u, // MAP_D40R0104 warp-id 0 via map 242 warp 4 at 31,49
    0x00F4u, // MAP_D40R0107 warp-id 0 via map 243 warp 5 at 31,43
    0x004Bu, // MAP_T24 warp-id 0 via map 139 warp 0 at 13,19
    0x082Cu, // MAP_R42 warp-id 2 via map 119 warp 0 at 20,46
    0x0077u, // MAP_D38R0101 warp-id 0 via map 44 warp 2 at 436,171
    0x00FAu, // MAP_D38R0102 warp-id 0 via map 119 warp 4 at 34,31
    0x00FBu, // MAP_D38R0103 warp-id 0 via map 119 warp 9 at 45,2
    0x00FCu, // MAP_D38R0104 warp-id 0 via map 119 warp 10 at 45,44
    0x002Du, // MAP_R43 warp-id 0 via map 142 warp 1 at 5,2
    0x0058u, // MAP_T29 warp-id 0 via map 294 warp 0 at 4,8
    0x002Eu, // MAP_R44 warp-id 0 via map 120 warp 0 at 11,58
    0x0078u, // MAP_D39R0101 warp-id 0 via map 46 warp 0 at 633,169
    0x00EDu, // MAP_D39R0102 warp-id 0 via map 120 warp 2 at 55,7
    0x00EEu, // MAP_D39R0103 warp-id 0 via map 237 warp 2 at 25,8
    0x00EFu, // MAP_D39R0104 warp-id 0 via map 238 warp 2 at 16,17
    0x0059u, // MAP_T30 warp-id 0 via map 120 warp 1 at 55,40
    0x007Du, // MAP_D44R0101 warp-id 0 via map 89 warp 2 at 672,132
    0x00FDu, // MAP_D44R0102 warp-id 0 via map 125 warp 1 at 6,5
    0x002Fu, // MAP_R45 warp-id 0 via map 123 warp 1 at 60,4
    0x0030u, // MAP_R46 warp-id 0 via map 134 warp 1 at 5,2
    0x00B0u, // MAP_D42R0102 warp-id 0 via map 35 warp 2 at 565,269
    0x047Bu, // MAP_D42R0101 warp-id 1 via map 47 warp 0 at 650,198
    0x0097u, // MAP_R47 warp-id 0 via map 279 warp 1 at 18,46
    0x0092u, // MAP_D11R0101 warp-id 0 via map 92 warp 0 at 1127,501
    0x01C5u, // MAP_D11R0102 warp-id 0 via map 146 warp 2 at 52,20
    0x01C6u, // MAP_D11R0103 warp-id 0 via map 453 warp 2 at 32,22
    0x01C7u, // MAP_D11R0104 warp-id 0 via map 454 warp 4 at 43,12
    0x01C8u, // MAP_D11R0105 warp-id 0 via map 455 warp 4 at 44,22
    0x01CEu, // MAP_D41R0105 warp-id 0 via map 122 warp 1 at 15,12
    0x01D0u, // MAP_D41R0107 warp-id 0 via map 459 warp 6 at 14,39
    0x01D1u, // MAP_D41R0108 warp-id 0 via map 464 warp 1 at 13,1
    0x0156u, // MAP_D50R0101 warp-id 0 via map 151 warp 1 at 130,385
    0x0155u, // MAP_D17R0112 warp-id 0 via map 339 warp 6 at 12,17
    0x005Au, // MAP_T31 warp-id 0 via map 122 warp 0 at 40,61
    0x007Au, // MAP_D41R0101 warp-id 0 via map 90 warp 0 at 811,260
    0x01CBu, // MAP_D41R0102 warp-id 0 via map 463 warp 1 at 20,1
    0x09CCu, // MAP_D41R0103 warp-id 2 via map 122 warp 3 at 51,46
    0x01CDu, // MAP_D41R0104 warp-id 0 via map 122 warp 2 at 34,47
    0x0014u, // MAP_R12 warp-id 0 via map 425 warp 1 at 10,7
    0x005Bu, // MAP_W19 warp-id 0 via map 424 warp 1 at 5,12
    0x005Cu, // MAP_W20 warp-id 0 via map 146 warp 0 at 55,28
    0x0031u, // MAP_T01 warp-id 0 via map 503 warp 0 at 5,10
    0x0032u, // MAP_T02 warp-id 0 via map 496 warp 0 at 5,47
    0x1C34u, // MAP_T04 warp-id 7 via map 145 warp 0 at 49,42
    0x0436u, // MAP_T06 warp-id 1 via map 358 warp 0 at 8,19
    0x0037u, // MAP_T07 warp-id 0 via map 370 warp 0 at 12,12
    0x0038u, // MAP_T08 warp-id 0 via map 392 warp 0 at 1,7
    0x0039u, // MAP_T09 warp-id 0 via map 508 warp 0 at 8,19
    0x001Eu, // MAP_R26 warp-id 0 via map 296 warp 0 at 4,8
    0x001Fu, // MAP_R27 warp-id 0 via map 126 warp 0 at 30,22
    0x0020u, // MAP_R28 warp-id 0 via map 299 warp 3 at 1,8
    0x006Bu, // MAP_D02R0101 warp-id 0 via map 11 warp 0 at 1172,102
    0x01C0u, // MAP_D02R0102 warp-id 0 via map 107 warp 2 at 17,4
    0x046Cu, // MAP_D05R0101 warp-id 1 via map 18 warp 0 at 1419,163
    0x01C4u, // MAP_D05R0102 warp-id 0 via map 108 warp 2 at 8,34
    0x047Cu, // MAP_D43R0101 warp-id 1 via map 178 warp 0 at 7,31
    0x0009u, // MAP_R01 warp-id 0 via map 527 warp 0 at 5,12
    0x080Au, // MAP_R02 warp-id 2 via map 418 warp 1 at 5,12
    0x000Bu, // MAP_R03 warp-id 0 via map 107 warp 0 at 4,4
    0x000Cu, // MAP_R04 warp-id 0 via map 107 warp 1 at 22,23
    0x000Du, // MAP_R05 warp-id 0 via map 391 warp 1 at 5,2
    0x000Eu, // MAP_R06 warp-id 0 via map 389 warp 0 at 5,12
    0x000Fu, // MAP_R07 warp-id 0 via map 493 warp 1 at 1,7
    0x0010u, // MAP_R08 warp-id 0 via map 390 warp 1 at 10,7
    0x0012u, // MAP_R10 warp-id 0 via map 108 warp 1 at 46,10
    0x0813u, // MAP_R11 warp-id 2 via map 106 warp 0 at 4,6
    0x0017u, // MAP_R15 warp-id 0 via map 392 warp 1 at 10,7
    0x0018u, // MAP_R16 warp-id 0 via map 421 warp 1 at 1,7
    0x001Au, // MAP_R18 warp-id 0 via map 423 warp 0 at 1,7
    0x001Bu, // MAP_R22 warp-id 0 via map 299 warp 2 at 21,8
    0x001Du, // MAP_R25 warp-id 0 via map 440 warp 0 at 7,11
    0x007Eu, // MAP_D45R0101 warp-id 0 via map 31 warp 0 at 740,396
    0x012Au, // MAP_D45R0102 warp-id 0 via map 126 warp 2 at 27,11
    0x006Au, // MAP_D01R0101 warp-id 0 via map 19 warp 2 at 1354,302
    0x00B2u, // MAP_D43R0102 warp-id 0 via map 124 warp 1 at 19,7
    0x00B3u, // MAP_D43R0103 warp-id 0 via map 58 warp 0 at 912,218
    0x119Eu, // MAP_R02R0101 warp-id 4 via map 106 warp 7 at 37,10
    0x0093u, // MAP_D46R0101 warp-id 0 via map 419 warp 1 at 5,2
    0x0091u, // MAP_D03R0101 warp-id 0 via map 52 warp 7 at 1290,107
    0x0DC2u, // MAP_D03R0102 warp-id 3 via map 145 warp 1 at 55,11
    0x05C3u, // MAP_D03R0103 warp-id 1 via map 145 warp 2 at 55,22
};

static MapTeleportDestination sMapTeleportEncounterDestinationScratch;

static u16 MapTeleport_EncounterDestinationPackedMapId(u16 packed)
{
    return (u16)((packed >> MAP_TELEPORT_ENCOUNTER_MAP_SHIFT)
        & MAP_TELEPORT_ENCOUNTER_MAP_MASK);
}

static const MapTeleportDestination *MapTeleport_EncounterDestinationFromPacked(u16 packed)
{
    sMapTeleportEncounterDestinationScratch.mapId =
        MapTeleport_EncounterDestinationPackedMapId(packed);
    sMapTeleportEncounterDestinationScratch.x =
        (u16)((packed >> MAP_TELEPORT_ENCOUNTER_WARP_SHIFT)
            & MAP_TELEPORT_ENCOUNTER_WARP_MASK);
    sMapTeleportEncounterDestinationScratch.y = MAP_TELEPORT_DESTINATION_WARP_ID_Y;
    sMapTeleportEncounterDestinationScratch.direction = MAP_TELEPORT_DIRECTION_SOUTH;
    return &sMapTeleportEncounterDestinationScratch;
}

static const MapTeleportDestination *MapTeleport_EncounterDestinationByIndex(u16 index)
{
    if (index >= MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT) {
        return NULL;
    }

    return MapTeleport_EncounterDestinationFromPacked(sMapTeleportEncounterDestinations[index]);
}

const MapTeleportEncounterDestinationEntry gMapTeleportEncounterDestinationEntry
    __attribute__((section(".map_teleport_encounter_destination_entry"), used)) = {
    MAP_TELEPORT_ENCOUNTER_DESTINATION_MAGIC,
    MAP_TELEPORT_ENCOUNTER_DESTINATION_VERSION,
    sizeof(MapTeleportEncounterDestinationEntry),
    MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT,
    0,
    MapTeleport_EncounterDestinationByIndex,
    NULL,
};

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS

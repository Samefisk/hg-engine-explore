# Johto Wild Encounter Rebalance - Player Guide

This guide explains what changed in the wild so you can plan your team during a normal story playthrough.

## Opening-route playtest — October 2026

Routes29,30,31 and46 now use the checked Johto land slots and levels from
`13bad83b4`. Their scoped test pools are removed, including the affected Surf,
fishing, swarm and normal Headbutt species. Random walking encounters stay
off. Cherrygrove's placement pilot, nearby cave and tower pools, existing
behavior settings, six initial Land/Surf slots and the60-frame base refill
setting stay unchanged.

Violet City uses existing roof, signpost and mailbox destinations. Pidgey fills
the morning and day land tables. The night table has Hoothoot99% and Rowlet1%
(last slot, level5); city birds are levels3–5. Rowlet uses the same Small Bird
Hop, Fly In and raised-surface Perch memberships. Their field settings do not
change. No valid Violet flower-bed entries exist, so Flabébé is left out.
Pichu and Sentret are also left out of Violet.

The existing time mix stays on:80% of land rolls use the current time's table;
20% choose one of morning, day or night at random, including the current table.
Thus a night Pokémon can appear by day. Rowlet's1% is its night-table weight,
not its share of all city spawns; placement checks can reject a rolled species.
At night, the raw land roll gives Rowlet about0.87%; by day, about0.067%.

The user owns the game checks for TKT-0053. Follow New Bark → Route29 → lower
Route46 → Cherrygrove → Routes30–31 → Dark Cave entrance → Violet → Sprout
Tower. Repeat Violet and the tower at night. Check a catch, follower movement,
spawn and distance removal, doors and stairs, control after events, raised
landings and clear door access. The new ROM has not earned agent game or pacing
proof; those checks are left to the user.

## Goldenrod encounter plan — October 2026

Goldenrod City (map76, encounter142) uses the mix below. Morning and day
share one table. These two new encounter pools use the current clock table
only; all older pools keep their existing80/20 current/random table mix.

| Pokémon | Morning/day | Night | City levels | Placement |
| --- | ---: | ---: | --- | --- |
| Meowth |30%|30%|12–13| Behind Buildings; no rooftop |
| Rattata |20%|40%|12–15| Behind Buildings |
| Snubbull |10%|10%|14| Land |
| Pidove |30%|0%|12,14| Land and Rooftop |
| Murkrow |0%|10%|14| Rooftop and Canopy |
| Trubbish |9%|8%|15–16| Behind Buildings |
| Grimer |1%|1%|16| Behind Buildings |
| Rotom |0%|1%|16| Behind Buildings |

The main public Underground corridor (map199, encounter143) uses95% Rattata
and5% Grimer at all times, on existing Land. Rattata is level12–16; Grimer is
level15–16. Other Underground rooms and the department-store basement keep
their existing encounter settings.

The twelve native slot weights are20,20,10,10,10,10,5,5,4,4,1,1.
City morning/day slots are Meowth,Pidove,Meowth,Rattata,Pidove,Snubbull,
Rattata,Rattata,Trubbish,Trubbish,Trubbish,Grimer. Night slots are Rattata,
Meowth,Rattata,Meowth,Snubbull,Murkrow,Rattata,Rattata,Trubbish,Trubbish,
Grimer,Rotom. Underground slots are Rattata except Grimer in slots9 and11.
Both pools use levels12,12,13,13,14,14,14,15,15,15,16,16 in slot order.
Walking battles, Surf, rods, sound replacements, and swarm slots remain off
for these two new pools. The overworld uses the authored land tables.

Four visible Placement profiles supply these sites: Behind Buildings, Land
Placement, Land and Rooftop, and Rooftop and Canopy. Their applications match
the map and listed species. They keep the normal movement, speed, pauses,
attacks, and reactions. Birds gain only their listed raised-surface permissions.
Rotom uses the same building rule as the other listed ground Pokémon; it has
no Radio Tower or other landmark rule. The location must still pass the shared
Land check, so a blocked or water tile cannot become a valid spawn site.

These are raw encounter-roll shares. A lack of a permitted nearby destination
can reject a rolled Pokémon. Host data, clock, and resolver checks do not prove
natural game births or frame pacing; those need current-ROM acceptance.

## What This Rebalance Does

- Johto Pokémon appear earlier and more often.
- Early routes are less dominated by Kanto staples.
- Formerly late/postgame Johto favorites are now usable during the main story.
- Baby Pokémon and special forms are placed in logical habitats.
- Rare encounters still feel special, but many old "too rare to use" picks are now practical.

## Early Route Highlights (Routes 29-31)

- `Sentret`, `Hoothoot`, `Ledyba`, and `Spinarak` are much more prominent.
- `Pichu`, `Igglybuff`, `Mime Jr.`, and `Happiny` are available early.
- `Delibird` appears in early-morning grass for early Ice coverage.
- `Toedscool` is available early as a rare damp-route find.

## Route 46 Early Team Projects

- `Phanpy` and `Teddiursa` can be found before Gym 1.
- `Gligar` appears at night.
- `Hisuian Sneasel` was moved away from Route 46 (see below).

## "No More Gimmick" Johto Mons

These are now realistic to catch and actually use:

- `Yanma` on Route 35.
- `Dunsparce` in Dark Cave (Route 31 side).
- `Snubbull` on Route 34.
- `Qwilfish` in earlier fishing access.
- `Pineco` in Ilex Forest grass (not just tree gimmicks).
- `Chinchou` appears earlier in Route 32 water access.

## Johto Species Moved Into Main Story

- `Houndour`: Route 36/37 (night), Burned Tower.
- `Misdreavus`: Burned Tower B1F and deep Slowpoke Well.
- `Slugma`: Burned Tower and deeper Dark Cave.
- `Sneasel`: Ilex Forest (night), plus later Ice-path support.
- `Murkrow`: Ilex Forest (night).
- `Skarmory`: Route 42 and Mt. Mortar outer sections.
- `Mantine`: common in western sea routes.
- `Larvitar`: deep Mt. Mortar as a mid-game exploration reward.

## Baby Pokémon Expansion

Early babies are now spread through safe or lore-appropriate zones:

- Route 32 grass: `Mantyke`, `Azurill`.
- Union Cave 1F: `Azurill`.
- Ruins of Alph area: `Togepi`, `Cleffa`.
- Dark Cave entrance area: `Smoochum`, `Wynaut`.
- Union Cave deeper floors: `Magby`.
- Route 33: `Elekid`, `Bonsly`.

## Regional Form Additions (Where to Look)

### Urban / Invasive Theme

- Route 38/39: `Galarian Meowth` (day), `Alolan Meowth` (night).
- Burned Tower: `Alolan Grimer`, plus `Galarian Weezing` support.
- National Park: `Galarian Ponyta`.
- Sprout/Bell Tower nights: `Alolan Rattata`.
- Route 39 ranch identity: Paldean Tauros forms in the farm ecosystem.

### Ancient Heritage Theme

- Route 37: `Hisuian Growlithe`.
- Route 33 and Ilex: `Hisuian Voltorb`.
- Ilex Forest: `Galarian Farfetch'd`.
- Whirl Islands: `Hisuian Qwilfish`.

### Micro-Climate Theme

- Route 32 / Ruins outside: `Paldean Wooper`.
- Union Cave lower floors: `Alolan Sandshrew`.
- Ice Path: `Alolan Vulpix`, `Galarian Mr. Mime`.
- Mt. Mortar depths: `Alolan Geodude`, `Alolan Diglett`.
- Slowpoke Well: `Galarian Slowpoke`.
- Deep Whirl water: `Galarian Corsola`.

## Convergent Species

- `Toedscool`: early damp/forest routes.
- `Wiglett`: west-coast sea fishing routes.

## Special Request Updates Included

- `Hisuian Sneasel` relocated to:
  - Route 42 (outside Mt. Mortar)
  - Mt. Mortar 1F
- `Eevee` added as a rare wild National Park encounter.
- `Doduo` and `Dodrio` now support Route 39's ranch identity.

## Practical Team-Building Notes

- You can build much more Johto-native teams before Ecruteak.
- Early Ice, Ground, and utility options arrive much sooner.
- More viable alternatives exist for mid-game Gyms without waiting for Kanto or postgame.


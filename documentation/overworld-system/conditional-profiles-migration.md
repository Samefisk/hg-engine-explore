# Conditional Profile Migration Map

This is the CP6 record for removing the old Alert-to-Active ownership model.
The machine-checked copy is
[`conditional_profile_migration_v1.json`](../../tools/overworld/fixtures/conditional_profile_migration_v1.json).

## Mapping rule

An old Active response is now a conditional override profile. The condition
entry owns activation. The normal source profile keeps alert presentation until
CP7 removes the old trigger fields. Tired profiles stay unchanged.

The old `stamina` value counted completed movement actions. A new duration is
an actor-system frame count, so exact timing is not possible. CP6 uses a fixed
case-by-case estimate:

~~~text
duration = old stamina × nominal frames for one authored action
cooldown = duration + old rest time
~~~

For a two-tile Ambush Plant hop, the nominal action is 12 frames. A more
specific overlapping condition is listed after its broad condition and wins.

## Old Active references

| Old source | Old response | New conditional profile | Conditions | Result |
| --- | --- | --- | --- | --- |
| Default | Default Active | Default Active | Default, class, and later normal-profile pools below | Presentation only; response fields are empty |
| Flying Insect | Default Active | Default Active | Flying Insect notices player | Presentation only |
| Nervous Scavenger | Nervous Scavenger | Default Active | Nervous and Playful Scavenger notices player | Presentation only; reapplying the owner had no field change |
| Hopping Scavenger | Hopping Scavenger | Default Active | Hopping and Hopping Thrower notices player | Presentation only; reapplying the owner had no field change |
| Baby Pokémon | Skittish | Skittish | Baby and Igglybuff notices player | Owner becomes Flee |
| Swaying Plant | Swaying Plant Active | Swaying Plant Active | Swaying Plant notices player | Faster ordinary wander |
| Ambush Plant | Ambush Plant Active | Ambush Plant Active | Ambush Plant notices player | Hop toward player |

The Default Active application is before the three response applications.
This makes a later flee, sway, or chase condition own the final target and
field provenance.

## Timed condition entries

| Condition | Subject pool | Notice rule | Duration | Cooldown |
| --- | --- | --- | ---: | ---: |
| Default | Default behavior class | Facing line plus close radius, 3, 100% | 960 | 970 |
| Aggressive Chase | Aggressive Chase class | Facing line plus close radius, 3, 100% | 160 | 164 |
| Aggressive Ram | Aggressive Ram class | Cardinal line, 14, 100% | 96 | 100 |
| Nervous Scavenger | Nervous application | Facing line plus close radius, 3, 100% | 140 | 150 |
| Hopping Scavenger | Hopping application | Facing line plus close radius, 3, 100% | 240 | 250 |
| Flying Insect | Flying Insect application | Radius, 7, 100% | 160 | 180 |
| Gentle Grazer | Gentle Grazer application | Radius, 2, 80% | 280 | 290 |
| Throwing | Throwing application | Radius, 2, 100% | 2880 | 2890 |
| Hopping Thrower | Mankey family | Radius, 2, 100% | 720 | 730 |
| Playful | Playful application | Radius, 3, 100% | 2880 | 2890 |
| Playful Scavenger | Sentret, Furret, Aipom, Ambipom | Radius, 3, 100% | 420 | 430 |
| Baby | Baby application | Facing line plus close radius, 3, 100% | 960 | 970 |
| Igglybuff | Igglybuff | Facing line plus close radius, 3, 100% | 240 | 250 |
| Swaying Plant | Swaying Plant application | Facing line plus close radius, 3, 100% | 44 | 164 |
| Ambush Plant | Ambush Plant application | Radius, 4, 100% | 36 | 126 |

All entries capture the player. A held activation keeps that target until it
expires or the target becomes invalid. Cooldown starts with the trigger.

## Other current conditions

The two old terrain/speed records were already moved in CP1:

- `canopy-hop-surface` owns `condition-canopy-hopper-on-canopy`.
- `bird-rooftop` owns `condition-bird-rooftop`.

They stay while-true and targetless.

## Notice-disabled profile

The Mewtwo Test profile has `alertChance = 0`. It is now a selected Test
behavior class instead of a normal application. The broad Default condition
matches only the Default behavior class, so Mewtwo remains outside that pool.
This preserves the disabled notice rule without adding condition negation.

The Follower application still suppresses legacy alert presentation during
the CP6 compatibility period. CP7 decides condition use at the Follower intent
boundary; it does not add a second alert owner.

## Proof

`test_conditional_profile_migration.py` checks all seven old Active references,
both terrain migrations, exact response fields, Mewtwo exclusion, application
order, target provenance, and these four host resolver results:

- Default is presentation-only and does not change Owner bytes.
- Baby Pokémon resolves Flee.
- Swaying Plant resolves its faster walk values.
- Ambush Plant resolves Hop toward Player.

The CP6 exit gate also uses the catalog generator check, Workshop authoring
check, resolver check, and the fresh Active migration inventory.

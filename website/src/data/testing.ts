// Edit this file to change the "What's being tested" page. No other code needs touching.

export const currentBuild = {
  label: 'Tester build 3555',
  date: '2026-10-09',
  note: 'Latest build sent to testers. If you are on an older one, ask for the new patch.',
};

export type Status = 'testing' | 'stable' | 'rough' | 'planned';

export interface Area {
  name: string;
  status: Status;
  what: string;
  lookFor: string[];
}

export const statusLabel: Record<Status, string> = {
  testing: 'Needs testing',
  stable: 'Looks stable',
  rough: 'Known rough edges',
  planned: 'Planned',
};

export const areas: Area[] = [
  {
    name: 'Wild Pokémon in the overworld',
    status: 'testing',
    what:
      'Wild Pokémon walk around the routes, notice you, react, and spawn or despawn as you travel. Each species has its own behavior.',
    lookFor: [
      'Pokémon that freeze, get stuck, or keep standing still after noticing you',
      'Spawning that feels too slow, too fast, or lags the game',
      'Pokémon vanishing or appearing in odd spots, including across map transitions',
    ],
  },
  {
    name: 'Reactions: Ram, Throw and Ambush',
    status: 'testing',
    what:
      'Some Pokémon charge at you (Ram), pick things up and throw them (Throw), or hop out at you (Ambush). Followers can throw away Pokémon that hit you.',
    lookFor: [
      'A Ram that stops early, ignores you, or ends on your tile',
      'Throws that never trigger, throw the wrong way, or leave a Pokémon stuck',
      'Odd sounds or visual glitches during a throw',
    ],
  },
  {
    name: 'Followers',
    status: 'testing',
    what: 'Your lead Pokémon follows you and can react to the world around you.',
    lookFor: [
      'Direction it faces when it stops',
      'Pauses between hops that feel too long',
      'Getting stuck after noticing another Pokémon',
    ],
  },
  {
    name: 'Riding',
    status: 'rough',
    what: 'You can ride your Pokémon. Rides use their own movement rules.',
    lookFor: [
      'Hopping, ledges and rooftops',
      'Leaving the running animation after being knocked back',
      'Anything that feels wrong while mounted',
    ],
  },
  {
    name: 'Player HP and knockback',
    status: 'rough',
    what:
      'Contact with wild Pokémon can hurt you and knock you back. Healing, zero HP and battle interaction are still in progress.',
    lookFor: [
      'Damage and knockback that feel unfair or inconsistent',
      'Healing while moving',
      'Red or blue tints showing on Pokémon and whether they read clearly',
    ],
  },
  {
    name: 'Performance and stability',
    status: 'testing',
    what: 'Frame pacing, freezes and black flashes across routes and map changes.',
    lookFor: [
      'Stutter while walking, especially right after a Pokémon spawns',
      'Freezes when entering a route',
      'Brief black screens',
    ],
  },
];

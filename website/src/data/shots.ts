// Screenshots live in public/shots/. Add a file, then add an entry here.
// `area` ties a shot to a card on the testing page (matches Area.name in testing.ts).
export interface Shot {
  file: string;
  caption: string;
  title?: string;
  area?: string;
  alt: string;
}

export const shots: Shot[] = [
  {
    file: 'wild-hoothoot-rooftop.png',
    area: 'Wild Pokémon in the overworld',
    caption: 'Wild Hoothoot perched on a rooftop in Cherrygrove while your Mankey follows along.',
    alt: 'Two wild Hoothoot standing on a rooftop beside the player and a Mankey follower',
  },
  {
    file: 'follower-mankey.png',
    area: 'Followers',
    caption: 'Your Mankey follows you through town. The HP bar in the corner tracks the player.',
    alt: 'The player walking with a Mankey follower and the HP bar visible in the corner',
  },
  {
    file: 'riding-stantler.png',
    area: 'Riding',
    caption: 'Riding Stantler. The ? bubble shows a nearby wild Pokémon noticing you.',
    alt: 'The player riding Stantler with a question mark bubble above a nearby wild Pokémon',
  },
  {
    file: 'ambush-hit.png',
    area: 'Reactions: Ram, Throw and Ambush',
    caption: 'An Ambush: a wild Weepinbell jumps the player. The red flash and white HP bar mark the hit.',
    alt: 'A wild Pokémon in mid-air above the player with a red damage flash around the screen edge',
  },
  {
    file: 'alert-bubble.png',
    area: 'Reactions: Ram, Throw and Ambush',
    caption: 'An alert bubble shows that a Pokémon has noticed something and is about to react.',
    alt: 'An exclamation mark bubble above a wild Pokémon next to the player',
  },
  {
    file: 'damage-tint.png',
    area: 'Player HP and knockback',
    caption: 'Pokémon that have taken damage are tinted red, which fades as they recover.',
    alt: 'A Snorlax tinted pinkish-purple next to a follower in a dark route',
  },
  {
    file: 'ram.png',
    area: 'Reactions: Ram, Throw and Ambush',
    title: 'Ram',
    caption: 'A wild Onix charges down the player\'s row. The hit knocks the player back with a red flash.',
    alt: 'A wild Onix beside the player with a red damage flash around the screen edge',
  },
  {
    file: 'throw.png',
    area: 'Reactions: Ram, Throw and Ambush',
    title: 'Throw',
    caption: 'The Mankey follower picks up a wild Onix and throws it away.',
    alt: 'A wild Onix held above the ground by a Mankey follower, glowing before being thrown',
  },
  {
    file: 'startled.png',
    title: 'Startled',
    caption: 'A Bellsprout notices the player and reacts with a ! bubble.',
    alt: 'Two Bellsprout in front of the player, one with an exclamation bubble',
  },
  {
    file: 'lurk.png',
    title: 'Lurk',
    caption: 'An Ekans waits near the path, notices the player, then springs an Ambush.',
    alt: 'An Ekans with a question mark bubble in front of the player',
  },
  {
    file: 'playful.png',
    title: 'Playful',
    caption: 'A Clefairy stays close to the player instead of keeping its distance.',
    alt: 'A Clefairy standing right next to the player at the Pokémon Center door',
  },
  {
    file: 'skittish.png',
    title: 'Skittish',
    caption: 'Baby Pokémon like Cleffa notice the player and keep away.',
    alt: 'A Cleffa walking away from the player near a flower bed',
  },
  {
    file: 'stalker.png',
    title: 'Stalker',
    caption: 'A Gastly drifts in behind the player while the player is not looking at it.',
    alt: 'A Gastly with a question mark bubble directly behind the player',
  },
  {
    file: 'teleport.png',
    title: 'Teleport',
    caption: 'Ghosts such as Gastly jump to a new spot, here right behind the player.',
    alt: 'A Gastly just behind the player after teleporting',
  },
  {
    file: 'perch.png',
    title: 'Perch',
    caption: 'Birds such as Hoothoot settle on rooftops, signposts and mailboxes.',
    alt: 'A Hoothoot standing on a rooftop beside a house',
  },
  {
    file: 'rooftop-access.png',
    title: 'Rooftop Access',
    caption: 'Mankey can hop up onto a roof, here beside a perched Hoothoot.',
    alt: 'A Mankey and a Hoothoot on the same rooftop',
  },
  {
    file: 'hop.png',
    title: 'Hops',
    caption: 'Mankey hops in an arc over obstacles instead of walking around them.',
    alt: 'A Mankey follower in mid-hop next to a wild Onix',
  },
  {
    file: 'stomp.png',
    title: 'Heavy Stomp',
    caption: 'Heavy Pokémon like Rhydon walk with a stomp. Here one passes the player.',
    alt: 'A Rhydon walking beside the player on a path',
  },
  {
    file: 'flower-bed.png',
    title: 'Flower Bed',
    caption: 'Sunkern settles among the flowers in a flower bed.',
    alt: 'A Sunkern among flowers behind a fence',
  },
];

export const forArea = (name: string) => shots.filter((s) => s.area === name);

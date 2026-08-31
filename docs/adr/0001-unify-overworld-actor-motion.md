---
status: accepted
---

# Unify overworld Pokémon under one actor and motion system

Wild Pokémon, followers, and mounted control will use one resolved behavior model and one motion lifecycle behind a three-call actor facade. Role controllers provide intent, while a shared Motion Module plans and executes Walk, Hop, and Teleport and coordinates streaming, presentation, commit, and cancellation through adapters. This accepted target is not implemented yet. It trades a staged migration and a small observation cost for one source of truth, one motion owner, wild/mounted parity, and a stable agent test surface; DS overlays remain deployment adapters instead of architectural boundaries.

## Considered options

- Keep independent wild and mount engines: lowest short-term change, but it preserves the duplication that caused repeated parity and lifecycle regressions.
- Expose every overlay service as a public module: matches physical placement, but produces shallow interfaces and forces callers to understand implementation order.
- Use one actor facade with private adapters: keeps the public interface small while allowing memory-constrained physical modules and host test adapters.

## Consequences

- Mounted control is a role and presentation rebind, not a separate profile type.
- One accepted movement has one logical owner, one motion, ordered path advances,
  and one terminal semantic commit.
- Profile resolution must become portable and shared by ROM and tools.
- Runtime observation and deterministic scenarios are part of the interface, not temporary diagnostics.

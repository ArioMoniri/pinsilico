# Physics Model

> Phase 0 stub. Populated in detail when Phase 4 lands the simulation
> engine.

PInSilico's kinetic simulation is a **deliberate abstraction**, not full
molecular dynamics. This document will be the candid record of what the
model captures and — equally important — what it does not.

## What the model captures (Phase 4)

- Overdamped Langevin / Brownian dynamics for free ligand particles, with
  a diffusion coefficient derived from molecular volume (RDKit).
- Real protein excluded volumes (van der Waals radii from heavy-atom
  convex hulls).
- Real binding-site positions from fpocket centroids on the loaded PDB.
- Residence times that are Boltzmann-scaled from cached docking ΔG:
  `τ ∝ exp(-ΔG / RT)` (capped for the live view; uncapped for
  fast-forward statistical accumulation).
- Competition between species for a finite, first-come-first-served set
  of pocket sites.
- An **optional**, **honestly labelled** weak attractive potential toward
  unoccupied pockets — a kinetic accelerator so live demos don't wait
  minutes for a hit. **Not** real electrostatics. **Not** implicit
  solvent. Default ON for the demo; one click away from OFF for honest
  pure-diffusion runs.

## What the model does NOT capture

- Induced fit / receptor flexibility (frozen during the kinetic phase).
- Allostery and conformational coupling between sites.
- Explicit solvent in the kinetic layer (the docking layer's solvent
  model is whatever the engine — Smina, Vina, DiffDock, Boltz — uses).
- Polarisability, charge transfer, covalent binding.
- Long-range electrostatics beyond the optional encounter potential.
- Atomistic motion of the bound complex post-binding (Phase 8's
  atomistic view replays the docked pose under a harmonic restraint
  with thermal noise — it shows what binding *looks* like, it does not
  run MD).

For atomistic dynamics of the bound complex, Phase 10 ships an
"Export to OpenMM / GROMACS" action.

## Why this is the right abstraction for v1

The intended user runs hundreds of trials watching selectivity converge
across off-targets, not single high-fidelity MD trajectories. Boltzmann-
scaled residence times derived from real docking ΔG capture the
*relative* kinetic difference that drives selectivity, which is what the
researcher needs to see. Full MD would slow the loop by 4–5 orders of
magnitude with no proportional gain in qualitative insight.

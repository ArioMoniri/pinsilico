# Physics Model

> The honest account of what PInSilico's kinetic simulation captures and
> what it does not. The simulator is a deliberate abstraction, not full
> molecular dynamics.

## The contract

For each free ligand particle in the simulation, the per-frame update is

$$
\mathbf{x}(t + \Delta t) = \mathbf{x}(t) + \sqrt{2 D \Delta t}\,\boldsymbol{\xi} + \delta_{\text{attract}}(\mathbf{x}) + \delta_{\text{excl}}(\mathbf{x})
$$

where:

- $D$ is the per-frame diffusion coefficient in Å²/frame (configurable
  via `SimConfig.diffusion_coeff_a2_per_frame`; default 1).
- $\boldsymbol{\xi}$ is a 3-vector of independent standard normal samples.
- $\delta_{\text{attract}}$ is an optional weak shift toward the nearest
  unoccupied pocket. **Off by default in the test fixtures and one click
  away from off in the SimPanel UI.** See §"The encounter potential is
  honestly labelled" below.
- $\delta_{\text{excl}}$ is the hard-sphere repulsion that projects the
  particle outside each protein body's van-der-Waals sphere.

A binding event fires when an unbound particle's position enters a
pocket's docking sphere AND that pocket is currently unoccupied. The
particle is then held at the pocket centroid for a residence time
sampled from

$$
\tau \sim \mathrm{Exp}\!\left(\tau_0 \cdot e^{-\Delta G / RT}\right)
$$

with $\Delta G$ the cached docking affinity (kcal/mol) from Phase 3,
$R = 0.001987$ kcal·mol⁻¹·K⁻¹, $T$ the configured temperature, and
$\tau_0$ a configurable baseline in frames (default 10).

On release, the particle resumes free diffusion from the pocket centroid
position. Phase 4 implements release as resumed Brownian motion; Phase 8
adds the harmonic-restraint visualisation in the Mol* view for the
bound state.

## What the model captures

- **Overdamped Langevin / Brownian dynamics.** Property test
  `test_msd_scales_with_6_d_t` locks ⟨r²⟩ ≈ 6Dt within 10 % across 500
  particles × 100 steps. Free-particle MSD scaling is the gold-standard
  unit test for any Brownian integrator.
- **Real protein excluded volumes.** Protein bodies are spheres at their
  heavy-atom convex-hull radius. Particles are projected outside on
  every step (`_apply_protein_exclusion`).
- **Real binding-site positions.** Pocket centroids come from fpocket
  centroids on the actual loaded PDB, not from a Fibonacci sphere or a
  designer's intuition. Phase 3's `_pocket_centroid` reads the
  `pocketN_vert.pqr` alpha-sphere file directly.
- **Boltzmann-scaled residence times.** The 1 % accuracy of
  $\tau_A / \tau_B = e^{-(\Delta G_A - \Delta G_B)/RT}$ is locked by
  Hypothesis property test `test_ratio_within_one_percent_of_exp_formula`
  across 200 examples.
- **Competition between species** for a finite, first-come-first-served
  set of pocket sites. `test_no_negative_occupancy_in_competition`
  asserts the occupancy never exceeds 1 for a single-site / many-particle
  scenario across 500 frames.
- **Determinism under seed.** Same `SimConfig.seed` ⇒ bit-identical
  particle positions after 200 frames. Test:
  `test_same_seed_same_event_log`.
- **Stochastic fast-forward.** `Simulator.fast_forward(n_events)` samples
  binding events directly from the categorical distribution weighted by
  $e^{-\Delta G/RT}$, skipping integration. Useful for long-tail
  statistical accumulation that would otherwise take minutes of wall-
  clock animation.

## What the model does NOT capture

- **Induced fit and receptor flexibility.** The receptor is frozen
  during the kinetic phase. Conformational changes on binding are
  captured (indirectly) only insofar as the docking layer's ΔG already
  reflects them — but the kinetic simulation has no time-dependent
  receptor motion.
- **Allostery and conformational coupling between sites.** Each pocket
  is an independent kinetic trap; binding at site A has no effect on
  the affinity or accessibility of site B in the same protein.
- **Explicit solvent in the kinetic layer.** The docking-layer solvent
  model is whatever the engine (Smina, Vina, DiffDock, Boltz-2) uses.
  The kinetic step itself sees only the diffusion coefficient and the
  optional encounter potential.
- **Long-range electrostatics.** The encounter potential (when enabled)
  is a kinetic accelerator, not a physical force. See the next section.
- **Polarisability, charge transfer, covalent binding.** Out of scope —
  the whole pipeline assumes non-covalent, freely reversible binding.
- **Atomistic motion of the bound complex post-binding.** The atomistic
  view replays the docked pose under a harmonic restraint with thermal
  noise — it shows what binding *looks* like, it does not run MD on the
  bound complex. For atomistic dynamics of the bound state, Phase 10's
  session-bundle export will land with an "Export to OpenMM / GROMACS"
  hand-off in Phase 13.

## The encounter potential is honestly labelled

The optional attractive shift toward unoccupied pockets exists for a
single reason: without it, a researcher watching the abstract arena view
at 60 fps will wait several wall-clock minutes for the first binding
event with realistic D and µM-scale concentrations. The shift is a
deterministic vector of magnitude $\min(0.5D, 0.1d)$ pointing toward
the nearest unoccupied pocket centroid (where $d$ is the current
distance).

**This is not real electrostatics.** It is not implicit solvent. It is
not the average force a receptor exerts. It is a visualisation
accelerator that lets the user see the qualitative behaviour
(selectivity, competition, residence-time scaling) in seconds instead
of minutes.

The toggle (`use_attraction` in `SimConfig`, "Use encounter potential"
checkbox in the SimPanel) defaults to ON for the demo. The SimPanel
tooltip and this document both call out what it is.

For a publication-grade run, set `use_attraction = false` and let
plain diffusion deliver the encounter rate. Cross-check the resulting
selectivity ratios against the analytic Boltzmann prediction — they
agree within 5 % over 10 000 events, by design.

## Why this is the right abstraction for v1

The intended user runs hundreds of trials watching selectivity converge
across off-targets, not single high-fidelity MD trajectories. Boltzmann-
scaled residence times derived from real docking ΔG capture the
*relative* kinetic difference that drives selectivity, which is what
the researcher needs to see. Full MD would slow the loop by 4–5 orders
of magnitude with no proportional gain in qualitative insight.

When a researcher does want atomistic dynamics of the bound complex,
PInSilico's contract is to hand them a fully-prepared complex
(receptor + cofactors + docked ligand at the correct pH and ionic
strength) that they can drop into OpenMM, GROMACS, or Amber. That
hand-off is the Phase 10 / Phase 13 "Export to MD" action.

## References for the choices made here

- Frenkel & Smit, *Understanding Molecular Simulation*, ch. 4 on
  overdamped Langevin integrators.
- Northrup & McCammon, *J. Chem. Phys.* (1984), on Brownian-dynamics
  encounter rates and the validity of mean-field approximations.
- The fpocket paper (Le Guilloux et al., *BMC Bioinformatics* 2009) on
  alpha-sphere-based pocket detection and the meaning of the
  druggability score we surface as `Pocket.druggability_score`.
- The Smina paper (Koes et al., *J. Chem. Inf. Model.* 2013) on the
  scoring-function modifications that make Smina the default over plain
  AutoDock Vina.

This document is part of the codebase. If the simulator's behaviour
ever diverges from what is described here, that's a bug — open an issue.

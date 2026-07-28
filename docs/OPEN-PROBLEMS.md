# Open problems

A place for questions this project's contributors want stated precisely, so that
someone could actually attack them. Everything here follows one format, and the
format is the point:

1. **Setup** — the objects, named, with enough structure to be argued about.
2. **Obstruction** — what is already known, *including what already answers the
   question in the negative*. This section comes before the problem, not after.
3. **Problem** — what would count as a solution.
4. **Acceptance criteria** — what a submission must contain, including at least
   one number that could come out wrong.

The Obstruction section is what separates an open problem from a hunch. A
proposal that has not confronted the standard result contradicting it will be
dismissed on sight by anyone qualified to evaluate it, and that dismissal costs
the proposer a hearing they may not get twice.

**Nothing on this page is a claim that the standard theory is wrong.** These are
requests for a precise formulation.

---

## OP-1 — Boundary-determined interior dynamics for a body in a continuous medium

*Contributed by the maintainer. Status: **partially answered in the negative.**
The surviving open component is Problem A.*

### Origin of the question

The informal intuition: gravity might be understood through the mathematics of
how a *continuous* larger entity acts on discrete particles *inside* it — an
inverted Gaussian-surface problem, where the exterior determines the forces on
interior constituents through boundary data, with the universe itself as the
limiting case of the "larger particle".

Stated that way it is not yet a question. Below is what it becomes once the
existing physics is brought in — which turns out to split it into three claims,
one refuted, one already a large field, and one genuinely open and *logically
independent of the other two*.

### Setup

Let $(M, g)$ be a four-dimensional spacetime containing a compact material body
$B$. Let $\Sigma$ be a timelike hypersurface of finite radius enclosing $B$, with
induced three-metric $h_{ab}$ and extrinsic curvature $K_{ab}$; let the exterior
$M \setminus \mathrm{int}(\Sigma)$ carry a continuous distribution $T_{ab}$ — the
"larger entity". Write $D = (h_{ab}, K_{ab})$ for the boundary data, equivalently
the Brown–York boundary stress tensor.

### Obstruction — read this first

**If the exterior is static and spherically symmetric about $B$, the answer is
already known, and it is exactly zero.**

- **[Newton's shell theorem](https://en.wikipedia.org/wiki/Shell_theorem)** — a
  spherically symmetric shell exerts no net gravitational force on any object
  anywhere inside it.
- **[Gauss's law for gravity](https://en.wikipedia.org/wiki/Gauss%27s_law_for_gravity)**
  — flux through a closed surface depends only on the *enclosed* mass. Exterior
  mass contributes nothing. (Worth noting: Gauss's law fixes only the divergence
  of $\mathbf{g}$, not its curl, so boundary conditions do carry information the
  enclosed-mass statement alone does not.)
- **The corollary of Birkhoff's theorem is stronger still.** Melia
  ([MNRAS 382, 1917, 2007](https://academic.oup.com/mnras/article/382/4/1917/1152726))
  states it directly: the metric inside an empty spherical cavity at the centre
  of a spherically symmetric system is *exactly flat Minkowski* — "it matters not
  what the constituents of the medium outside the cavity are, as long as the
  medium is spherically symmetric", **even if that medium is infinite**.
- **The exact-solution version agrees.** An Einstein–Straus vacuole matched into
  an FLRW dust background feels no influence from the cosmic background
  ([Mars, Mena & Vera](https://arxiv.org/abs/1307.4371); see also
  [McVittie](https://arxiv.org/abs/1003.4777)).

This is not a technicality to be routed around. It is why FLRW cosmology admits a
Newtonian derivation, and why cosmic expansion does not stretch atoms, planets,
or the solar system. Since the cosmological principle asserts the universe is
isotropic about every point, **treating the universe as one large spherically
symmetric body makes its contribution to any interior region identically zero.**

There is a second conceptual problem with the cosmological framing: FLRW has no
exterior and no material boundary. The universe is not a body embedded in
something else, so "the exterior of the universe acting on its interior" does not
denote. Any such scheme needs an actual boundary surface, and the available
candidates are *horizons* — particle, Hubble, apparent, or local Rindler — which
is precisely where the existing screen-based derivations operate.

### What survives, and is genuinely active

The shell theorem kills only the monopole. Everything below it is real research:

- **Tidal and higher-multipole coupling** of the external universe to a body,
  formalised by [Thorne & Hartle](https://link.aps.org/doi/10.1103/PhysRevD.31.1815)
  (Phys. Rev. D **31**, 1815, 1985) via the Riemann curvature of the surrounding
  spacetime and matched asymptotic expansions — valid for arbitrarily strong
  self-gravity.
- **Rotational frame dragging.** [Brill & Cohen](https://link.aps.org/doi/10.1103/PhysRev.143.1011)
  (Phys. Rev. **143**, 1011, 1966): a rotating exterior shell drags the interior
  inertial frame, approaching full co-rotation in the strong-field limit. This is
  the exterior demonstrably acting on the interior.
- **How cosmological dynamics affects local systems** remains quantitatively
  unresolved — [Carrera & Giulini](https://arxiv.org/abs/0810.2712), *Rev. Mod.
  Phys.*, describe exact solutions as giving only partial insight.

### And the part that is already formalised, more precisely than the intuition

"The boundary encodes the exterior's influence" is standard, and the machinery is
mature:

- **[Israel junction conditions](https://link.springer.com/article/10.1007/BF02710419)**
  characterise interior/exterior matching entirely by the extrinsic curvature of
  the boundary.
- **[Brown–York quasilocal energy](https://arxiv.org/abs/gr-qc/9209012)** is
  obtained by differentiating the action with respect to the boundary
  three-metric, and depends on the total mean curvature of the spatial boundary.
  This is very nearly the literal "inverted Gaussian surface", and it already has
  the right Newtonian limit.
- **[ADM](https://arxiv.org/abs/gr-qc/0405109)** makes gravitational energy a
  boundary surface integral.
- **Holography of information** — in asymptotically flat quantum gravity the
  state outside a region fixes it inside: first
  [at null infinity](https://arxiv.org/abs/2002.02448), and more recently
  [for a ball of finite radius](https://arxiv.org/abs/2410.17316) in linearised
  quantum gravity. **This last paper is the closest published thing to the
  original picture and should be read first.**
- **"Continuous acting on discrete"** is [Sakharov's induced gravity](https://arxiv.org/abs/gr-qc/0204062)
  in one reading — gravity emerging from QFT as hydrodynamics emerges from
  molecular physics — and [Jacobson's derivation](https://arxiv.org/abs/gr-qc/9504004)
  of the Einstein equation as an equation of state from a boundary thermodynamic
  relation in another. [Verlinde's entropic gravity](https://arxiv.org/abs/1001.0785)
  is the most literal "a screen determines the force on interior matter", though
  it is [contested](https://arxiv.org/abs/1009.5414). For a discrete particle in
  a field it also sources, the technology is
  [gravitational self-force](https://arxiv.org/abs/1102.0529).

### Problem A (open)

Construct, **or prove impossible**, a formulation of the equations of motion of
$B$ in which the entire influence of the exterior enters only through the
boundary data $D$ on $\Sigma$, such that it:

1. reproduces **exactly zero** net monopole effect for a static spherically
   symmetric exterior (the Obstruction above);
2. reproduces in closed form the known nonzero effects — Thorne–Hartle tidal
   coupling and the Brill–Cohen dragging coefficient including its strong-field
   limit;
3. reduces to the Newtonian limit with the correct gravitational binding energy,
   as Brown–York already does;
4. **yields at least one quantitative prediction differing numerically from
   general relativity**, with a stated magnitude and a named observational
   channel: solar-system ephemerides, lunar laser ranging, pulsar timing, or
   galaxy rotation curves.

Condition 4 is the falsifiability criterion and it is not optional. A
construction satisfying 1–3 but not 4 is a *reformulation* of general relativity,
not a new physical claim, and should be reported as one. The cautionary example
is [shape dynamics](https://arxiv.org/abs/1010.2481): relational, elegant, and
provably equivalent to Einstein gravity in a fixed gauge — therefore making no
new predictions.

**Problem A-cosmological.** Take $\Sigma$ to be a horizon rather than a material
shell. Does there exist a choice of horizon and boundary data such that the
interior dynamics differs measurably from FLRW-plus-Einstein–Straus matching, and
if so by how much? Given Carrera & Giulini, a well-formulated answer here would
be a genuine contribution.

### Problem B (open, and independent of A)

**Is the gravitational field fundamentally classical?**

This is a respectable live question, not a fringe one — but it is a *separate*
one, and bundling it with Problem A weakens both. Nothing about a boundary
formulation implies gravity is classical, and nothing about classical gravity
implies a boundary formulation.

[Carlip's survey](https://iopscience.iop.org/article/10.1088/0264-9381/25/15/154010)
concludes the theoretical arguments against classical–quantum coupling are strong
but not conclusive, and the question is ultimately experimental.
[Oppenheim's postquantum classical gravity](https://arxiv.org/abs/1811.03116)
(Phys. Rev. X **13**, 041040, 2023) is a concrete consistent framework in which
the metric stays classical and stochastic, evading the no-go theorems, with a
falsifiable tradeoff between matter decoherence and metric diffusion. The
[BMV](https://arxiv.org/abs/1707.06050) /
[Marletto–Vedral](https://arxiv.org/abs/1707.06036) entanglement-witness
experiments are the intended discriminator.

Note that the interpretation of that test is *itself* now disputed: Aziz & Howl
argue classical gravity can generate entanglement once matter is treated in full
QFT ([Nature 646, 813, 2025](https://arxiv.org/abs/2510.19714)), and Gundhi,
Infantino & Bassi rebut that the effect comes from discarding transition
amplitudes ([arXiv:2604.19696](https://arxiv.org/abs/2604.19696)). As of July
2026 this is unresolved — **a clean statement of which observable actually
discriminates would itself be a useful contribution**, and is a far more
tractable target than Problem A.

### Acceptance criteria

A submission resolving **Problem A** must contain: the explicit map from boundary
data $D$ to the interior equations of motion; a demonstration of the Obstruction
limit; a recovery of the Brill–Cohen dragging coefficient; and one falsifiable
number with an error bar. A negative resolution must state a no-go theorem with
its hypotheses made explicit.

---

## Why this page is separate from the graph

The graph holds mathematics that is settled and checkable. This page holds
questions that are not. Mixing them would make both less useful — and a
repository that presents open speculation alongside machine-validated content,
without a visible boundary between them, invites a reader to discount the
validated part too.

If you want to add a problem here, use the format above. The Obstruction section
is mandatory, and writing it honestly is most of the work. If you cannot find
anything that already bears on your question, that is much more likely to mean
the search was not thorough than that the territory is empty.

"""Probability of Collision (Pc) — Foster 2-D method.

Replaces the geometric *proxy* in ``risk.py`` with a real, physically-grounded
collision probability. Public TLEs carry NO covariance, so we compute Pc under a
*documented assumed* covariance — always label results "Pc under assumed σ".

THE METHOD (Foster & Estes 1992). Reduce the 3-D encounter to a 2-D integral:

  1. At closest approach: relative position ``r_miss`` (⟂ v_rel, |r_miss| = miss
     distance) and relative velocity ``v_rel``.
  2. Encounter plane ⟂ v_rel; two orthonormal in-plane axes (x̂, ŷ).  ``encounter_basis``
  3. Combined covariance C = C_A + C_B (same ECI frame). TLEs → assume a diagonal
     RTN covariance per object, rotate to ECI.   ``rtn_to_eci_cov`` + ``assumed_rtn_sigma``
  4. Project onto the plane:  C_2D = P C Pᵀ,  P = [x̂; ŷ] (2×3).
  5. Hard-body radius HBR = radius_A + radius_B (assumed sizes).
  6. Pc = ∬_disk N(x; 0, C_2D) dx dy over the disk of radius HBR centered at the
     in-plane miss offset μ = (x̂·r_miss, ŷ·r_miss).   ``foster_pc``

Correctness anchor (tests/test_pc.py): isotropic σ, zero miss offset →
``Pc = 1 − exp(−HBR² / (2σ²))``.  Units: METERS internally; Pc is dimensionless.

References: Foster & Estes 1992 (NASA JSC-25898); Chan 2008; Alfano 2005; NASA CA
Handbook Appendix N; Flohrer et al. 2008 (TLE error magnitudes).
"""

from __future__ import annotations

import numpy as np

# Assumed defaults — Pc is very sensitive to these; document + tune (Flohrer 2008).
DEFAULT_HBR_M = 10.0          # combined hard-body radius (m): ~5 m + 5 m objects
DEFAULT_SIGMA_R_M = 200.0     # radial 1-σ (m)
DEFAULT_SIGMA_T_M = 500.0     # along-track 1-σ at epoch (m) — dominant for TLEs
DEFAULT_SIGMA_N_M = 200.0     # cross-track 1-σ (m)
DEFAULT_ALONGTRACK_GROWTH_M_PER_DAY = 1000.0   # σ_T grows ~1 km per day of TLE age


def assumed_rtn_sigma(tle_age_days: float = 0.0, alt_km: float | None = None) -> tuple:
    """Assumed (σ_R, σ_T, σ_N) in METERS for a TLE-propagated state.

    Convention (not derived physics): along-track dominates and grows with TLE age.
    """
    sr = DEFAULT_SIGMA_R_M
    st = DEFAULT_SIGMA_T_M + DEFAULT_ALONGTRACK_GROWTH_M_PER_DAY * max(tle_age_days, 0.0)
    sn = DEFAULT_SIGMA_N_M
    return (sr, st, sn)


def _rtn_axes(pos, vel):
    """Orthonormal RTN (radial, along-track, cross-track) unit vectors from a state."""
    pos = np.asarray(pos, float); vel = np.asarray(vel, float)
    R = pos / np.linalg.norm(pos)
    N = np.cross(pos, vel); N = N / np.linalg.norm(N)   # orbit normal (cross-track)
    T = np.cross(N, R)                                   # along-track (already unit)
    return R, T, N


def rtn_to_eci_cov(pos, vel, sigma_r, sigma_t, sigma_n) -> np.ndarray:
    """3×3 ECI position covariance from diagonal RTN sigmas.

    Q has columns (R̂, T̂, N̂) → maps RTN→ECI; C_eci = Q diag(σ²) Qᵀ.
    Rotation preserves the eigenvalues {σ_R², σ_T², σ_N²}.
    """
    R, T, N = _rtn_axes(pos, vel)
    Q = np.column_stack([R, T, N])
    D = np.diag([sigma_r ** 2, sigma_t ** 2, sigma_n ** 2])
    return Q @ D @ Q.T


def eci_to_rtn(pos, vel, vec) -> tuple:
    """Components of ``vec`` in the RTN frame of the state (pos, vel)."""
    R, T, N = _rtn_axes(pos, vel)
    vec = np.asarray(vec, float)
    return (float(vec @ R), float(vec @ T), float(vec @ N))


def encounter_basis(v_rel) -> tuple:
    """Two orthonormal 3-vectors (x̂, ŷ) spanning the plane ⟂ to v_rel."""
    v = np.asarray(v_rel, float)
    vn = v / np.linalg.norm(v)
    seed = np.array([1.0, 0.0, 0.0]) if abs(vn[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = np.cross(seed, vn); x = x / np.linalg.norm(x)
    y = np.cross(vn, x)                                   # unit, ⟂ x and vn
    return x, y


def foster_pc(r_miss, v_rel, cov_a_eci, cov_b_eci, hbr_m: float,
              n_rho: int = 160, n_phi: int = 160) -> float:
    """Foster 2-D probability of collision (inputs in METERS / m·s⁻¹)."""
    r_miss = np.asarray(r_miss, float)
    x, y = encounter_basis(v_rel)
    P = np.vstack([x, y])                                 # 2×3
    C = np.asarray(cov_a_eci, float) + np.asarray(cov_b_eci, float)
    C2 = P @ C @ P.T                                      # 2×2 combined, projected
    det = C2[0, 0] * C2[1, 1] - C2[0, 1] * C2[1, 0]
    if not np.isfinite(det) or det <= 0:
        return 0.0
    Cinv = np.linalg.inv(C2)
    mu = np.array([x @ r_miss, y @ r_miss])              # in-plane miss offset
    a, b, c = Cinv[0, 0], Cinv[0, 1], Cinv[1, 1]
    norm = 1.0 / (2.0 * np.pi * np.sqrt(det))

    # vectorized polar quadrature over the disk of radius hbr, centered at mu
    rho = np.linspace(0.0, hbr_m, n_rho)
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    drho = hbr_m / (n_rho - 1) if n_rho > 1 else hbr_m
    dphi = 2.0 * np.pi / n_phi
    RHO = rho[:, None]
    X = mu[0] + RHO * np.cos(phi)[None, :]
    Y = mu[1] + RHO * np.sin(phi)[None, :]
    quad = a * X * X + 2.0 * b * X * Y + c * Y * Y        # xᵀ C2⁻¹ x
    integrand = norm * np.exp(-0.5 * quad) * RHO          # RHO = polar Jacobian
    pc = float(integrand.sum() * drho * dphi)
    return min(max(pc, 0.0), 1.0)


def max_pc(r_miss, v_rel, cov_a_eci, cov_b_eci, hbr_m: float) -> float:
    """Worst-case Pc: scale the combined covariance so the miss sits at ~1σ.

    A standard sanity bound — the largest Pc achievable by inflating/deflating the
    (assumed) covariance isotropically. Useful because Pc is so covariance-sensitive.
    """
    x, y = encounter_basis(v_rel)
    P = np.vstack([x, y])
    C2 = P @ (np.asarray(cov_a_eci, float) + np.asarray(cov_b_eci, float)) @ P.T
    mu = np.array([x @ np.asarray(r_miss, float), y @ np.asarray(r_miss, float)])
    d2 = float(mu @ mu)
    if d2 <= 0:
        return foster_pc(r_miss, v_rel, cov_a_eci, cov_b_eci, hbr_m)
    # scale so the trace-normalized covariance places the miss at 1σ (classic max-Pc)
    scale = d2 / max(np.trace(C2) / 2.0, 1e-12)
    return foster_pc(r_miss, v_rel, cov_a_eci * scale, cov_b_eci * scale, hbr_m)


def pc_for_event(r_miss_km, v_rel_kms, pos_a_km, vel_a_kms, pos_b_km, vel_b_kms,
                 tle_age_days_a=0.0, tle_age_days_b=0.0, hbr_m=DEFAULT_HBR_M) -> float:
    """Glue: assumed covariances → foster_pc, converting km → m."""
    r_miss = np.asarray(r_miss_km, float) * 1000.0
    v_rel = np.asarray(v_rel_kms, float) * 1000.0
    pa, va = np.asarray(pos_a_km, float) * 1000.0, np.asarray(vel_a_kms, float) * 1000.0
    pb, vb = np.asarray(pos_b_km, float) * 1000.0, np.asarray(vel_b_kms, float) * 1000.0
    ca = rtn_to_eci_cov(pa, va, *assumed_rtn_sigma(tle_age_days_a))
    cb = rtn_to_eci_cov(pb, vb, *assumed_rtn_sigma(tle_age_days_b))
    return foster_pc(r_miss, v_rel, ca, cb, hbr_m)

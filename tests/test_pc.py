"""Milestone A target — implement src/orbitguard/risk_pc.py until these pass.

Run:  python tests/test_pc.py      (or: python -m pytest tests/test_pc.py -q)

They will FAIL until you fill in the TODOs in risk_pc.py. That's intentional —
this is test-driven: each test tells you exactly what your function must satisfy.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from orbitguard import risk_pc  # noqa: E402


# --- encounter_basis: two orthonormal vectors perpendicular to v_rel ----------
def test_encounter_basis_orthonormal():
    v = np.array([7500.0, 1200.0, -300.0])   # some relative velocity (m/s)
    x, y = risk_pc.encounter_basis(v)
    x, y = np.asarray(x, float), np.asarray(y, float)
    assert abs(np.linalg.norm(x) - 1) < 1e-9       # unit length
    assert abs(np.linalg.norm(y) - 1) < 1e-9
    assert abs(np.dot(x, y)) < 1e-9                # orthogonal to each other
    assert abs(np.dot(x, v)) < 1e-6                # both perpendicular to v_rel
    assert abs(np.dot(y, v)) < 1e-6


# --- rtn_to_eci_cov: rotation preserves trace/eigenvalues ---------------------
def test_rtn_cov_symmetric_and_eigenvalues():
    pos = np.array([7000e3, 0.0, 0.0])       # meters
    vel = np.array([0.0, 7546.0, 0.0])       # meters/s (roughly circular LEO)
    sr, st, sn = 200.0, 500.0, 300.0
    C = np.asarray(risk_pc.rtn_to_eci_cov(pos, vel, sr, st, sn), float)
    assert C.shape == (3, 3)
    assert np.allclose(C, C.T, atol=1e-6)                     # symmetric
    # rotation preserves the set of variances (eigenvalues):
    eig = np.sort(np.linalg.eigvalsh(C))
    assert np.allclose(eig, np.sort([sr**2, st**2, sn**2]), rtol=1e-6)


# --- foster_pc: the correctness anchor (closed form) --------------------------
def test_pc_isotropic_zero_offset_closed_form():
    sigma, hbr = 100.0, 20.0                  # meters
    C = sigma**2 * np.eye(3)                   # isotropic -> projects to sigma^2 * I2
    v_rel = np.array([7500.0, 0.0, 0.0])
    r_miss = np.array([0.0, 0.0, 0.0])         # zero miss offset
    pc = risk_pc.foster_pc(r_miss, v_rel, C, np.zeros((3, 3)), hbr)
    expected = 1.0 - np.exp(-hbr**2 / (2 * sigma**2))   # Rayleigh CDF
    assert abs(pc - expected) < 2e-3, f"pc={pc:.5f} expected={expected:.5f}"


# --- foster_pc: monotonicity sanity ------------------------------------------
def test_pc_increases_with_hbr():
    sigma = 150.0
    C = sigma**2 * np.eye(3)
    v = np.array([7500.0, 0.0, 0.0])
    r = np.array([0.0, 100.0, 0.0])           # 100 m miss, in-plane
    small = risk_pc.foster_pc(r, v, C, np.zeros((3, 3)), 5.0)
    big = risk_pc.foster_pc(r, v, C, np.zeros((3, 3)), 30.0)
    assert big > small > 0                     # bigger target -> higher Pc


def test_pc_decreases_as_miss_grows():
    sigma = 150.0
    C = sigma**2 * np.eye(3)
    v = np.array([7500.0, 0.0, 0.0])
    near = risk_pc.foster_pc(np.array([0., 50., 0.]), v, C, np.zeros((3, 3)), 15.0)
    far = risk_pc.foster_pc(np.array([0., 800., 0.]), v, C, np.zeros((3, 3)), 15.0)
    assert near > far                          # closer pass -> higher Pc


# --- assumed_rtn_sigma: altitude + age scaled covariance model -----------------
def test_assumed_sigma_returns_triple_meters():
    s = risk_pc.assumed_rtn_sigma(0.0, 550.0)
    assert len(s) == 3
    sr, st, sn = s
    # at epoch the model returns the documented baselines (metres)
    assert abs(sr - risk_pc.DEFAULT_SIGMA_R_M) < 1e-9
    assert abs(st - risk_pc.DEFAULT_SIGMA_T_M) < 1e-6
    assert abs(sn - risk_pc.DEFAULT_SIGMA_N_M) < 1e-6


def test_along_track_grows_with_age():
    young = risk_pc.assumed_rtn_sigma(0.0, 800.0)[1]
    old = risk_pc.assumed_rtn_sigma(5.0, 800.0)[1]
    assert old > young                              # σ_T grows with TLE age


def test_low_altitude_has_larger_along_track():
    age = 3.0
    low = risk_pc.assumed_rtn_sigma(age, 400.0)[1]   # deep LEO, heavy drag
    high = risk_pc.assumed_rtn_sigma(age, 1500.0)[1]  # high LEO, light drag
    assert low > high                                # drag → faster along-track growth


def test_cross_track_grows_with_age():
    young = risk_pc.assumed_rtn_sigma(0.0, 800.0)[2]
    old = risk_pc.assumed_rtn_sigma(6.0, 800.0)[2]
    assert old > young                              # σ_N grows mildly with age


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  ok   {fn.__name__}"); passed += 1
        except NotImplementedError as e:
            print(f"  TODO {fn.__name__}: {e}")
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
    if passed == len(fns):
        print(f"\n{passed}/{len(fns)} passing — Foster 2-D Pc verified (incl. closed form).")
    else:
        print(f"\n{passed}/{len(fns)} passing. Implement the risk_pc.py TODOs to turn these green.")

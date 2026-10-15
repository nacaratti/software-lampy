import numpy as np
from scipy.interpolate import interp1d
from typing import Union, Tuple
from pint import Quantity
from fibersim.core.units import ureg

_H_PLANCK = 6.62607015e-34  # J*s
_C_LIGHT = 299792458.0       # m/s
_K_BOLTZMANN = 1.380649e-23  # J/K


def _mccumber_emission_cross_section(
    wavelengths_m: np.ndarray,
    sigma_abs: np.ndarray,
    lambda_zero_line_m: float,
    temperature_k: float = 300.0,
) -> np.ndarray:
    """Derives the emission cross-section from the absorption cross-section
    via the McCumber relation (McCumber, Phys. Rev. 136, A954, 1964) — the
    standard approach for quasi-three-level rare-earth transitions (Yb, Er)
    used throughout the literature (e.g. Giles & Desurvire 1991 for EDFAs):

        sigma_em(lambda) = sigma_abs(lambda) * exp[hc*(1/lambda_zl - 1/lambda) / (k*T)]

    `lambda_zero_line_m` is the "zero-line" wavelength — the 0-0 transition
    between the lowest Stark sublevels of the upper and lower manifolds,
    identifiable spectroscopically as the wavelength where measured
    absorption and emission cross-sections coincide.
    """
    wl = np.asarray(wavelengths_m, dtype=float)
    energy_term = _H_PLANCK * _C_LIGHT * (1.0 / lambda_zero_line_m - 1.0 / wl)
    return np.asarray(sigma_abs, dtype=float) * np.exp(energy_term / (_K_BOLTZMANN * temperature_k))


def _interp_table_nm(wls_nm: np.ndarray, anchor_nm, anchor_val, *, zero_outside: bool = True) -> np.ndarray:
    """Piecewise-linear interpolation from sparse (wavelength_nm, value) anchor
    points onto a fine wavelength grid, zeroing outside the anchors' own range
    (rather than np.interp's default of extending the edge value) so multiple
    disjoint bands can be summed onto a shared grid without contaminating
    regions outside where they were defined."""
    anchor_nm = np.asarray(anchor_nm, dtype=float)
    anchor_val = np.asarray(anchor_val, dtype=float)
    values = np.interp(wls_nm, anchor_nm, anchor_val)
    if zero_outside:
        values = np.where((wls_nm >= anchor_nm[0]) & (wls_nm <= anchor_nm[-1]), values, 0.0)
    return values


class ActiveIon:
    """
    Represents an active dopant ion (e.g., Yb3+, Er3+, Tm3+) in a glass matrix.

    Attributes:
        name (str): Name of the active ion.
        lifetime (float): Upper state spontaneous emission lifetime (seconds).
        wavelengths (np.ndarray): Wavelength grid in meters.
        sigma_abs (np.ndarray): Absorption cross-sections in m^2.
        sigma_em (np.ndarray): Emission cross-sections in m^2.
    """
    def __init__(
        self,
        name: str,
        lifetime: float,
        wavelengths: np.ndarray,
        sigma_abs: np.ndarray,
        sigma_em: np.ndarray,
        upconversion_coeff_m3_s: float = 0.0,
    ):
        self.name = name
        self.lifetime = lifetime
        self.wavelengths = np.asarray(wavelengths)
        self.sigma_abs = np.asarray(sigma_abs)
        self.sigma_em = np.asarray(sigma_em)
        # Cooperative (homogeneous) upconversion coefficient C_up (m^3/s): an
        # extra N2-dependent decay path N2/tau -> N2/tau + C_up*N2^2 from
        # ion-ion energy transfer between two excited neighbors, one of which
        # gets kicked to a higher (non-lasing) state and lost. Standard model
        # for concentration-quenching ESA/upconversion loss in heavily-doped
        # Er fiber (Myslinski et al., "Performance of high concentration
        # erbium doped fiber amplifiers", IEEE PTL 1997); zero for ions/host
        # combinations where this isn't the dominant excited-state process.
        self.upconversion_coeff_m3_s = upconversion_coeff_m3_s

        # Setup interpolators for cross-sections (fill outer range with 0)
        self._abs_interp = interp1d(self.wavelengths, self.sigma_abs, kind='linear', bounds_error=False, fill_value=0.0)
        self._em_interp = interp1d(self.wavelengths, self.sigma_em, kind='linear', bounds_error=False, fill_value=0.0)

    def get_cross_sections(self, wavelength: Union[float, Quantity]) -> Tuple[float, float]:
        """
        Retrieves interpolated absorption and emission cross-sections.

        Arguments:
            wavelength (Union[float, Quantity]): Wavelength. If float, assumed in meters.

        Returns:
            Tuple[float, float]: (sigma_abs, sigma_em) in m^2.
        """
        if isinstance(wavelength, Quantity):
            wl_m = wavelength.to("meter").magnitude
        else:
            wl_m = float(wavelength)

        sig_a = float(self._abs_interp(wl_m))
        sig_e = float(self._em_interp(wl_m))
        return sig_a, sig_e

    @classmethod
    def create_yb3(cls) -> "ActiveIon":
        """Ytterbium (Yb3+) ion model in silica glass.

        Absorption cross-sections are anchored to the widely-reproduced
        Yb-silica spectral shape (Pask et al. 1995, "Ytterbium-doped silica
        fiber lasers", IEEE JSTQE; also Paschotta's RP Photonics Yb-doped
        fiber reference data): a sharp main peak at ~976 nm (~2.5e-24 m^2)
        with a broader shoulder at ~915 nm. Emission is *derived* from
        absorption via the McCumber relation (not independently guessed),
        which is the standard treatment for this quasi-three-level ion and
        correctly reproduces the well-known spectroscopic fact that
        absorption and emission cross-sections coincide at the ~975.5 nm
        zero-line, with emission exceeding absorption at longer wavelengths
        (the basis of Yb's usable 1030-1100 nm gain band).
        """
        lambda_zero_line = 975.5e-9

        anchor_nm = [860, 890, 900, 910, 915, 920, 930, 940, 950, 955, 960, 965,
                     970, 973, 975.5, 978, 980, 985, 990, 1000, 1010, 1020, 1030,
                     1040, 1050, 1064, 1080, 1100, 1150]
        anchor_abs_e24 = [0.02, 0.12, 0.30, 0.60, 0.85, 0.80, 0.60, 0.45, 0.50,
                          0.60, 0.75, 1.05, 1.55, 2.05, 2.50, 2.35, 2.20, 1.70,
                          1.10, 0.45, 0.15, 0.09, 0.057, 0.033, 0.0204, 0.00775,
                          0.00233, 0.000433, 0.00003]

        wls_nm = np.linspace(860.0, 1150.0, 59)
        wls_m = wls_nm * 1e-9
        sig_abs = _interp_table_nm(wls_nm, anchor_nm, anchor_abs_e24, zero_outside=False) * 1e-24
        sig_em = _mccumber_emission_cross_section(wls_m, sig_abs, lambda_zero_line)

        return cls("Yb3+", lifetime=0.85e-3, wavelengths=wls_m, sigma_abs=sig_abs, sigma_em=sig_em)

    @classmethod
    def create_er3(cls) -> "ActiveIon":
        """Erbium (Er3+) ion model for C/L-band simulation.

        Absorption cross-sections follow the standard Er-silica C-band shape
        (Giles & Desurvire, "Modeling Erbium-Doped Fiber Amplifiers", IEEE
        JLT 1991; Miniscalco & Quimby zero-line treatment): asymmetric peak
        at ~1530 nm with a shoulder near 1480-1500 nm. Emission is derived
        via the same McCumber relation used in that reference for gain
        spectra (rather than an independently-fit curve), with the
        zero-line at ~1530 nm matching where absorption and emission
        cross-sections are known to coincide for Er-doped silica.

        Also carries a nonzero cooperative-upconversion coefficient
        (see `upconversion_coeff_m3_s` docs above) representing the
        ⁴I13/2 + ⁴I13/2 -> ⁴I9/2 + ⁴I15/2 excited-state pair process that
        measurably reduces quantum efficiency in moderately-to-heavily
        Er-doped fiber — the dominant ESA/upconversion loss mechanism for
        this ion at typical EDFA doping levels.
        """
        lambda_zero_line = 1530e-9

        anchor_nm = [1450, 1460, 1470, 1480, 1490, 1500, 1510, 1520, 1525, 1530,
                     1535, 1540, 1550, 1560, 1570, 1580, 1600, 1620, 1650]
        anchor_abs_e24 = [0.05, 0.08, 0.11, 0.15, 0.13, 0.11, 0.14, 0.22, 0.27,
                          0.30, 0.28, 0.22, 0.12, 0.05, 0.02, 0.008, 0.002,
                          0.0005, 0.0001]

        wls_nm_c = np.linspace(1450.0, 1650.0, 41)
        sig_abs_c = _interp_table_nm(wls_nm_c, anchor_nm, anchor_abs_e24, zero_outside=False) * 1e-24
        sig_em_c = _mccumber_emission_cross_section(wls_nm_c * 1e-9, sig_abs_c, lambda_zero_line)

        # ⁴I15/2 -> ⁴I11/2 pump band (~980 nm), modeled the standard way for
        # an effective two-level EDFA model (Giles & Desurvire 1991): an
        # absorption-only band, since ⁴I11/2 decays non-radiatively to ⁴I13/2
        # in ~µs, so stimulated emission at the pump is negligible. Peak
        # ~2.5e-25 m^2 near 979 nm for alumino-germanosilicate hosts.
        pump_anchor_nm = [940, 955, 965, 972, 976, 979, 982, 986, 992, 1000, 1010]
        pump_anchor_abs_e24 = [0.0, 0.03, 0.08, 0.16, 0.22, 0.25, 0.22, 0.14, 0.06, 0.015, 0.0]
        wls_nm_p = np.linspace(940.0, 1010.0, 36)
        sig_abs_p = _interp_table_nm(wls_nm_p, pump_anchor_nm, pump_anchor_abs_e24) * 1e-24
        sig_em_p = np.zeros_like(sig_abs_p)

        # Explicit zeros in the gap so the linear interpolator doesn't
        # bridge the two bands with a spurious ramp across 1010-1450 nm.
        gap_nm = np.array([1020.0, 1440.0])
        wls_m = np.concatenate([wls_nm_p, gap_nm, wls_nm_c]) * 1e-9
        sig_abs = np.concatenate([sig_abs_p, np.zeros(2), sig_abs_c])
        sig_em = np.concatenate([sig_em_p, np.zeros(2), sig_em_c])

        return cls("Er3+", lifetime=10.0e-3, wavelengths=wls_m, sigma_abs=sig_abs, sigma_em=sig_em,
                    upconversion_coeff_m3_s=8e-24)

    @classmethod
    def create_tm3(cls) -> "ActiveIon":
        """Thulium (Tm3+) ion model for 2 um band simulation.

        Two distinct spectral features, modeled separately since they belong
        to different electronic manifolds (not McCumber-conjugate pairs):
        - A ~790 nm ground-state absorption band (3H6 -> 3H4), the standard
          pump wavelength for cladding-pumped Tm fiber lasers/amplifiers —
          this is what enables the "2-for-1" cross-relaxation upconversion
          (2x Yb3+-like ions populated per absorbed 790 nm pump photon) that
          gives Tm its characteristically high slope efficiency.
        - The 3F4 <-> 3H6 laser transition band (~1600-2100 nm emission,
          with weak in-band absorption below ~1750 nm), kept as an empirical
          fit (not McCumber-derived, unlike Yb/Er above) since this ion's
          Stark splitting and zero-line are less consistently reported in
          the literature to derive it with confidence.
        """
        pump_anchor_nm = [760, 770, 780, 785, 790, 795, 800, 810, 820, 830]
        pump_anchor_abs_e24 = [0.05, 0.20, 0.55, 0.85, 1.10, 0.95, 0.60, 0.25, 0.10, 0.03]

        laser_anchor_nm = [1600, 1650, 1700, 1750, 1800, 1850, 1880, 1900, 1950, 2000, 2050, 2100]
        laser_anchor_abs_e24 = [0.9, 0.5, 0.25, 0.08, 0.02, 0.005, 0.002, 0.001, 0.0003, 0.0001, 0.00003, 0.00001]
        laser_anchor_em_e24 = [0.02, 0.05, 0.10, 0.25, 0.45, 0.58, 0.60, 0.55, 0.42, 0.28, 0.15, 0.07]

        wls_nm = np.linspace(750.0, 2100.0, 136)
        wls_m = wls_nm * 1e-9

        pump_band = _interp_table_nm(wls_nm, pump_anchor_nm, pump_anchor_abs_e24) * 1e-24
        laser_abs = _interp_table_nm(wls_nm, laser_anchor_nm, laser_anchor_abs_e24) * 1e-24
        laser_em = _interp_table_nm(wls_nm, laser_anchor_nm, laser_anchor_em_e24) * 1e-24

        sig_abs = pump_band + laser_abs
        sig_em = laser_em

        return cls("Tm3+", lifetime=0.3e-3, wavelengths=wls_m, sigma_abs=sig_abs, sigma_em=sig_em)

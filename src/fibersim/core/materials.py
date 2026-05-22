import math
from typing import Union
from pint import Quantity
from fibersim.core.units import ureg

# Sellmeier coefficients for Silica (SiO2)
# Reference: Malitson, I. H. (1965). Interspecimen comparison of the refractive index of fused silica.
SILICA_B = [0.6961663, 0.4079426, 0.8974794]
SILICA_C = [0.0684043**2, 0.1162414**2, 9.896161**2]  # in microns^2

# Sellmeier coefficients for Germania (GeO2)
# Reference: Fleming, J. W. (1984). Dispersion in GeO2-SiO2 glasses.
GERMANIA_B = [0.80686642, 0.71815848, 0.85416831]
GERMANIA_C = [0.06897262**2, 0.15341426**2, 11.841931**2]  # in microns^2

# Sellmeier coefficients for a typical Phosphate glass
# Reference: Literature values for standard phosphate laser glass (e.g. LHG-8 or Q-98)
PHOSPHATE_B = [1.2065, 0.1519, 0.8872]
PHOSPHATE_C = [0.01015, 0.0436, 101.4]  # in microns^2


def wavelength_to_um(wavelength: Union[float, Quantity]) -> float:
    """Convert wavelength to micrometers for Sellmeier formulas.

    Pint quantities use their native unit. Plain floats use meters when
    ``wavelength < 1e-3`` (e.g. 1550e-9 m), otherwise micrometers (legacy).
    """
    if isinstance(wavelength, Quantity):
        return wavelength.to("micrometer").magnitude
    wl = float(wavelength)
    if wl < 1e-3:
        return wl * 1e6
    return wl


def sellmeier_index(wavelength_um: float, B: list, C: list) -> float:
    """Calculates refractive index squared and returns refractive index."""
    w2 = wavelength_um**2
    n2 = 1.0
    for bi, ci in zip(B, C):
        n2 += (bi * w2) / (w2 - ci)
    return math.sqrt(max(n2, 1.0))


class Material:
    """Base class for optical materials."""
    def __init__(self, name: str):
        self.name = name

    def refractive_index(self, wavelength: Union[float, Quantity]) -> float:
        """Returns refractive index at a given wavelength (meters if float < 1e-3)."""
        raise NotImplementedError


class Silica(Material):
    """Fused Silica (SiO2) glass."""
    def __init__(self):
        super().__init__("Silica")

    def refractive_index(self, wavelength: Union[float, Quantity]) -> float:
        return sellmeier_index(wavelength_to_um(wavelength), SILICA_B, SILICA_C)


class Germanosilicate(Material):
    """Germanium-doped Silica glass (GeO2-SiO2)."""
    def __init__(self, molar_fraction_geo2: float):
        """
        Arguments:
            molar_fraction_geo2 (float): Mole fraction of GeO2 (between 0.0 and 1.0).
        """
        super().__init__(f"Germanosilicate ({molar_fraction_geo2 * 100:.1f}% GeO2)")
        self.x = max(0.0, min(molar_fraction_geo2, 1.0))

    def refractive_index(self, wavelength: Union[float, Quantity]) -> float:
        wl_um = wavelength_to_um(wavelength)
        n_silica = sellmeier_index(wl_um, SILICA_B, SILICA_C)
        n_germania = sellmeier_index(wl_um, GERMANIA_B, GERMANIA_C)
        # Linear interpolation of refractive index squared
        n2 = (1 - self.x) * (n_silica**2) + self.x * (n_germania**2)
        return math.sqrt(max(n2, 1.0))


class Phosphate(Material):
    """Phosphate glass."""
    def __init__(self):
        super().__init__("Phosphate")

    def refractive_index(self, wavelength: Union[float, Quantity]) -> float:
        return sellmeier_index(wavelength_to_um(wavelength), PHOSPHATE_B, PHOSPHATE_C)

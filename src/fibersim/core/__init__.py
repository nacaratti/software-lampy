"""Core physical models: units, constants, materials, ions, fibers."""

from fibersim.core.units import ureg, Quantity, Length, Wavelength, Power, Frequency
from fibersim.core.materials import Material, Silica, Germanosilicate, Phosphate
from fibersim.core.ions import ActiveIon
from fibersim.core.fiber import (
    FiberGeometry,
    StepIndexFiber,
    GradedIndexFiber,
    DoubleCladFiber,
    ActiveFiber,
)

__all__ = [
    "ureg",
    "Quantity",
    "Length",
    "Wavelength",
    "Power",
    "Frequency",
    "Material",
    "Silica",
    "Germanosilicate",
    "Phosphate",
    "ActiveIon",
    "FiberGeometry",
    "StepIndexFiber",
    "GradedIndexFiber",
    "DoubleCladFiber",
    "ActiveFiber",
]

import pint
from pydantic import BeforeValidator
from typing import Annotated

# Create a shared unit registry for fibersim
ureg = pint.UnitRegistry()
Quantity = ureg.Quantity

# Helper to validate and convert custom quantities using Pydantic
def validate_quantity(v, unit: str) -> pint.Quantity:
    if isinstance(v, (int, float)):
        return v * ureg(unit)
    if isinstance(v, str):
        return ureg(v)
    if isinstance(v, pint.Quantity):
        return v.to(unit)
    raise ValueError(f"Cannot parse value {v} as unit {unit}")

# Predefined annotated types for Pint + Pydantic integration
Length = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "meter"))]
Frequency = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "hertz"))]
Power = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "watt"))]
Wavelength = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "meter"))]
Density = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "1/meter**3"))]
Lifetime = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "second"))]
Area = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "meter**2"))]
CrossSection = Annotated[pint.Quantity, BeforeValidator(lambda v: validate_quantity(v, "meter**2"))]

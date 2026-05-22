import math
from fibersim.core.units import ureg

# Speed of light in vacuum (m/s)
C_LIGHT = 299792458 * ureg("meter / second")

# Planck constant (J * s)
H_PLANCK = 6.62607015e-34 * ureg("joule * second")

# Reduced Planck constant (J * s)
H_BAR = (6.62607015e-34 / (2 * math.pi)) * ureg("joule * second")

# Vacuum permittivity (F/m or A**2 * s**4 / (kg * m**3))
EPSILON_0 = 8.8541878128e-12 * ureg("farad / meter")

# Elementary charge (Coulombs)
E_CHARGE = 1.602176634e-19 * ureg("coulomb")

# Boltzmann constant (J/K)
K_BOLTZMANN = 1.380649e-23 * ureg("joule / kelvin")

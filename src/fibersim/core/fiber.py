import math
import numpy as np
from typing import Union
from pint import Quantity
from fibersim.core.units import ureg
from fibersim.core.materials import Material, Silica
from fibersim.core.ions import ActiveIon

class FiberGeometry:
    """Base class for fiber geometry models."""
    def __init__(self, core_radius: Union[float, Quantity], cladding_radius: Union[float, Quantity]):
        """
        Arguments:
            core_radius (Union[float, Quantity]): Core radius. If float, assumed in meters.
            cladding_radius (Union[float, Quantity]): Cladding radius. If float, assumed in meters.
        """
        self.core_radius = core_radius.to("meter").magnitude if isinstance(core_radius, Quantity) else float(core_radius)
        self.cladding_radius = cladding_radius.to("meter").magnitude if isinstance(cladding_radius, Quantity) else float(cladding_radius)

    def refractive_index_profile(self, r: Union[float, np.ndarray], wavelength: Union[float, Quantity]) -> Union[float, np.ndarray]:
        """Returns the refractive index at radial position r and given wavelength."""
        raise NotImplementedError

    def mode_solving_cladding_radius(self) -> float:
        """Radial position used as the cladding index reference for mode/V-number solvers."""
        return self.cladding_radius


class StepIndexFiber(FiberGeometry):
    """Standard step-index fiber geometry."""
    def __init__(
        self,
        core_radius: Union[float, Quantity],
        cladding_radius: Union[float, Quantity],
        core_material: Union[Material, float],
        cladding_material: Union[Material, float]
    ):
        """
        Arguments:
            core_radius: core radius.
            cladding_radius: cladding radius.
            core_material: Material instance or constant refractive index float.
            cladding_material: Material instance or constant refractive index float.
        """
        super().__init__(core_radius, cladding_radius)
        self.core_mat = core_material
        self.cladding_mat = cladding_material

    def refractive_index_profile(self, r: Union[float, np.ndarray], wavelength: Union[float, Quantity]) -> Union[float, np.ndarray]:
        # Compute core and cladding indices at wavelength
        if isinstance(self.core_mat, Material):
            n_co = self.core_mat.refractive_index(wavelength)
        else:
            n_co = float(self.core_mat)

        if isinstance(self.cladding_mat, Material):
            n_cl = self.cladding_mat.refractive_index(wavelength)
        else:
            n_cl = float(self.cladding_mat)

        # Profile evaluation
        r_arr = np.asarray(r)
        n_prof = np.where(np.abs(r_arr) <= self.core_radius, n_co, n_cl)
        
        if n_prof.ndim == 0:
            return float(n_prof)
        return n_prof


class GradedIndexFiber(FiberGeometry):
    """Parabolic or power-law graded-index fiber geometry."""
    def __init__(
        self,
        core_radius: Union[float, Quantity],
        cladding_radius: Union[float, Quantity],
        n_peak: Union[Material, float],
        n_cladding: Union[Material, float],
        alpha: float = 2.0
    ):
        """
        Arguments:
            alpha (float): Profile parameter (alpha = 2.0 is parabolic).
        """
        super().__init__(core_radius, cladding_radius)
        self.n_peak = n_peak
        self.n_cladding = n_cladding
        self.alpha = float(alpha)

    def refractive_index_profile(self, r: Union[float, np.ndarray], wavelength: Union[float, Quantity]) -> Union[float, np.ndarray]:
        n_co = self.n_peak.refractive_index(wavelength) if isinstance(self.n_peak, Material) else float(self.n_peak)
        n_cl = self.n_cladding.refractive_index(wavelength) if isinstance(self.n_cladding, Material) else float(self.n_cladding)

        delta = (n_co**2 - n_cl**2) / (2 * n_co**2)
        r_arr = np.asarray(r)

        # Formula: n^2(r) = n_co^2 * [1 - 2 * delta * (r/a)^alpha] for r <= a, and n_cl for r > a
        norm_r = np.abs(r_arr) / self.core_radius
        n2_core = n_co**2 * (1.0 - 2.0 * delta * (norm_r ** self.alpha))
        n_core = np.sqrt(np.maximum(n2_core, n_cl**2))
        
        n_prof = np.where(np.abs(r_arr) <= self.core_radius, n_core, n_cl)
        if n_prof.ndim == 0:
            return float(n_prof)
        return n_prof


class DoubleCladFiber(FiberGeometry):
    """Double-clad fiber geometry for high-power active devices."""
    def __init__(
        self,
        core_radius: Union[float, Quantity],
        inner_cladding_radius: Union[float, Quantity],
        outer_cladding_radius: Union[float, Quantity],
        core_material: Union[Material, float],
        inner_cladding_material: Union[Material, float],
        outer_cladding_material: Union[Material, float]
    ):
        super().__init__(core_radius, outer_cladding_radius)
        self.inner_cladding_radius = inner_cladding_radius.to("meter").magnitude if isinstance(inner_cladding_radius, Quantity) else float(inner_cladding_radius)
        self.core_mat = core_material
        self.inner_cladding_mat = inner_cladding_material
        self.outer_cladding_mat = outer_cladding_material

    def mode_solving_cladding_radius(self) -> float:
        """Core modes are guided against the inner cladding, not the outer jacket."""
        return self.inner_cladding_radius

    def refractive_index_profile(self, r: Union[float, np.ndarray], wavelength: Union[float, Quantity]) -> Union[float, np.ndarray]:
        n_co = self.core_mat.refractive_index(wavelength) if isinstance(self.core_mat, Material) else float(self.core_mat)
        n_cl1 = self.inner_cladding_mat.refractive_index(wavelength) if isinstance(self.inner_cladding_mat, Material) else float(self.inner_cladding_mat)
        n_cl2 = self.outer_cladding_mat.refractive_index(wavelength) if isinstance(self.outer_cladding_mat, Material) else float(self.outer_cladding_mat)

        r_arr = np.asarray(r)
        
        # Determine index based on radial layers
        n_prof = np.where(
            np.abs(r_arr) <= self.core_radius,
            n_co,
            np.where(np.abs(r_arr) <= self.inner_cladding_radius, n_cl1, n_cl2)
        )
        if n_prof.ndim == 0:
            return float(n_prof)
        return n_prof


class ActiveFiber:
    """
    Couples a fiber geometry with a distribution of active dopant ions.
    """
    def __init__(
        self,
        geometry: FiberGeometry,
        ion: ActiveIon,
        dopant_density_core: float,
        dopant_profile_type: str = "uniform"
    ):
        """
        Arguments:
            geometry (FiberGeometry): The optical waveguide geometry.
            ion (ActiveIon): The spectroscopic model of the active ion.
            dopant_density_core (float): Peak dopant density in ions/m^3.
            dopant_profile_type (str): Profile distribution ('uniform' inside core, or 'gaussian' with std=core_radius).
        """
        self.geometry = geometry
        self.ion = ion
        self.N_max = float(dopant_density_core)
        self.profile_type = dopant_profile_type.lower()

    def dopant_density_profile(self, r: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Returns the local active ion density in ions/m^3 at radial coordinate r."""
        r_arr = np.asarray(r)
        
        if self.profile_type == "uniform":
            density = np.where(np.abs(r_arr) <= self.geometry.core_radius, self.N_max, 0.0)
        elif self.profile_type == "gaussian":
            # Gaussian doping profile: exp(-r^2 / w^2) where w = core_radius
            density = self.N_max * np.exp(-(r_arr / self.geometry.core_radius)**2)
        else:
            raise ValueError(f"Unknown doping profile type: {self.profile_type}")
            
        if density.ndim == 0:
            return float(density)
        return density

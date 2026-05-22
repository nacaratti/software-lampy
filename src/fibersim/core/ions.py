import numpy as np
from scipy.interpolate import interp1d
from typing import Union, Tuple
from pint import Quantity
from fibersim.core.units import ureg

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
        sigma_em: np.ndarray
    ):
        self.name = name
        self.lifetime = lifetime
        self.wavelengths = np.asarray(wavelengths)
        self.sigma_abs = np.asarray(sigma_abs)
        self.sigma_em = np.asarray(sigma_em)
        
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
        """Creates a default Ytterbium (Yb3+) ion model in silica glass."""
        # Standard Yb-silica spectrum from 900 nm to 1100 nm
        wls_nm = np.linspace(900.0, 1100.0, 41)
        wls_m = wls_nm * 1e-9
        
        # Simplified but realistic spectral profile matching Pask/Paschotta curves:
        # Peak absorption around 976 nm (~2.5e-24 m^2), secondary around 915 nm.
        # Peak emission around 976 nm (~2.5e-24 m^2), secondary around 1030 nm (~0.5e-24 m^2).
        sig_abs = np.zeros_like(wls_nm)
        sig_em = np.zeros_like(wls_nm)
        
        for idx, wl in enumerate(wls_nm):
            # Absorption model: peak at 975.5, peak at 915
            abs_val = (2.5e-24 * np.exp(-((wl - 975.5)/4.0)**2) + 
                       0.8e-24 * np.exp(-((wl - 915.0)/20.0)**2) +
                       0.1e-24 * np.exp(-((wl - 1030.0)/40.0)**2))
            
            # Emission model: peak at 975.5, secondary peak at 1030
            em_val = (2.5e-24 * np.exp(-((wl - 975.5)/4.0)**2) + 
                      0.6e-24 * np.exp(-((wl - 1030.0)/30.0)**2) +
                      0.3e-24 * np.exp(-((wl - 1060.0)/40.0)**2))
            
            sig_abs[idx] = abs_val
            sig_em[idx] = em_val
            
        return cls("Yb3+", lifetime=0.85e-3, wavelengths=wls_m, sigma_abs=sig_abs, sigma_em=sig_em)

    @classmethod
    def create_er3(cls) -> "ActiveIon":
        """Creates a default Erbium (Er3+) ion model for C-band simulation."""
        # Standard Er-silica spectrum from 1450 nm to 1650 nm
        wls_nm = np.linspace(1450.0, 1650.0, 41)
        wls_m = wls_nm * 1e-9
        
        sig_abs = np.zeros_like(wls_nm)
        sig_em = np.zeros_like(wls_nm)
        
        for idx, wl in enumerate(wls_nm):
            # Absorption: peak at 1530 nm
            abs_val = 0.7e-24 * np.exp(-((wl - 1530.0)/12.0)**2) + 0.15e-24 * np.exp(-((wl - 1480.0)/30.0)**2)
            # Emission: peak at 1530 nm, tail up to 1600 nm
            em_val = 0.75e-24 * np.exp(-((wl - 1530.0)/12.0)**2) + 0.35e-24 * np.exp(-((wl - 1550.0)/25.0)**2)
            
            sig_abs[idx] = abs_val
            sig_em[idx] = em_val
            
        return cls("Er3+", lifetime=10.0e-3, wavelengths=wls_m, sigma_abs=sig_abs, sigma_em=sig_em)

    @classmethod
    def create_tm3(cls) -> "ActiveIon":
        """Creates a default Thulium (Tm3+) ion model for 2 um band simulation."""
        # Standard Tm-silica spectrum from 1600 nm to 2100 nm
        wls_nm = np.linspace(1600.0, 2100.0, 51)
        wls_m = wls_nm * 1e-9
        
        sig_abs = np.zeros_like(wls_nm)
        sig_em = np.zeros_like(wls_nm)
        
        for idx, wl in enumerate(wls_nm):
            # Thulium absorption peak around 790/1650/1700 nm
            abs_val = 0.9e-24 * np.exp(-((wl - 1650.0)/60.0)**2) + 0.3e-24 * np.exp(-((wl - 1800.0)/100.0)**2)
            # Thulium emission peak around 1900 nm
            em_val = 0.6e-24 * np.exp(-((wl - 1880.0)/80.0)**2) + 0.4e-24 * np.exp(-((wl - 1950.0)/100.0)**2)
            
            sig_abs[idx] = abs_val
            sig_em[idx] = em_val
            
        return cls("Tm3+", lifetime=0.3e-3, wavelengths=wls_m, sigma_abs=sig_abs, sigma_em=sig_em)

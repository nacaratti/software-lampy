import numpy as np
from scipy import linalg

def calculate_uniform_fbg(n_eff, period_nm, length_mm, dn,
                          wl_start_nm, wl_end_nm, num_points=1000):
    """
    Calculate reflectivity spectrum for a uniform Fiber Bragg Grating.
    Uses coupled-mode theory to compute the reflectivity as a function of wavelength.
    """
    period = period_nm * 1e-9
    length = length_mm * 1e-3

    wavelengths_nm = np.linspace(wl_start_nm, wl_end_nm, num_points)
    wavelengths = wavelengths_nm * 1e-9

    bragg_wavelength = 2 * n_eff * period
    bragg_wavelength_nm = bragg_wavelength * 1e9

    kappa = (np.pi * dn) / bragg_wavelength

    delta_beta = 2 * np.pi * n_eff * (1.0/wavelengths - 1.0/bragg_wavelength)

    reflectivity = np.zeros_like(wavelengths, dtype=float)

    gamma_squared = kappa**2 - delta_beta**2
    stop_band_mask = gamma_squared > 0
    pass_band_mask = ~stop_band_mask

    if np.any(stop_band_mask):
        gamma = np.sqrt(gamma_squared[stop_band_mask])
        tanh_gL = np.tanh(gamma * length)
        num = (kappa**2) * (tanh_gL**2)
        den = (gamma**2) + (delta_beta[stop_band_mask]**2) * (tanh_gL**2)
        reflectivity[stop_band_mask] = np.where(den != 0, num / den, 0.0)

    if np.any(pass_band_mask):
        gamma_prime = np.sqrt(-gamma_squared[pass_band_mask])
        sin_gL = np.sin(gamma_prime * length)
        cos_gL = np.cos(gamma_prime * length)
        num = (kappa**2) * (sin_gL**2)
        den = (gamma_prime**2) * (cos_gL**2) + (delta_beta[pass_band_mask]**2) * (sin_gL**2)
        reflectivity[pass_band_mask] = np.where(den != 0, num / den, 0.0)

    # Clean up outputs
    reflectivity = np.clip(reflectivity, 0.0, 1.0)
    peak_reflectivity = float(np.max(reflectivity))
    fwhm_nm = calculate_fwhm(wavelengths_nm, reflectivity)
    bandwidth_3db_nm = calculate_bandwidth_3db(wavelengths_nm, reflectivity)

    metadata = {
        'bragg_wavelength_nm': float(bragg_wavelength_nm),
        'fwhm_nm': float(fwhm_nm) if fwhm_nm is not None else None,
        'peak_reflectivity': peak_reflectivity,
        'bandwidth_3db_nm': float(bandwidth_3db_nm) if bandwidth_3db_nm is not None else None,
        'kappa': float(kappa),
        'grating_type': 'Uniform FBG'
    }

    return wavelengths_nm, reflectivity, metadata


def calculate_chirped_fbg(n_eff, period_start_nm, period_end_nm,
                          length_mm, dn, chirp_type='linear',
                          wl_start_nm=None, wl_end_nm=None, num_points=1000, num_sections=500):
    """
    Calculate reflectivity spectrum for a chirped Fiber Bragg Grating.
    Uses transfer matrix method by dividing the grating into many sections.
    """
    period_start = period_start_nm * 1e-9
    period_end = period_end_nm * 1e-9
    length = length_mm * 1e-3

    bragg_start = 2 * n_eff * period_start
    bragg_end = 2 * n_eff * period_end

    if wl_start_nm is None:
        wl_start_nm = min(bragg_start, bragg_end) * 1e9 - 10.0
    if wl_end_nm is None:
        wl_end_nm = max(bragg_start, bragg_end) * 1e9 + 10.0

    wavelengths_nm = np.linspace(wl_start_nm, wl_end_nm, num_points)
    wavelengths = wavelengths_nm * 1e-9

    z = np.linspace(0, length, num_sections + 1)
    dz = z[1] - z[0]
    z_centers = (z[:-1] + z[1:]) / 2.0

    if chirp_type == 'linear':
        C = (period_end - period_start) / length
        periods = period_start + C * z_centers
    elif chirp_type == 'quadratic':
        C = (period_end - period_start) / (length**2)
        periods = period_start + C * (z_centers**2)
    else:
        raise ValueError(f"Unknown chirp type: {chirp_type}")

    reflectivity = np.zeros(len(wavelengths))

    for i, wavelength in enumerate(wavelengths):
        T_total = np.eye(2, dtype=complex)

        for j, period_j in enumerate(periods):
            lambda_B = 2.0 * n_eff * period_j
            kappa = (np.pi * dn) / lambda_B
            delta = 2.0 * np.pi * n_eff * (1.0/wavelength - 1.0/lambda_B)
            gamma_sq = kappa**2 - delta**2

            if gamma_sq > 0:
                gamma = np.sqrt(gamma_sq)
                cosh_gz = np.cosh(gamma * dz)
                sinh_gz = np.sinh(gamma * dz)

                T11 = cosh_gz - 1j * (delta / gamma) * sinh_gz
                T12 = -1j * (kappa / gamma) * sinh_gz
                T21 = 1j * (kappa / gamma) * sinh_gz
                T22 = cosh_gz + 1j * (delta / gamma) * sinh_gz
            else:
                gamma_prime = np.sqrt(-gamma_sq)
                cos_gz = np.cos(gamma_prime * dz)
                sin_gz = np.sin(gamma_prime * dz)

                T11 = cos_gz - 1j * (delta / gamma_prime) * sin_gz
                T12 = -1j * (kappa / gamma_prime) * sin_gz
                T21 = 1j * (kappa / gamma_prime) * sin_gz
                T22 = cos_gz + 1j * (delta / gamma_prime) * sin_gz

            T_section = np.array([[T11, T12], [T21, T22]], dtype=complex)
            T_total = T_section @ T_total

        r = T_total[1, 0] / T_total[0, 0]
        reflectivity[i] = np.abs(r)**2

    reflectivity = np.clip(reflectivity, 0.0, 1.0)
    peak_reflectivity = float(np.max(reflectivity))
    fwhm_nm = calculate_fwhm(wavelengths_nm, reflectivity)
    bandwidth_3db_nm = calculate_bandwidth_3db(wavelengths_nm, reflectivity)
    bragg_center_nm = (bragg_start + bragg_end) / 2.0 * 1e9

    metadata = {
        'bragg_wavelength_nm': float(bragg_center_nm),
        'bragg_start_nm': float(bragg_start * 1e9),
        'bragg_end_nm': float(bragg_end * 1e9),
        'fwhm_nm': float(fwhm_nm) if fwhm_nm is not None else None,
        'peak_reflectivity': peak_reflectivity,
        'bandwidth_3db_nm': float(bandwidth_3db_nm) if bandwidth_3db_nm is not None else None,
        'chirp_type': chirp_type,
        'grating_type': 'Chirped FBG'
    }

    return wavelengths_nm, reflectivity, metadata


def calculate_apodized_fbg(n_eff, period_nm, length_mm, dn_peak,
                           apodization_profile='gaussian', profile_strength=1.0,
                           wl_start_nm=None, wl_end_nm=None, num_points=1000, num_sections=500):
    """
    Calculate reflectivity spectrum for an apodized Fiber Bragg Grating.
    Uses transfer matrix method with spatially varying index modulation.
    """
    period = period_nm * 1e-9
    length = length_mm * 1e-3

    bragg_wavelength = 2.0 * n_eff * period
    bragg_wavelength_nm = bragg_wavelength * 1e9

    if wl_start_nm is None:
        wl_start_nm = bragg_wavelength_nm - 5.0
    if wl_end_nm is None:
        wl_end_nm = bragg_wavelength_nm + 5.0

    wavelengths_nm = np.linspace(wl_start_nm, wl_end_nm, num_points)
    wavelengths = wavelengths_nm * 1e-9

    z = np.linspace(0, length, num_sections + 1)
    dz = z[1] - z[0]
    z_centers = (z[:-1] + z[1:]) / 2.0
    z_norm = (z_centers - length/2.0) / (length/2.0)

    if apodization_profile == 'gaussian':
        sigma = max(profile_strength * 0.5, 0.01)
        apodization = np.exp(-(z_norm / sigma)**2)
    elif apodization_profile == 'raised_cosine':
        apodization = np.cos(np.pi * z_norm / 2.0)**2
    elif apodization_profile == 'tanh':
        edge_width = 0.2 / max(profile_strength, 0.01)
        apodization = 0.5 * (np.tanh((z_norm + 1.0) / edge_width) - np.tanh((z_norm - 1.0) / edge_width))
    elif apodization_profile == 'hamming':
        apodization = 0.54 - 0.46 * np.cos(np.pi * (z_norm + 1.0))
    else:
        raise ValueError(f"Unknown apodization profile: {apodization_profile}")

    # Scale using strength parameter
    apodization = profile_strength * apodization + (1.0 - profile_strength)
    dn_z = dn_peak * apodization

    reflectivity = np.zeros(len(wavelengths))

    for i, wavelength in enumerate(wavelengths):
        T_total = np.eye(2, dtype=complex)
        delta = 2.0 * np.pi * n_eff * (1.0/wavelength - 1.0/bragg_wavelength)

        for j, dn_j in enumerate(dn_z):
            kappa = (np.pi * dn_j) / bragg_wavelength
            gamma_sq = kappa**2 - delta**2

            if gamma_sq > 0:
                gamma = np.sqrt(gamma_sq)
                cosh_gz = np.cosh(gamma * dz)
                sinh_gz = np.sinh(gamma * dz)

                T11 = cosh_gz - 1j * (delta / gamma) * sinh_gz
                T12 = -1j * (kappa / gamma) * sinh_gz
                T21 = 1j * (kappa / gamma) * sinh_gz
                T22 = cosh_gz + 1j * (delta / gamma) * sinh_gz
            else:
                gamma_prime = np.sqrt(-gamma_sq)
                cos_gz = np.cos(gamma_prime * dz)
                sin_gz = np.sin(gamma_prime * dz)

                T11 = cos_gz - 1j * (delta / gamma_prime) * sin_gz
                T12 = -1j * (kappa / gamma_prime) * sin_gz
                T21 = 1j * (kappa / gamma_prime) * sin_gz
                T22 = cos_gz + 1j * (delta / gamma_prime) * sin_gz

            T_section = np.array([[T11, T12], [T21, T22]], dtype=complex)
            T_total = T_section @ T_total

        r = T_total[1, 0] / T_total[0, 0]
        reflectivity[i] = np.abs(r)**2

    reflectivity = np.clip(reflectivity, 0.0, 1.0)
    peak_reflectivity = float(np.max(reflectivity))
    fwhm_nm = calculate_fwhm(wavelengths_nm, reflectivity)
    bandwidth_3db_nm = calculate_bandwidth_3db(wavelengths_nm, reflectivity)

    metadata = {
        'bragg_wavelength_nm': float(bragg_wavelength_nm),
        'fwhm_nm': float(fwhm_nm) if fwhm_nm is not None else None,
        'peak_reflectivity': peak_reflectivity,
        'bandwidth_3db_nm': float(bandwidth_3db_nm) if bandwidth_3db_nm is not None else None,
        'apodization_profile': apodization_profile,
        'profile_strength': float(profile_strength),
        'grating_type': 'Apodized FBG'
    }

    return wavelengths_nm, reflectivity, metadata


def calculate_tilted_fbg(n_eff_core, n_eff_cladding_base, period_nm, length_mm,
                          dn, tilt_angle_deg, fiber_radius_um=62.5,
                          num_cladding_modes=10, wl_start_nm=None, wl_end_nm=None,
                          num_points=1000):
    """
    Calculate transmission spectrum for a tilted Fiber Bragg Grating.
    """
    period = period_nm * 1e-9
    length = length_mm * 1e-3
    tilt_angle_rad = np.deg2rad(tilt_angle_deg)

    cladding_mode_indices = []
    for m in range(1, num_cladding_modes + 1):
        # Slightly decreasing effective refractive index
        n_eff_clad_m = n_eff_cladding_base - 0.001 * m
        cladding_mode_indices.append(n_eff_clad_m)

    resonance_wavelengths = []
    for n_clad in cladding_mode_indices:
        lambda_res = (n_eff_core - n_clad) * period / np.cos(tilt_angle_rad)
        resonance_wavelengths.append(lambda_res * 1e9)

    if wl_start_nm is None:
        wl_start_nm = min(resonance_wavelengths) - 20.0
    if wl_end_nm is None:
        wl_end_nm = max(resonance_wavelengths) + 20.0

    wavelengths_nm = np.linspace(wl_start_nm, wl_end_nm, num_points)
    wavelengths = wavelengths_nm * 1e-9

    transmission = np.ones(len(wavelengths))

    for i, (lambda_res_val, n_clad) in enumerate(zip(resonance_wavelengths, cladding_mode_indices)):
        lambda_res_m = lambda_res_val * 1e-9
        kappa_clad = (np.pi * dn) / lambda_res_m * np.sin(tilt_angle_rad)
        delta_clad = 2.0 * np.pi * (n_eff_core - n_clad) * (1.0/wavelengths - 1.0/lambda_res_m)
        gamma_sq = kappa_clad**2 - delta_clad**2

        coupling = np.zeros_like(wavelengths)

        stop_band_mask = gamma_sq > 0
        if np.any(stop_band_mask):
            gamma = np.sqrt(gamma_sq[stop_band_mask])
            tanh_gL = np.tanh(gamma * length)
            num = (kappa_clad**2) * (tanh_gL**2)
            den = (gamma**2) + (delta_clad[stop_band_mask]**2) * (tanh_gL**2)
            coupling[stop_band_mask] = np.where(den != 0, num / den, 0.0)

        pass_band_mask = ~stop_band_mask
        if np.any(pass_band_mask):
            gamma_prime = np.sqrt(-gamma_sq[pass_band_mask])
            sin_gL = np.sin(gamma_prime * length)
            cos_gL = np.cos(gamma_prime * length)
            num = (kappa_clad**2) * (sin_gL**2)
            den = (gamma_prime**2) * (cos_gL**2) + (delta_clad[pass_band_mask]**2) * (sin_gL**2)
            coupling[pass_band_mask] = np.where(den != 0, num / den, 0.0)

        transmission -= coupling * 0.5

    transmission = np.clip(transmission, 0.0, 1.0)
    min_transmission = float(np.min(transmission))

    metadata = {
        'tilt_angle_deg': float(tilt_angle_deg),
        'num_cladding_modes': num_cladding_modes,
        'resonance_wavelengths_nm': [float(w) for w in resonance_wavelengths],
        'min_transmission': min_transmission,
        'grating_type': 'Tilted FBG'
    }

    return wavelengths_nm, transmission, metadata


def calculate_lpg(n_eff_core, n_eff_cladding, period_um, length_mm, dn,
                  target_mode_order=2, wl_start_nm=None, wl_end_nm=None,
                  num_points=1000):
    """
    Calculate transmission spectrum for a Long Period Grating (LPG).
    """
    period = period_um * 1e-6
    length = length_mm * 1e-3

    # For LPG, coupling is co-propagating: resonance λ = (n_core - n_clad) * Λ
    resonance_wavelength = (n_eff_core - n_eff_cladding) * period
    resonance_wavelength_nm = resonance_wavelength * 1e9

    if wl_start_nm is None:
        wl_start_nm = resonance_wavelength_nm - 50.0
    if wl_end_nm is None:
        wl_end_nm = resonance_wavelength_nm + 50.0

    wavelengths_nm = np.linspace(wl_start_nm, wl_end_nm, num_points)
    wavelengths = wavelengths_nm * 1e-9

    kappa = (np.pi * dn) / resonance_wavelength
    delta = 2.0 * np.pi * (n_eff_core - n_eff_cladding) * (1.0/wavelengths - 1.0/resonance_wavelength)

    gamma_sq = kappa**2 + delta**2
    gamma = np.sqrt(np.abs(gamma_sq))

    transmission = 1.0 - (kappa / gamma)**2 * np.sin(gamma * length)**2
    transmission = np.clip(transmission, 0.0, 1.0)

    min_transmission = float(np.min(transmission))
    dip_depth_db = float(-10 * np.log10(min_transmission)) if min_transmission > 0 else float('inf')

    metadata = {
        'resonance_wavelength_nm': float(resonance_wavelength_nm),
        'target_mode_order': target_mode_order,
        'min_transmission': min_transmission,
        'dip_depth_db': dip_depth_db,
        'period_um': float(period_um),
        'grating_type': 'Long Period Grating (LPG)'
    }

    return wavelengths_nm, transmission, metadata


# Utility functions
def _phase_mask_viability(period_nm: float) -> tuple:
    """Return (viable: bool, message: str) based on phase mask period."""
    if period_nm < 400:
        return False, "Período muito pequeno para fabricação convencional (< 400 nm)"
    elif period_nm < 500:
        return True, "Viável com e-beam lithography de alta precisão"
    elif period_nm < 1000:
        return True, "Viável com fotolitografia UV padrão"
    elif period_nm < 5000:
        return True, "Facilmente fabricável com fotolitografia convencional"
    else:
        return True, "Período grande — considere fabricação holográfica ou direta"


def _phase_mask_technique(period_nm: float) -> str:
    if period_nm < 500:
        return "E-beam lithography"
    elif period_nm < 1500:
        return "Fotolitografia UV (DUV ou I-line)"
    else:
        return "Fotolitografia convencional ou holográfica"


def calculate_phase_mask(
    grating_type: str,
    n_eff: float,
    length_mm: float,
    dn: float,
    period_nm: float = 535.0,
    period_end_nm: float = 536.0,
    chirp_type: str = 'linear',
    apodization_profile: str = 'gaussian',
    profile_strength: float = 1.0,
    lambda_uv_nm: float = 248.0,
    num_sections: int = 500,
) -> dict:
    """
    Compute phase mask profile for FBG inscription via UV exposure.

    Phase mask period Λ_pm = 2 × Λ_FBG so that the ±1 diffraction orders
    interfere and produce fringes with period Λ_FBG satisfying λ_B = 2 n_eff Λ_FBG.

    Also computes the UV diffraction geometry, viability assessment, and
    manufacturing recommendations following the reference FBG phase mask calculator.

    Returns spatial profiles of:
    - period_pm_nm: phase mask period Λ_pm(z) [nm]
    - dn_profile:   index modulation δn(z)
    - kappa_profile: coupling coefficient κ(z) [1/m]
    - phase_rad:    accumulated grating phase φ(z) [rad]
    - params:       summary including diffraction angle and fabrication notes
    """
    length = length_mm * 1e-3
    z = np.linspace(0.0, length, num_sections)

    if grating_type in ('uniform', 'tilted'):
        period_fbg_nm = np.full(num_sections, period_nm)
        dn_profile = np.full(num_sections, dn)

    elif grating_type == 'chirped':
        if chirp_type == 'linear':
            C = (period_end_nm - period_nm) / length_mm
            period_fbg_nm = period_nm + C * (z * 1e3)
        else:  # quadratic
            C = (period_end_nm - period_nm) / (length_mm ** 2)
            period_fbg_nm = period_nm + C * (z * 1e3) ** 2
        dn_profile = np.full(num_sections, dn)

    elif grating_type == 'apodized':
        period_fbg_nm = np.full(num_sections, period_nm)
        z_norm = (z - length / 2.0) / (length / 2.0)
        if apodization_profile == 'gaussian':
            sigma = max(profile_strength * 0.5, 0.01)
            apod = np.exp(-(z_norm / sigma) ** 2)
        elif apodization_profile == 'raised_cosine':
            apod = np.cos(np.pi * z_norm / 2.0) ** 2
        elif apodization_profile == 'tanh':
            edge = 0.2 / max(profile_strength, 0.01)
            apod = 0.5 * (np.tanh((z_norm + 1.0) / edge) - np.tanh((z_norm - 1.0) / edge))
        elif apodization_profile == 'hamming':
            apod = 0.54 - 0.46 * np.cos(np.pi * (z_norm + 1.0))
        else:
            apod = np.ones(num_sections)
        apod = profile_strength * apod + (1.0 - profile_strength)
        dn_profile = dn * apod

    else:  # lpg or unknown
        period_fbg_nm = np.full(num_sections, period_nm)
        dn_profile = np.full(num_sections, dn)

    period_pm_nm = 2.0 * period_fbg_nm  # Λ_pm = 2 × Λ_FBG
    period_pm_center = float(np.mean(period_pm_nm))

    # Bragg wavelength: λ_B = n_eff × Λ_pm (at center)
    bragg_nm = float(n_eff * period_pm_center)
    lambda_B = bragg_nm * 1e-9

    kappa_profile = np.pi * dn_profile / lambda_B

    # Accumulated grating phase: φ(z) = ∫₀ᶻ 2π/Λ_FBG dz'
    period_fbg_m = period_fbg_nm * 1e-9
    dz = (z[1] - z[0]) if num_sections > 1 else length
    phase_rad = np.cumsum(2.0 * np.pi / period_fbg_m * dz)

    # UV diffraction geometry: sin(θ) = λ_UV / Λ_pm
    sin_theta = lambda_uv_nm / period_pm_center
    if abs(sin_theta) <= 1.0:
        diffraction_angle_deg = float(np.degrees(np.arcsin(sin_theta)))
    else:
        diffraction_angle_deg = None  # UV wavelength too long for this mask period

    # Viability and manufacturing
    viable, viability_msg = _phase_mask_viability(period_pm_center)
    technique = _phase_mask_technique(period_pm_center)
    required_precision_nm = period_pm_center * 0.005  # 0.5% of period

    params = {
        'grating_type': grating_type,
        'bragg_wavelength_nm': bragg_nm,
        'period_pm_center_nm': period_pm_center,
        'period_pm_min_nm': float(np.min(period_pm_nm)),
        'period_pm_max_nm': float(np.max(period_pm_nm)),
        'length_mm': length_mm,
        'dn_peak': float(np.max(dn_profile)),
        'dn_min': float(np.min(dn_profile)),
        'kappa_peak': float(np.max(kappa_profile)),
        'kappa_L_product': float(np.max(kappa_profile) * length),
        'phase_total_rad': float(phase_rad[-1]),
        'phase_total_cycles': float(phase_rad[-1] / (2.0 * np.pi)),
        # UV writing geometry
        'lambda_uv_nm': lambda_uv_nm,
        'diffraction_angle_deg': diffraction_angle_deg,
        # Fabrication info
        'viable': viable,
        'viability_message': viability_msg,
        'recommended_technique': technique,
        'required_precision_nm': float(required_precision_nm),
        'typical_fluence': '100–500 mJ/cm²',
    }

    return {
        'z_mm': (z * 1e3).tolist(),
        'period_pm_nm': period_pm_nm.tolist(),
        'dn_profile': dn_profile.tolist(),
        'kappa_profile': kappa_profile.tolist(),
        'phase_rad': phase_rad.tolist(),
        'params': params,
    }


def calculate_fwhm(wavelengths, spectrum):
    try:
        peak_value = np.max(spectrum)
        half_max = peak_value / 2.0

        above_half = spectrum >= half_max
        if not np.any(above_half):
            return None

        indices = np.where(above_half)[0]
        if len(indices) < 2:
            return None

        fwhm = wavelengths[indices[-1]] - wavelengths[indices[0]]
        return float(fwhm)
    except:
        return None


def calculate_bandwidth_3db(wavelengths, spectrum):
    try:
        peak_value = np.max(spectrum)
        threshold = peak_value / np.sqrt(2.0)

        above_threshold = spectrum >= threshold
        if not np.any(above_threshold):
            return None

        indices = np.where(above_threshold)[0]
        if len(indices) < 2:
            return None

        bandwidth = wavelengths[indices[-1]] - wavelengths[indices[0]]
        return float(bandwidth)
    except:
        return None

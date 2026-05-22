from fastapi import APIRouter, HTTPException
from backend.app.schemas.thermal import ThermalCalculationRequest, ThermalCalculationResponse
from backend.app.services.encoders import encode_array
from fibersim.solvers.thermal.cavity import solve_laser_rate_equations, calculate_thermal_cavity

router = APIRouter(prefix="/api/thermal", tags=["thermal"])

@router.post("/calculate", response_model=ThermalCalculationResponse)
def calculate_thermal(req: ThermalCalculationRequest) -> ThermalCalculationResponse:
    try:
        # 1. Solve active laser cavity power distributions
        laser_res = solve_laser_rate_equations(
            fiber_length=req.fiber_length_m,
            core_radius=req.core_radius_um * 1e-6,
            clad_radius=req.clad_radius_um * 1e-6,
            coating_radius=req.coating_radius_um * 1e-6,
            N_total=req.N_total,
            tau=req.tau_ms * 1e-3,
            lambda_pump=req.lambda_pump_nm * 1e-9,
            lambda_signal=req.lambda_signal_nm * 1e-9,
            gamma_pump=req.gamma_pump,
            gamma_signal=req.gamma_signal,
            P_pump_forward=req.P_pump_forward_w,
            P_pump_backward=req.P_pump_backward_w,
            P_signal_seed=req.P_signal_seed_w,
            pumping=req.pumping,
            num_points=req.num_z_points,
        )
        
        # 2. Solve active 2D thermal distribution
        thermal_res = calculate_thermal_cavity(
            laser_res,
            core_radius=req.core_radius_um * 1e-6,
            clad_radius=req.clad_radius_um * 1e-6,
            coating_radius=req.coating_radius_um * 1e-6,
            lambda_pump=req.lambda_pump_nm * 1e-9,
            lambda_signal=req.lambda_signal_nm * 1e-9,
            k_core=req.k_core,
            k_clad=req.k_clad,
            k_coat=req.k_coat,
            h_conv=req.h_conv,
            T_ambient=req.T_ambient_celsius + 273.15,
            num_radial=req.num_r_points,
        )
        
        # Format outputs
        z_list = laser_res['z'].tolist()
        pumps_f = laser_res['P_pump_forward'].tolist()
        pumps_b = laser_res['P_pump_backward'].tolist()
        pumps_t = laser_res['P_pump'].tolist()
        sigs = laser_res['P_signal'].tolist()
        n2_f = (laser_res['N2'] / req.N_total).tolist()
        
        r_list_um = (thermal_res['r'] * 1e6).tolist()
        T_center = (thermal_res['T_center'] - 273.15).tolist()
        T_surface = (thermal_res['T_surface'] - 273.15).tolist()
        
        return ThermalCalculationResponse(
            z_m=z_list,
            pumps_forward=pumps_f,
            pumps_backward=pumps_b,
            pumps_total=pumps_t,
            signals_forward=sigs,
            n2_fraction=n2_f,
            r_um=r_list_um,
            T_center_celsius=T_center,
            T_surface_celsius=T_surface,
            T_2d=encode_array(thermal_res['T_2d'] - 273.15), # return in Celsius
            gain_db=laser_res['gain_db'],
            efficiency=laser_res['efficiency'],
            output_power_w=laser_res['output_power'],
            T_max_celsius=thermal_res['T_max_celsius'],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thermal simulation error: {str(e)}")

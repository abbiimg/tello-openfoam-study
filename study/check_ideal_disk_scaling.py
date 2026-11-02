"""Internal consistency check against analytic isolated-disk hover theory.

This is NOT additional CFD, a measured motor map, or hardware validation.
Only the two original completed finest-grid flat references are compared.
"""
from pathlib import Path
import json
import math


def main():
    out = Path(__file__).resolve().parent/'results'
    info = json.loads((out/'statistics.json').read_text())
    comparisons = []
    for n in (4,8):
        name = f'fine_n{n}_e19.2923_d1000_az0000'
        row = next(r for r in info['cases'] if r['case'] == name)
        pe = row['battery_power_W']
        axial = .5*.6*(.95*(pe-.5)-n*.1)
        area = n*math.pi*(row['diameter_m']/2)**2
        ideal = (axial*math.sqrt(2*1.225*area))**(2/3)
        comparisons.append(dict(case=name,nominal_assumed_axial_power_W=axial,
            isolated_disk_area_sum_m2=area,analytic_isolated_ideal_thrust_N=ideal,
            simulated_mean_vertical_lift_N=row['mean_lift_N'],
            simulated_minus_analytic_percent=100*(row['mean_lift_N']/ideal-1),
            simulated_window_s=[row['start_s'],row['stop_s']]))
    result = dict(kind='Analytic estimate compared with completed CFD; internal consistency only',
        formula='T_ideal=(P_axial*sqrt(2*rho*A_sum))^(2/3)',rho_kg_m3=1.225,
        assumptions='Isolated, flat, ideal hovering disks; nominal modeled axial-work budget',
        limitations='Not an independent experiment, an electrical-efficiency calibration, a Tello performance rating, or a strict bound for interacting/canted arrays.',
        theory_reference='https://rotorcraft.arc.nasa.gov/Publications/files/marshall-et-al-2024.pdf',
        comparisons=comparisons)
    (out/'ideal_disk_consistency.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()

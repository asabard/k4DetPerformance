"""
Config for CLD full-sim + reco on lxplus/HTCondor.
Mirroirs config.sh. Importé par utils.load_config().
"""
from pathlib import Path

# ============================================================
# DÉTECTEUR (override possible : DETECTOR_MODEL=CLD_o3_v01 python ...)
# ============================================================
import os
DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "CLD_o2_v07")

# ============================================================
# CHEMINS DE BASE (AFS + EOS)
# ============================================================
AFS_HOME = Path("/afs/cern.ch/user/a/asabard/private/FCC_PhD")
EOS_BASE = Path("/eos/user/a/asabard/DigiPerformance")

CLDCONFIG_DIR = AFS_HOME / "CLDConfig" / "CLDConfig"
CONDOR_ROOT   = AFS_HOME / "k4DetPerformance" / "TrackingPerformance" / "Condor"

# Script sourcé au début de chaque job worker
setup = CONDOR_ROOT / "setup_fcc.sh"

# ============================================================
# STEERING FILES
# ============================================================
sim_steering_file  = CLDCONFIG_DIR / "cld_steer.py"
reco_steering_file = CLDCONFIG_DIR / "CLDReconstruction.py"

# compact files relatifs à $k4geo_DIR (résolu sur le worker)
detector_dir = Path("$k4geo_DIR")
det_mod_paths = {
    "CLD_o2_v07": Path("FCCee/CLD/compact/CLD_o2_v07/CLD_o2_v07.xml"),
    "CLD_o2_v05": Path("FCCee/CLD/compact/CLD_o2_v05/CLD_o2_v05.xml"),
    "CLD_o3_v01": Path("FCCee/CLD/compact/CLD_o3_v01/CLD_o3_v01.xml"),
}

# ============================================================
# SCANS (miroir de config.sh)
# ============================================================
##detector_model_list = [DETECTOR_MODEL]
detector_model_list = ["CLD_o2_v07"]
particle_list       = ["pi-", "e-"]                             # utilisé tel quel dans --gun.particle
momentum_list       = [1, 10, 30, 100]                              # GeV
theta_list          = ["global", 10, 20, 30, 40, 50, 60, 70, 80, 90]

# ============================================================
# ÉVÉNEMENTS & SPLIT
# ============================================================
N_EVTS         = 10000    # total par (particle, énergie, theta)
N_EVTS_PER_JOB = 1000     # => 4 jobs condor par combinaison

# ============================================================
# GUN
# ============================================================
THETA_MODE = "smeared"   # "fixed" ou "smeared" (±1°)
SEED       = "0123456789"

# ============================================================
# RECO
# ============================================================
RECO_MODE = "detailed"   # "detailed" ou "parametric"
RES_UM    = "3um"        # utilisé uniquement en mode parametric

# ============================================================
# SORTIES
# ============================================================
data_dir         = EOS_BASE / DETECTOR_MODEL
sim_condor_dir   = CONDOR_ROOT / "sim_jobs"
reco_condor_dir  = CONDOR_ROOT / "reco_jobs"

# ============================================================
# HTCONDOR
# ============================================================
# espresso(20min) / microcentury(1h) / longlunch(2h) / workday(8h) /
# tomorrow(1d) / testmatch(3d) / nextweek(1w)
JOB_FLAVOR = "workday"

# naming convention utilisé dans tes scripts bash actuels
EDM4HEP_SUFFIX_WITH_UNDERSCORE = True

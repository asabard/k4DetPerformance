"""
Config TEST : CLD_o2_v07, 10000 mu- @ 30 GeV, scan complet en theta.

Usage :
    python condorJobs_sim.py  --config config_mu30
    python condorJobs_reco.py --config config_mu30
"""
from pathlib import Path

# ============================================================
# DÉTECTEUR
# ============================================================
DETECTOR_MODEL = "CLD_o2_v07"

# ============================================================
# CHEMINS (identiques à config_cld.py)
# ============================================================
AFS_HOME = Path("/afs/cern.ch/user/a/asabard/private/FCC_PhD")
EOS_BASE = Path("/eos/user/a/asabard/DigiPerformance")

CLDCONFIG_DIR = AFS_HOME / "CLDConfig" / "CLDConfig"
CONDOR_ROOT   = AFS_HOME / "k4DetPerformance" / "TrackingPerformance" / "Condor"

setup = CONDOR_ROOT / "setup_fcc.sh"
sim_steering_file  = CLDCONFIG_DIR / "cld_steer.py"
reco_steering_file = CLDCONFIG_DIR / "CLDReconstruction.py"

detector_dir = Path("$k4geo_DIR")
det_mod_paths = {
    "CLD_o2_v07": Path("FCCee/CLD/compact/CLD_o2_v07/CLD_o2_v07.xml"),
}

# ============================================================
# SCAN — LE COEUR DE LA CONFIG DE TEST
# ============================================================
detector_model_list = ["CLD_o2_v07"]
particle_list       = ["mu-"]                                       # muons
momentum_list       = [30]                                          # 30 GeV
theta_list          = ["global", 10, 20, 30, 40, 50, 60, 70, 80, 90]

# 10 000 events par (particle, énergie, theta) = 10k events × 10 thetas = 100k total
N_EVTS         = 10000
N_EVTS_PER_JOB = 1000        # -> 10 jobs par theta, 100 jobs au total

# ============================================================
# GUN
# ============================================================
THETA_MODE = "smeared"       # θ±1° autour de la valeur centrale
SEED       = "0123456789"

# ============================================================
# RECO
# ============================================================
RECO_MODE = "detailed"
RES_UM    = "3um"

# ============================================================
# SORTIES
# ============================================================
data_dir        = EOS_BASE / DETECTOR_MODEL
sim_condor_dir  = CONDOR_ROOT / "sim_jobs_mu30"     # sous-dossier dédié au test
reco_condor_dir = CONDOR_ROOT / "reco_jobs_mu30"

# ============================================================
# HTCONDOR
# ============================================================
JOB_FLAVOR = "longlunch"     # 2h — largement suffisant pour 1000 mu-@30GeV
EDM4HEP_SUFFIX_WITH_UNDERSCORE = True

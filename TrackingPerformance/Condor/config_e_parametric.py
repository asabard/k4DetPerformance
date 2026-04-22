"""
Scan mu- sur CLD_o2_v07 perso — RECO PARAMETRIC (smearing 3um).

Même SIM que config_mu_detailed, juste un autre mode de reco.

Pour lancer (sim déjà produite) :
    python condorJobs_reco.py --config config_e_parametric
"""
from pathlib import Path
import os

_TAG = Path(__file__).stem

DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "CLD_o2_v07")
OUTPUT_TAG     = "perso"

AFS_HOME = Path("/afs/cern.ch/user/a/asabard/public/FCC_PHD_Condor")
EOS_BASE = Path("/eos/user/a/asabard/DigiPerformance")

CLDCONFIG_DIR = AFS_HOME / "CLDConfig" / "CLDConfig"
CONDOR_ROOT   = AFS_HOME / "k4DetPerformance" / "TrackingPerformance" / "Condor"

setup               = CONDOR_ROOT / "setup_fcc.sh"
sim_steering_file   = CLDCONFIG_DIR / "cld_steer.py"
reco_steering_file  = CLDCONFIG_DIR / "CLDReconstruction.py"

detector_dir = Path("$k4geo_DIR")
det_mod_paths = {
    "CLD_o2_v07": Path("FCCee/CLD/compact/CLD_o2_v07/CLD_o2_v07.xml"),
    "CLD_o2_v05": Path("FCCee/CLD/compact/CLD_o2_v05/CLD_o2_v05.xml"),
    "CLD_o3_v01": Path("FCCee/CLD/compact/CLD_o3_v01/CLD_o3_v01.xml"),
}

detector_model_list = [DETECTOR_MODEL]
particle_list       = ["e-"]
momentum_list       = [1, 2, 5, 10, 20, 50, 100]
theta_list          = [10, 20, 30, 40, 50, 60, 70, 80, 90]

N_EVTS         = 10000
N_EVTS_PER_JOB = 1000

THETA_MODE = "smeared"
SEED       = "0123456789"

# ============================================================
# RECO MODE — parametric smearing
# ============================================================
RECO_MODE = "parametric"
RES_UM    = "3um"     # resolution du smearing u,v -> 3 microns

# SIM partagée avec le mode detailed
SIM_SOURCE_TAG = "config_e"
data_dir        = EOS_BASE / f"{DETECTOR_MODEL}_{OUTPUT_TAG}"
sim_condor_dir  = CONDOR_ROOT / "sim_jobs"  / f"{SIM_SOURCE_TAG}_{OUTPUT_TAG}"
reco_condor_dir = CONDOR_ROOT / "reco_jobs" / f"{_TAG}_{OUTPUT_TAG}"

JOB_FLAVOR = "longlunch"   # parametric est plus rapide que detailed

EDM4HEP_SUFFIX_WITH_UNDERSCORE = True

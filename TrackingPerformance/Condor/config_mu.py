"""
Scan mu- sur CLD_o2_v07 — TA GÉOMÉTRIE PERSO (avec ton digitizer).
Grille : 7 énergies × 9 thetas × 10 subjobs = 630 jobs.

Outputs dans CLD_o2_v07_perso/ pour distinguer des runs CVMFS.

Pour lancer :
    python condorJobs_sim.py --config config_mu
"""
from pathlib import Path
import os

_TAG = Path(__file__).stem   # "config_mu"

# ============================================================
# DÉTECTEUR
# ============================================================
DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "CLD_o2_v07")
OUTPUT_TAG     = "perso"   # <-- TA géom

# ============================================================
# CHEMINS — tout dans public (accessible par les workers condor)
# ============================================================
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

# ============================================================
# SCAN — MUONS
# ============================================================
detector_model_list = [DETECTOR_MODEL]
particle_list       = ["mu-"]
momentum_list       = [1, 2, 5, 10, 20, 50, 100]
theta_list          = [10, 20, 30, 40, 50, 60, 70, 80, 90]

N_EVTS         = 10000
N_EVTS_PER_JOB = 1000

# ============================================================
# GUN
# ============================================================
THETA_MODE = "smeared"
SEED       = "0123456789"

# ============================================================
# RECO
# ============================================================
RECO_MODE = "detailed"
RES_UM    = "3um"

# ============================================================
# SORTIES
# ============================================================
data_dir        = EOS_BASE / f"{DETECTOR_MODEL}_{OUTPUT_TAG}"
sim_condor_dir  = CONDOR_ROOT / "sim_jobs"  / f"{_TAG}_{OUTPUT_TAG}"
reco_condor_dir = CONDOR_ROOT / "reco_jobs" / f"{_TAG}_{OUTPUT_TAG}"

# ============================================================
# HTCONDOR
# ============================================================
JOB_FLAVOR = "longlunch"

EDM4HEP_SUFFIX_WITH_UNDERSCORE = True

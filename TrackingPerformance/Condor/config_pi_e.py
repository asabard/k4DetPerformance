"""
Scan complet pi- + e- (+ optionnellement mu-) sur CLD_o2_v07.

Pour lancer :
    python condorJobs_sim.py --config config_pi_e

Le nom du fichier de config est utilisé automatiquement comme tag des
répertoires de soumission (sim_jobs/<tag>, reco_jobs/<tag>).
"""
from pathlib import Path
import os

# ============================================================
# TAG AUTOMATIQUE (évite les collisions entre scans)
# ============================================================
_TAG = Path(__file__).stem   # ex: "config_pi_e"

# ============================================================
# DÉTECTEUR
# ============================================================
DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "CLD_o2_v07")

# ============================================================
# CHEMINS DE BASE
# ============================================================
AFS_HOME = Path("/afs/cern.ch/user/a/asabard/private/FCC_PhD")
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
# SCANS
# ============================================================
detector_model_list = [DETECTOR_MODEL]

# Enlève/ajoute "mu-" selon que tu veuilles compléter le trio ou non
particle_list = ["pi-", "e-"]
# particle_list = ["mu-", "pi-", "e-"]   # trio complet (1200 jobs)

momentum_list = [1, 10, 30, 100]
theta_list    = ["global", 10, 20, 30, 40, 50, 60, 70, 80, 90]

# ============================================================
# ÉVÉNEMENTS & SPLIT
# ============================================================
N_EVTS         = 10000   # par (particule, énergie, θ)
N_EVTS_PER_JOB = 1000    # => 10 sub-jobs par combinaison

# Volume total : len(particle) × len(E) × len(θ) × 10
# pi-/e-    : 2 × 4 × 10 × 10 =  800 jobs
# +mu-      : 3 × 4 × 10 × 10 = 1200 jobs

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
# SORTIES — taggées par nom de config pour éviter les collisions
# ============================================================
data_dir        = EOS_BASE / DETECTOR_MODEL             # partagé entre configs (OK)
sim_condor_dir  = CONDOR_ROOT / "sim_jobs"  / _TAG      # isolé par config
reco_condor_dir = CONDOR_ROOT / "reco_jobs" / _TAG

# ============================================================
# HTCONDOR
# ============================================================
# pi-/e- à 100 GeV en full sim peut être lourd → workday (8h) prudent.
# Si tu vois des jobs à 6-7h dans les logs, passe à "tomorrow".
JOB_FLAVOR = "workday"

EDM4HEP_SUFFIX_WITH_UNDERSCORE = True

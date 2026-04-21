#!/usr/bin/env python
"""
Soumission de la reconstruction sur HTCondor — version alignée sur
ton step2a_reco_detailed.sh local.

Reproduit précisément ce que fait ton script bash :
  1. Workdir dédié au job (scratch condor de préférence).
  2. PYTHONPATH inclut CLDCONFIG (pour `py_utils`).
  3. Symlinks vers les sous-modules Gaudi (Tracking, Overlay, ...) + fichiers.
  4. k4run avec --detailedDigitization --trackingOnly --compactFile --num-events -1
     (ou la variante parametric).
  5. xrdcp de tous les fichiers *_REC.edm4hep.root vers EOS.

Usage :
    python condorJobs_reco.py --config config_mu30
"""

import itertools
import re
import sys
from os import fspath, system
from pathlib import Path

import ROOT
from utils import load_config, parse_args


# Sous-modules et fichiers que CLDReconstruction.py attend dans son cwd,
# identique à ce que ton step2a_reco_detailed.sh symlinke en local.
CLDCONFIG_LINKS = [
    "Tracking",
    "Overlay",
    "Diagnostics",
    "CaloDigi",
    "ParticleFlow",
    "HighLevelReco",
    "py_utils.py",
    "collections_rec_level.txt",
]


def build_sim_dir(config, part: str, energy: int) -> Path:
    if config.THETA_MODE == "smeared":
        sub = Path(part) / "ThetaNotFixed" / f"{energy}GeV"
    else:
        sub = Path(part) / f"{energy}GeV"
    return config.data_dir / "SIM" / sub / f"{config.N_EVTS}evts"


def build_reco_dir(config, part: str, energy: int) -> Path:
    if config.THETA_MODE == "smeared":
        sub = Path(part) / "ThetaNotFixed" / f"{energy}GeV"
    else:
        sub = Path(part) / f"{energy}GeV"
    if config.RECO_MODE == "parametric":
        return (config.data_dir / "REC_parametric" / sub
                / config.RES_UM / f"{config.N_EVTS}evts")
    return config.data_dir / "REC_detailed" / sub / f"{config.N_EVTS}evts"


def list_sim_files(sim_dir: Path, part: str, energy: int, theta,
                   n_per_job: int) -> list[Path]:
    patt = re.compile(
        rf"^SIM_{re.escape(part)}_{energy}GeV_theta{theta}_"
        rf"{n_per_job}evts_job\d+_edm4hep\.root$"
    )
    if not sim_dir.exists():
        return []
    return sorted(p for p in sim_dir.iterdir() if patt.match(p.name))


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    assert config.reco_steering_file.exists(), \
        f"Steering introuvable : {config.reco_steering_file}"
    assert config.RECO_MODE in ("detailed", "parametric")

    cldconfig_dir = config.CLDCONFIG_DIR

    directory_jobs = (
        config.reco_condor_dir
        / f"{config.detector_model_list[0]}_{config.RECO_MODE}"
    )
    try:
        directory_jobs.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"[ERROR] '{directory_jobs}' existe déjà.")
        print("        Supprime-le avant de resoumettre :")
        print(f"        rm -rf {directory_jobs}")
        sys.exit(1)
    (directory_jobs / "log").mkdir(exist_ok=True)

    NEED_SCRIPTS = False

    combos = itertools.product(
        config.theta_list,
        config.momentum_list,
        config.particle_list,
        config.detector_model_list,
    )

    # Flags k4run selon le mode, calqués sur step2a_reco_detailed.sh
    if config.RECO_MODE == "detailed":
        mode_flags = ["--detailedDigitization"]
    else:
        # Si tu as une variante parametric, ajoute les flags ici, par ex. :
        # mode_flags = ["--VXDTrackerHitDigitiser.resU", config.PARAM_RES_UV,
        #               "--VXDTrackerHitDigitiser.resV", config.PARAM_RES_UV]
        mode_flags = []

    for theta, energy, part, dect in combos:
        sim_dir  = build_sim_dir(config, part, energy)
        reco_dir = build_reco_dir(config, part, energy)
        reco_dir.mkdir(parents=True, exist_ok=True)

        sim_files = list_sim_files(sim_dir, part, energy, theta,
                                    config.N_EVTS_PER_JOB)
        if not sim_files:
            print(f"[WARN] aucun SIM dans {sim_dir} pour θ={theta} — skip")
            continue

        compact = Path("$k4geo_DIR") / config.det_mod_paths[dect]

        for sim_path in sim_files:
            # basename : SIM_..._job0 -> REC_detailed_..._job0
            job_tag  = sim_path.stem.replace("_edm4hep", "")
            basename = f"REC_{config.RECO_MODE}_{job_tag.removeprefix('SIM_')}"
            main_out = f"{basename}_REC.edm4hep.root"   # produit par k4run
            out_path = reco_dir / main_out

            # Skip si output déjà valide
            if out_path.exists():
                try:
                    f_ = ROOT.TFile(fspath(out_path), "READ")
                    tree = f_.Get("events")
                    if tree and tree.GetEntries() == config.N_EVTS_PER_JOB:
                        f_.Close()
                        continue
                    f_.Close()
                except Exception:
                    pass
            NEED_SCRIPTS = True

            # Commandes de symlinks reproduites depuis step2a_reco_detailed.sh
            link_cmds = "\n".join(
                f'ln -sfn "{cldconfig_dir}/{x}" .' for x in CLDCONFIG_LINKS
            )

            in_url = f"root://eosuser.cern.ch/{sim_path}"

            k4run_flags = [
                f"--inputFiles {in_url}",
                f"--outputBasename {basename}",
                f"--compactFile {compact}",
                *mode_flags,
                "--trackingOnly",
                "--num-events -1",
            ]
            k4run_cmd = f"k4run {config.reco_steering_file} \\\n    " + " \\\n    ".join(k4run_flags)

            bash = f"""#!/bin/bash
set -e
source {config.setup}

# --- Workdir dédié au job -----------------------------------
# Scratch condor si dispo (auto-nettoyé en fin de job),
# sinon /tmp avec PID pour l'isolation.
WORKDIR="${{_CONDOR_SCRATCH_DIR:-/tmp/${{USER}}_reco_$$}}"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# --- Symlinks attendus par CLDReconstruction.py --------------
{link_cmds}

# --- Reco ----------------------------------------------------
{k4run_cmd}

# --- Upload des outputs sur EOS ------------------------------
shopt -s nullglob
for f in {basename}*.root; do
    echo "[upload] $f"
    xrdcp -f "$f" "root://eosuser.cern.ch/{reco_dir}/"
done

# Nettoyage explicite (condor scratch est auto-nettoyé mais au cas où)
rm -f {basename}*.root
"""
            job_k = job_tag.split("_job")[-1]
            bash_name = (
                f"reco_{config.RECO_MODE}_{dect}_{part}_{energy}GeV_"
                f"theta{theta}_job{job_k}.sh"
            )
            bash_path = directory_jobs / bash_name
            bash_path.write_text(bash)
            bash_path.chmod(0o755)

    if not NEED_SCRIPTS:
        print("[INFO] Toutes les sorties reco existent déjà.")
        sys.exit(0)

    condor_sub = (
        "executable = $(filename)\n"
        "arguments  = $(ClusterId) $(ProcId)\n"
        "output     = log/output.$(ClusterId).$(ProcId).out\n"
        "error      = log/error.$(ClusterId).$(ProcId).err\n"
        "log        = log/log.$(ClusterId).log\n"
        f'+JobFlavour = "{config.JOB_FLAVOR}"\n'
        "queue filename matching files reco_*.sh\n"
    )
    (directory_jobs / "condor_script.sub").write_text(condor_sub)

    print(f"[INFO] Soumission depuis {directory_jobs}")
    system(f"cd {fspath(directory_jobs)}; condor_submit condor_script.sub")


if __name__ == "__main__":
    main()
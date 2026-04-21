#!/usr/bin/env python
"""
Soumission des jobs de SIMULATION sur HTCondor (lxplus).

Adapté de ton step1_simu.sh pour coller au framework utils.load_config :
  - θ = "global"      -> thetaMin=10°, thetaMax=170°
  - THETA_MODE=smeared-> thetaMin=θ-1°, thetaMax=θ+1°
  - Seed, naming SIM_<part>_<E>GeV_theta<θ>_<N>evts_jobK_edm4hep.root
  - Split de N_EVTS en N_EVTS_PER_JOB par combinaison (particle, énergie, θ)
  - Output sur EOS suivant l'arborescence SIM/<part>/[ThetaNotFixed/]<E>GeV/<N>evts

Usage :
    python condorJobs_sim.py --config config_cld
"""

import itertools
import sys
from math import ceil
from os import fspath, system
from pathlib import Path

import ROOT
from utils import load_config, parse_args


def build_sim_output_dir(config, particle: str, energy: int) -> Path:
    """Arborescence EOS de sortie, identique à config.sh::set_kinematics."""
    if config.THETA_MODE == "smeared":
        sub = Path(particle) / "ThetaNotFixed" / f"{energy}GeV"
    else:
        sub = Path(particle) / f"{energy}GeV"
    return config.data_dir / "SIM" / sub / f"{config.N_EVTS}evts"


def build_theta_range(theta, mode: str) -> tuple[str, str]:
    """Retourne (thetaMin, thetaMax) en reproduisant la logique du bash."""
    if theta == "global":
        return "10*deg", "170*deg"
    if mode == "smeared":
        return f"{int(theta) - 1}*deg", f"{int(theta) + 1}*deg"
    return f"{theta}*deg", f"{theta}*deg"


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    # --- Sanity checks -----------------------------------------------------
    assert config.sim_steering_file.exists(), \
        f"Steering file introuvable : {config.sim_steering_file}"
    assert config.setup.exists(), \
        f"Setup script introuvable : {config.setup}"
    assert isinstance(config.N_EVTS, int)
    assert isinstance(config.N_EVTS_PER_JOB, int)

    n_jobs_per_set = ceil(config.N_EVTS / config.N_EVTS_PER_JOB)
    n_sets = (
        len(config.detector_model_list)
        * len(config.particle_list)
        * len(config.theta_list)
        * len(config.momentum_list)
    )
    print(f"[INFO] {n_sets} combinaisons × {n_jobs_per_set} jobs "
          f"= {n_sets * n_jobs_per_set} jobs condor à préparer")

    # --- Répertoire de soumission (un par détecteur) -----------------------
    directory_jobs = config.sim_condor_dir / config.detector_model_list[0]
    try:
        directory_jobs.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"[ERROR] '{directory_jobs}' existe déjà.")
        print("        Supprime-le ou renomme-le avant de resoumettre.")
        sys.exit(1)
    (directory_jobs / "log").mkdir(exist_ok=True)

    NEED_SCRIPTS = False

    combos = itertools.product(
        config.theta_list,
        config.momentum_list,
        config.particle_list,
        config.detector_model_list,
    )

    for theta, energy, part, dect in combos:
        out_dir = build_sim_output_dir(config, part, energy)
        out_dir.mkdir(parents=True, exist_ok=True)

        t_min, t_max = build_theta_range(theta, config.THETA_MODE)
        compact = Path("$k4geo_DIR") / config.det_mod_paths[dect]

        for k in range(n_jobs_per_set):
            out_name = (
                f"SIM_{part}_{energy}GeV_theta{theta}_"
                f"{config.N_EVTS_PER_JOB}evts_job{k}_edm4hep.root"
            )
            out_path = out_dir / out_name

            # Skip si l'output existe déjà avec le bon nombre d'events
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

            # Chaque job reçoit un seed différent pour éviter les événements
            # dupliqués entre sous-jobs d'une même combinaison
            job_seed = int(config.SEED) + k

            ddsim_args = [
                f"--compactFile {compact}",
                f"--outputFile {out_name}",
                f"--steeringFile {config.sim_steering_file}",
                f"--random.seed {job_seed}",
                "--enableGun",
                f"--gun.particle {part}",
                f"--gun.energy {energy}*GeV",
                "--gun.distribution uniform",
                f"--gun.thetaMin {t_min}",
                f"--gun.thetaMax {t_max}",
                "--crossingAngleBoost 0",
                f"--numberOfEvents {config.N_EVTS_PER_JOB}",
            ]
            ddsim_cmd = "ddsim " + " ".join(ddsim_args)

            bash = (
                "#!/bin/bash\n"
                "set -e\n"
                f"source {config.setup}\n"
                "cd $TMPDIR 2>/dev/null || cd /tmp\n"
                f"{ddsim_cmd}\n"
                f"xrdcp -f {out_name} root://eosuser.cern.ch/{out_path}\n"
                f"rm -f {out_name}\n"
            )
            bash_name = (
                f"sim_{dect}_{part}_{energy}GeV_theta{theta}_job{k}.sh"
            )
            bash_path = directory_jobs / bash_name
            bash_path.write_text(bash)
            bash_path.chmod(0o755)

    if not NEED_SCRIPTS:
        print("[INFO] Toutes les sorties existent déjà — rien à soumettre.")
        sys.exit(0)

    # --- Fichier de soumission HTCondor ------------------------------------
    condor_sub = (
        "executable = $(filename)\n"
        "arguments  = $(ClusterId) $(ProcId)\n"
        "output     = log/output.$(ClusterId).$(ProcId).out\n"
        "error      = log/error.$(ClusterId).$(ProcId).err\n"
        "log        = log/log.$(ClusterId).log\n"
        f'+JobFlavour = "{config.JOB_FLAVOR}"\n'
        "queue filename matching files sim_*.sh\n"
    )
    (directory_jobs / "condor_script.sub").write_text(condor_sub)

    print(f"[INFO] Soumission depuis {directory_jobs}")
    system(f"cd {fspath(directory_jobs)}; condor_submit condor_script.sub")


if __name__ == "__main__":
    main()
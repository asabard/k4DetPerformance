#!/usr/bin/env python
"""
mergeOutputs.py — merge les sous-jobs en UN fichier par combinaison.

Usage :
    python mergeOutputs.py --config config_mu30 --stage sim
    python mergeOutputs.py --config config_mu30 --stage reco
    python mergeOutputs.py --config config_mu30 --stage both [--cleanup] [--dry-run]
"""

import argparse
import itertools
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from utils import load_config


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--stage", choices=("sim", "reco", "both"), default="both")
    p.add_argument("--cleanup", action="store_true",
                   help="Supprime les sous-jobs après merge validé")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--jobs", type=int, default=None,
                   help=f"Nb de hadd en parallèle (défaut : {os.cpu_count()})")
    return p.parse_args()


def dir_for(config, stage: str, particle: str, energy: int) -> Path:
    if config.THETA_MODE == "smeared":
        sub = Path(particle) / "ThetaNotFixed" / f"{energy}GeV"
    else:
        sub = Path(particle) / f"{energy}GeV"

    if stage == "sim":
        return config.data_dir / "SIM" / sub / f"{config.N_EVTS}evts"
    if config.RECO_MODE == "parametric":
        return (config.data_dir / "REC_parametric" / sub
                / config.RES_UM / f"{config.N_EVTS}evts")
    return config.data_dir / "REC_detailed" / sub / f"{config.N_EVTS}evts"


def names_for(config, stage: str, particle: str, energy: int, theta):
    """Retourne (glob d'entrée, nom de sortie mergé)."""
    if stage == "sim":
        in_pat = (f"SIM_{particle}_{energy}GeV_theta{theta}_"
                  f"{config.N_EVTS_PER_JOB}evts_job*_edm4hep.root")
        out = (f"SIM_{particle}_{energy}GeV_theta{theta}_"
               f"{config.N_EVTS}evts_edm4hep.root")
    else:
        # k4run produit <basename>_REC.edm4hep.root
        in_pat = (f"REC_{config.RECO_MODE}_{particle}_{energy}GeV_theta{theta}_"
                  f"{config.N_EVTS_PER_JOB}evts_job*_REC.edm4hep.root")
        out = (f"REC_{config.RECO_MODE}_{particle}_{energy}GeV_theta{theta}_"
               f"{config.N_EVTS}evts_REC.edm4hep.root")
    return in_pat, out


def merge_one(config, stage, theta, energy, particle,
              cleanup: bool, dry_run: bool) -> str:
    d = dir_for(config, stage, particle, energy)
    in_pat, out_name = names_for(config, stage, particle, energy, theta)
    subjobs = sorted(d.glob(in_pat))
    tag = f"{stage:4s} θ={str(theta):>6} | {particle}@{energy}GeV"

    if not subjobs:
        return f"[MISS]  {tag}"

    out_path = d / out_name
    if out_path.exists():
        return f"[OK]    {tag} — déjà mergé"

    if dry_run:
        return f"[DRY]   {tag} ← {len(subjobs)} sous-jobs → {out_name}"

    try:
        subprocess.run(
            ["hadd", "-f", str(out_path), *map(str, subjobs)],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        return f"[ERR]   {tag}\n         {e.stderr.strip()}"

    if not out_path.exists() or out_path.stat().st_size < 1024:
        return f"[ERR]   {tag} — output suspect (<1kB)"

    if cleanup:
        for f in subjobs:
            f.unlink()
        return f"[MERGE] {tag} — {len(subjobs)} sous-jobs mergés + supprimés"
    return f"[MERGE] {tag} — {len(subjobs)} sous-jobs mergés"


def main():
    args = parse_args()
    config = load_config(args.config)

    if shutil.which("hadd") is None:
        sys.exit("[ERROR] `hadd` introuvable — as-tu sourcé la stack key4hep ?")

    stages = ("sim", "reco") if args.stage == "both" else (args.stage,)

    tasks = [
        (stage, theta, energy, particle)
        for stage in stages
        for theta, energy, particle, _dect in itertools.product(
            config.theta_list,
            config.momentum_list,
            config.particle_list,
            config.detector_model_list,
        )
    ]

    print(f"[INFO] {len(tasks)} combinaisons à traiter "
          f"(stages={list(stages)}, jobs={args.jobs or os.cpu_count()})")

    counts = {"MERGE": 0, "OK": 0, "MISS": 0, "ERR": 0, "DRY": 0}
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures = [
            ex.submit(merge_one, config, *t, args.cleanup, args.dry_run)
            for t in tasks
        ]
        for fut in as_completed(futures):
            msg = fut.result()
            print(msg)
            for k in counts:
                if msg.lstrip().startswith(f"[{k}]"):
                    counts[k] += 1
                    break

    print(f"\n[SUMMARY] merged={counts['MERGE']}  "
          f"already={counts['OK']}  missing={counts['MISS']}  "
          f"errors={counts['ERR']}  dry={counts['DRY']}")


if __name__ == "__main__":
    main()
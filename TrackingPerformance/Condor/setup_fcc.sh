#!/bin/bash
# ============================================================
# setup_fcc.sh — pour condor worker
#
# Source les scripts setup_k4geo.sh / setup_k4Rec.sh qui utilisent
# $PWD pour construire les chemins. On fait donc pushd/popd
# pour que $PWD vaille USER_BASE au moment du source.
# ============================================================

set --

USER_BASE="/afs/cern.ch/user/a/asabard/public/FCC_PHD_Condor"

# ============================================================
# LAYER 1 — Key4hep stack
# ============================================================
FCC_STACK="${FCC_STACK:-stable}"

if [ "${FCC_STACK}" = "nightly" ]; then
    K4H_SETUP="/cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh"
else
    K4H_SETUP="/cvmfs/sw.hsf.org/key4hep/setup.sh"
fi

if [ -n "${FCC_STACK_RELEASE}" ]; then
    source "${K4H_SETUP}" -r "${FCC_STACK_RELEASE}"
else
    source "${K4H_SETUP}"
fi

# ============================================================
# LAYER 2 & 3 — k4geo + k4RecTracker persos
# ============================================================
# IMPORTANT : setup_k4geo.sh et setup_k4Rec.sh utilisent $PWD.
# On se place temporairement dans USER_BASE pour que $PWD soit correct.
_CALLER_PWD="$(pwd)"
cd "${USER_BASE}" || { echo "[ERROR] cd ${USER_BASE} failed" >&2; return 1 2>/dev/null || exit 1; }

if [ ! -f "${USER_BASE}/setup_k4geo.sh" ]; then
    echo "[ERROR] setup_k4geo.sh introuvable : ${USER_BASE}/setup_k4geo.sh" >&2
    cd "${_CALLER_PWD}"
    return 1 2>/dev/null || exit 1
fi
source "${USER_BASE}/setup_k4geo.sh"

if [ -f "${USER_BASE}/setup_k4Rec.sh" ]; then
    source "${USER_BASE}/setup_k4Rec.sh"
fi

cd "${_CALLER_PWD}"

# ============================================================
# Vérif stricte : K4GEO doit pointer vers le perso
# ============================================================
if [ "${K4GEO}" != "${USER_BASE}/k4geo" ]; then
    echo "[ERROR] K4GEO=${K4GEO} ne pointe PAS vers ${USER_BASE}/k4geo !" >&2
    return 1 2>/dev/null || exit 1
fi

CLD_XML="${K4GEO}/FCCee/CLD/compact/CLD_o2_v07/CLD_o2_v07.xml"
if [ ! -f "${CLD_XML}" ]; then
    echo "[ERROR] CLD XML introuvable : ${CLD_XML}" >&2
    return 1 2>/dev/null || exit 1
fi

# ============================================================
# LAYER 4 — CLDConfig
# ============================================================
export CLDCONFIG="${USER_BASE}/CLDConfig/CLDConfig"
export PYTHONPATH="${CLDCONFIG}:${PYTHONPATH}"

# ============================================================
# Récap
# ============================================================
echo "[setup] hostname     : $(hostname)"
echo "[setup] FCC_STACK    : ${FCC_STACK}${FCC_STACK_RELEASE:+ @ ${FCC_STACK_RELEASE}}"
echo "[setup] k4geo_DIR    : ${k4geo_DIR}"
echo "[setup] K4GEO        : ${K4GEO}"
echo "[setup] K4RECTRACKER : ${K4RECTRACKER:-not set}"
echo "[setup] CLDCONFIG    : ${CLDCONFIG}"
echo "[setup] CLD XML      : OK ($(stat -c %y ${CLD_XML} | cut -d. -f1))"
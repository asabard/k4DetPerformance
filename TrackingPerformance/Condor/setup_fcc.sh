#!/bin/bash
# ============================================================
# setup_fcc.sh — sourcé au début de chaque job condor (worker node)
#                ET utilisable interactivement sur lxplus.
#
# ⚠️ PAS de `set -e` : ce script est sourcé, donc set -e affecterait
#    le shell parent. On utilise `return 1` partout pour signaler
#    une erreur sans tuer le terminal.
#    Les scripts bash des jobs condor ont `set -e` eux-mêmes, donc
#    un `return 1` sourcé fera échouer le job proprement.
# ============================================================

# Clear condor positional args ($1=ClusterId $2=ProcId) avant de sourcer
# les setup.sh qui en râleraient ("Unknown argument ...").
set --

USER_BASE="/afs/cern.ch/user/a/asabard/private/FCC_PhD"

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
# LAYER 2 — Overlays perso
# ============================================================

# --- k4geo perso (OBLIGATOIRE) -----------------------------
K4GEO_DIR="${USER_BASE}/k4geo"
K4GEO_SETUP="${K4GEO_DIR}/install/bin/thisk4geo.sh"

if [ ! -f "${K4GEO_SETUP}" ]; then
    echo "[ERROR] k4geo perso introuvable : ${K4GEO_SETUP}" >&2
    echo "[ERROR] Pour rebuild, source d'abord le stack brut :" >&2
    echo "[ERROR]   source /cvmfs/sw.hsf.org/key4hep/setup.sh" >&2
    echo "[ERROR]   cd ${K4GEO_DIR} && rm -rf build install" >&2
    echo "[ERROR]   mkdir -p build && cd build" >&2
    echo "[ERROR]   cmake .. -DCMAKE_INSTALL_PREFIX=../install" >&2
    echo "[ERROR]   make -j\$(nproc) install" >&2
    return 1 2>/dev/null || exit 1
fi

source "${K4GEO_SETUP}"
export DD4HEP_LIBRARY_PATH="${K4GEO_DIR}/install/lib/:${DD4HEP_LIBRARY_PATH}"
export CMAKE_PREFIX_PATH="${K4GEO_DIR}/install/:${CMAKE_PREFIX_PATH}"
export LCGEO="${K4GEO_DIR}"
export lcgeo_DIR="${K4GEO_DIR}"
export K4GEO="${K4GEO_DIR}"
export k4geo_DIR="${K4GEO_DIR}"

# Vérif post-source : on DOIT pointer vers le perso, pas CVMFS.
case "${k4geo_DIR}" in
    ${USER_BASE}/*) : ;;    # OK, sous /afs/.../private/FCC_PhD/
    *)
        echo "[ERROR] k4geo_DIR=${k4geo_DIR} ne pointe PAS vers le perso !" >&2
        return 1 2>/dev/null || exit 1
        ;;
esac

# Vérif ABI : libk4geo.so chargeable avec le stack sourcé ?
K4GEO_LIB="${K4GEO_DIR}/install/lib/libk4geo.so"
if [ -f "${K4GEO_LIB}" ]; then
    _abi_miss=$(ldd "${K4GEO_LIB}" 2>/dev/null | grep "not found")
    if [ -n "${_abi_miss}" ]; then
        echo "[ERROR] ABI mismatch sur libk4geo.so :" >&2
        echo "${_abi_miss}" >&2
        echo "[ERROR] Ton k4geo a été compilé contre une autre stack." >&2
        echo "[ERROR] Rebuild avec la stack actuelle (source setup_fcc.sh puis recompile)." >&2
        return 1 2>/dev/null || exit 1
    fi
fi

# --- FCCDetectors (optionnel) -------------------------------
FCCD_DIR="${USER_BASE}/FCCDetectors"
if [ -d "${FCCD_DIR}/install" ]; then
    export FCCDETECTORS="${FCCD_DIR}/"
    export PATH="${FCCD_DIR}/install/bin/:${PATH}"
    export CMAKE_PREFIX_PATH="${FCCD_DIR}/install/:${CMAKE_PREFIX_PATH}"
    export LD_LIBRARY_PATH="${FCCD_DIR}/install/lib:${FCCD_DIR}/install/lib64:${LD_LIBRARY_PATH}"
    export PYTHONPATH="${FCCD_DIR}/install/python:${PYTHONPATH}"
fi

# --- k4RecTracker (optionnel) -------------------------------
K4RT_DIR="${USER_BASE}/k4RecTracker"
if [ -d "${K4RT_DIR}/install" ]; then
    export K4RECTRACKER="${K4RT_DIR}/install/share/k4RecTracker"
    export PATH="${K4RT_DIR}/install/bin/:${PATH}"
    export CMAKE_PREFIX_PATH="${K4RT_DIR}/install/:${CMAKE_PREFIX_PATH}"
    export LD_LIBRARY_PATH="${K4RT_DIR}/install/lib:${K4RT_DIR}/install/lib64:${LD_LIBRARY_PATH}"
    export PYTHONPATH="${K4RT_DIR}/install/python:${PYTHONPATH}"
fi

# ============================================================
# LAYER 3 — CLDConfig (pour CLDReconstruction.py + py_utils)
# ============================================================
export CLDCONFIG="${USER_BASE}/CLDConfig/CLDConfig"
export PYTHONPATH="${CLDCONFIG}:${PYTHONPATH}"

# ============================================================
# Récap visible dans les .out condor
# ============================================================
echo "[setup] hostname     : $(hostname)"
echo "[setup] FCC_STACK    : ${FCC_STACK}${FCC_STACK_RELEASE:+ @ ${FCC_STACK_RELEASE}}"
echo "[setup] k4geo_DIR    : ${k4geo_DIR}"
echo "[setup] K4GEO        : ${K4GEO}"
echo "[setup] FCCDETECTORS : ${FCCDETECTORS:-not set}"
echo "[setup] K4RECTRACKER : ${K4RECTRACKER:-not set}"
echo "[setup] CLDCONFIG    : ${CLDCONFIG}"

# Sanity check CLD XML existe bien dans ton k4geo perso
CLD_XML="${k4geo_DIR}/FCCee/CLD/compact/CLD_o2_v07/CLD_o2_v07.xml"
if [ -f "${CLD_XML}" ]; then
    echo "[setup] CLD XML      : OK ($(stat -c %y ${CLD_XML} | cut -d. -f1))"
else
    echo "[ERROR] CLD XML introuvable : ${CLD_XML}" >&2
    return 1 2>/dev/null || exit 1
fi
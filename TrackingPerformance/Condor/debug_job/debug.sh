#!/bin/bash
echo "=== DEBUG JOB ==="
echo "hostname: $(hostname)"
echo "user: $(whoami)"
echo "scratch: $_CONDOR_SCRATCH_DIR"
echo "pwd: $(pwd)"
echo ""
echo "--- tokens ---"
tokens 2>&1
echo ""
echo "--- klist ---"
klist 2>&1
echo ""
echo "--- ls AFS public racine ---"
ls -la /afs/cern.ch/user/a/asabard/public/ 2>&1
echo ""
echo "--- ls FCC_PHD_Condor ---"
ls -la /afs/cern.ch/user/a/asabard/public/FCC_PHD_Condor/ 2>&1
echo ""
echo "--- ls k4geo/install/bin ---"
ls -la /afs/cern.ch/user/a/asabard/public/FCC_PHD_Condor/k4geo/install/bin/ 2>&1
echo ""
echo "--- cat thisk4geo.sh (test lecture) ---"
head -10 /afs/cern.ch/user/a/asabard/public/FCC_PHD_Condor/k4geo/install/bin/thisk4geo.sh 2>&1
echo ""
echo "--- test CVMFS ---"
ls /cvmfs/sw.hsf.org/key4hep/ 2>&1 | head -5
echo ""
echo "--- fin ---"
echo "=== END DEBUG ==="

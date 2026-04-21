#!/bin/bash
set -e
source /afs/cern.ch/user/a/asabard/private/FCC_PhD/k4DetPerformance/TrackingPerformance/Condor/setup_fcc.sh
cd $TMPDIR 2>/dev/null || cd /tmp
ddsim --compactFile $k4geo_DIR/FCCee/CLD/compact/CLD_o2_v07/CLD_o2_v07.xml --outputFile SIM_mu-_30GeV_theta80_1000evts_job2_edm4hep.root --steeringFile /afs/cern.ch/user/a/asabard/private/FCC_PhD/CLDConfig/CLDConfig/cld_steer.py --random.seed 123456791 --enableGun --gun.particle mu- --gun.energy 30*GeV --gun.distribution uniform --gun.thetaMin 79*deg --gun.thetaMax 81*deg --crossingAngleBoost 0 --numberOfEvents 1000
xrdcp -f SIM_mu-_30GeV_theta80_1000evts_job2_edm4hep.root root://eosuser.cern.ch//eos/user/a/asabard/DigiPerformance/CLD_o2_v07/SIM/mu-/ThetaNotFixed/30GeV/10000evts/SIM_mu-_30GeV_theta80_1000evts_job2_edm4hep.root
rm -f SIM_mu-_30GeV_theta80_1000evts_job2_edm4hep.root

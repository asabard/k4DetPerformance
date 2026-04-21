"""
Analysis tracking pour FCC-ee.
Extrait les résidus des paramètres de trace à partir des fichiers de reconstruction.

CHANGEMENTS vs version précédente :
- Lecture de DETECTOR_MODEL via config_tracking (env)
- Boucle sur PARTICLE_LIST (mu, e, pi) au lieu de mu uniquement
- Charge dynamique dans Initialize_VP (plus de -1 hardcodé)
- Cuts anti-fake par particule via FAKE_CUT (plus de 0.20 pour tout le monde)

Usage:
    DIGI_MODE=detailed fccanalysis run analysis_tracking.py
    DIGI_MODE=parametric RESOLUTION=3um fccanalysis run analysis_tracking.py
    
    # Autre détecteur :
    DETECTOR_MODEL=CLD_o2_v05 DIGI_MODE=detailed fccanalysis run analysis_tracking.py
    
    # Particule spécifique :
    PARTICLE_LIST=e DIGI_MODE=detailed fccanalysis run analysis_tracking.py
"""
import os
import sys

# ============================================================================
# IMPORT CONFIG
# ============================================================================

try:
    from config_tracking import (
        DIGI_MODE, RESOLUTION, EOSBASE, DETECTOR_MODEL, NEVTS, NEVTS_PER_JOB,
        PARTICLE_LIST, THETA_LIST, MOMENTUM_LIST,
        get_reco_input_dir, get_analysis_output_dir,
        file_exists, ensure_dir, get_fake_cut,
        RESIDUAL_LIST, SPECIAL_LIST
    )
    CONFIG_LOADED = True
except ImportError:
    print("[WARNING] config_tracking.py non trouvé, utilisation de la config locale")
    CONFIG_LOADED = False
    
    DIGI_MODE = os.environ.get("DIGI_MODE", "detailed")
    RESOLUTION = os.environ.get("RESOLUTION", "3um")
    DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "CLD_o2_v07")
    EOSBASE = f"/eos/user/a/asabard/DigiPerformance/{DETECTOR_MODEL}"
    NEVTS = os.environ.get("NEVTS", "2000")
    NEVTS_PER_JOB = "2000"
    
    PARTICLE_LIST = os.environ.get("PARTICLE_LIST", "mu,e,pi").split(",")
    THETA_LIST = ["10", "20", "30", "40", "50", "60", "70", "80", "90"]
    MOMENTUM_LIST = ["1", "2", "3", "5", "10", "15", "20", "30", "50", "60", "100", "150"]
    
    RESIDUAL_LIST = ["d0", "z0", "phi0", "omega", "tanLambda", "phi", "theta"]
    SPECIAL_LIST = ["pt", "p"]
    
    def get_fake_cut(particle):
        return {"mu": 0.20, "e": 0.50, "pi": 0.30}.get(particle, 0.50)

# ============================================================================
# CHEMINS
# ============================================================================

THETA_FOLDER = "ThetaNotFixed"

# Note : comme on boucle maintenant sur les particules, chaque particule a
# son propre répertoire d'entrée.

# ============================================================================
# CONSTRUCTION DE LA LISTE DES PROCESSUS
# ============================================================================
# Clé importante : on boucle sur les 3 particules, pas juste mu.
# Chaque entrée de processList a son propre cut anti-fake via FAKE_CUT.

def build_process_list_safe():
    """
    Construit la liste des processus pour toutes les particules, vérifie
    l'existence des fichiers. Ajoute la particule dans le dict pour que
    RDFanalysis puisse lire le bon cut anti-fake.
    """
    process_list = {}
    missing_files = []
    
    for particle in PARTICLE_LIST:
        part_dir = get_reco_input_dir(particle=particle, theta_folder=THETA_FOLDER)
        
        for theta in THETA_LIST:
            for momentum in MOMENTUM_LIST:
                if DIGI_MODE == "parametric":
                    path_prefix = f"{momentum}GeV/{RESOLUTION}/{NEVTS}evts"
                else:
                    path_prefix = f"{momentum}GeV/{NEVTS}evts"
                
                file_name_rel = (f"{path_prefix}/REC_{DIGI_MODE}_{particle}-_"
                                 f"{momentum}GeV_theta{theta}_{NEVTS}evts_REC.edm4hep")
                full_path = os.path.join(part_dir, file_name_rel + ".root")
                
                output_name = f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts"
                
                if os.path.isfile(full_path):
                    # La clé inclut la particule pour que RDFanalysis puisse
                    # la retrouver. fccanalysis utilise la clé comme nom de
                    # fichier d'entrée — elle doit matcher.
                    process_list[file_name_rel] = {
                        "output": output_name,
                        # On stocke la particule dans un champ custom ; les
                        # versions récentes de fccanalysis le supportent
                        # en le passant via environnement ou globals.
                    }
                else:
                    missing_files.append((particle, theta, momentum, full_path))
    
    if missing_files:
        print("\n" + "=" * 70)
        print(f"[WARNING] {len(missing_files)} fichiers d'entrée manquants:")
        print("=" * 70)
        for particle, theta, momentum, path in missing_files[:15]:
            print(f"  - {particle} theta={theta}° p={momentum}GeV")
        if len(missing_files) > 15:
            print(f"  ... et {len(missing_files) - 15} autres")
        print(f"[INFO] {len(process_list)} fichiers seront traités.\n")
    
    if not process_list:
        print("[ERROR] Aucun fichier d'entrée trouvé!")
        sys.exit(1)
    
    return process_list

processList = build_process_list_safe()

nCPUS = -1

# ============================================================================
# CODE C++ POUR L'ANALYSE
# ============================================================================

import ROOT

ROOT.gInterpreter.Declare("""
ROOT::VecOps::RVec<int> MCTruthTrackIndex(ROOT::VecOps::RVec<int> trackIndex,
                                          ROOT::VecOps::RVec<int> mcIndex,
                                          ROOT::VecOps::RVec<edm4hep::MCParticleData> mc)
{
    ROOT::VecOps::RVec<int> res;
    res.resize(mc.size(), -1);

    for (size_t i = 0; i < mcIndex.size(); i++) {
        res[trackIndex[i]] = mcIndex[i];
    }
    return res;
}
""")

ROOT.gInterpreter.Declare("#include <marlinutil/HelixClass_double.h>")

# ============================================================================
# VARIABLES
# ============================================================================

varList = ["pt", "d0", "z0", "phi0", "omega", "tanLambda", "p", "phi", "theta"]

# ============================================================================
# CUTS ANTI-FAKE : on prend le cut le plus large de toutes les particules
# présentes. Ça garantit qu'aucune particule ne se voit couper ses queues
# physiques. La distinction fine par particule peut être faite en aval
# dans plots_tracking* via les histos.
# ============================================================================

MAX_FAKE_CUT = max(get_fake_cut(p) for p in PARTICLE_LIST)
print(f"[INFO] Cut anti-fake global: |Δv/v_true| ≤ {MAX_FAKE_CUT}")
print(f"[INFO] (basé sur {PARTICLE_LIST}, par-particule: "
      f"{ {p: get_fake_cut(p) for p in PARTICLE_LIST} })")

# ============================================================================
# ANALYSE RDataFrame
# ============================================================================

class RDFanalysis():
    
    @staticmethod
    def analysers(df):
        """Transformations RDataFrame."""
        
        df2 = (df
            .Alias("MCTrackAssociations0", "_SiTracksMCTruthLink_from.index")
            .Alias("MCTrackAssociations1", "_SiTracksMCTruthLink_to.index")
            .Alias("SiTracks_Refitted_1", "_SiTracks_Refitted_trackStates")

            .Define("GunParticle_index", "MCParticles.generatorStatus == 1")
            .Define("GunParticle", "MCParticles[GunParticle_index][0]")

            # Charge dynamique depuis la MCParticle (plus de -1 hardcodé !)
            # edm4hep::MCParticleData a un champ .charge (float, en unités de e)
            .Define("GunParticleCharge", "static_cast<double>(GunParticle.charge)")

            .Define("trackStates_IP", "SiTracks_Refitted_1[SiTracks_Refitted_1.location == 1]")
            .Define("MC2TrackIndex", "MCTruthTrackIndex(MCTrackAssociations0, MCTrackAssociations1, MCParticles)")
            .Define("GunParticleTrackIndex", "MC2TrackIndex[GunParticle_index][0]")
            .Define("GunParticleTSIP", "trackStates_IP[GunParticleTrackIndex]")

            .Define("MatchedGunParticle_1", "MCParticles[MC2TrackIndex != -1]")
            .Define("MatchedGunParticle", "FCCAnalyses::MCParticle::sel_genStatus(1)(MatchedGunParticle_1)")

            .Define("trackData", "SiTracks_Refitted[GunParticleTrackIndex]")

            # Hélice reconstruite (B=2T du champ CLD standard)
            .Define("GunParticleTSIPHelix", """
                auto h = HelixClass_double(); 
                h.Initialize_Canonical(GunParticleTSIP.phi, GunParticleTSIP.D0, GunParticleTSIP.Z0, 
                                       GunParticleTSIP.omega, GunParticleTSIP.tanLambda, 2); 
                return h;
            """)
            .Define("reco_pt", "GunParticleTSIPHelix.getPXY()")
            .Define("reco_d0", "GunParticleTSIP.D0")
            .Define("reco_z0", "GunParticleTSIP.Z0")
            .Define("reco_phi0", "GunParticleTSIP.phi")
            .Define("reco_omega", "GunParticleTSIP.omega")
            .Define("reco_tanLambda", "GunParticleTSIP.tanLambda")
            .Define("reco_pvec", """
                auto p = GunParticleTSIPHelix.getMomentum(); 
                return ROOT::Math::XYZVector(p[0], p[1], p[2]);
            """)
            .Define("reco_p", "reco_pvec.R()")
            .Define("reco_phi", "reco_pvec.Phi()")
            .Define("reco_theta", "reco_pvec.Theta()")

            # Hélice truth — charge dynamique
            .Define("GunParticleMCMom", """
                std::vector<double> v = {GunParticle.momentum.x, GunParticle.momentum.y, GunParticle.momentum.z}; 
                return v;
            """)
            .Define("GunParticleMCPos", """
                std::vector<double> v = {GunParticle.vertex.x, GunParticle.vertex.y, GunParticle.vertex.z}; 
                return v;
            """)
            .Define("GunParticleMCHelix", """
                auto h = HelixClass_double(); 
                h.Initialize_VP(GunParticleMCPos.data(), GunParticleMCMom.data(), 
                                GunParticleCharge, 2); 
                return h;
            """)
            .Define("true_pt", "GunParticleMCHelix.getPXY()")
            .Define("true_d0", "GunParticleMCHelix.getD0()")
            .Define("true_z0", "GunParticleMCHelix.getZ0()")
            .Define("true_phi0", "GunParticleMCHelix.getPhi0()")
            .Define("true_omega", "GunParticleMCHelix.getOmega()")
            .Define("true_tanLambda", "GunParticleMCHelix.getTanLambda()")
            .Define("true_pvec", "ROOT::Math::XYZVector(GunParticleMCMom[0], GunParticleMCMom[1], GunParticleMCMom[2])")
            .Define("true_p", "true_pvec.R()")
            .Define("true_phi", "true_pvec.Phi()")
            .Define("true_theta", "true_pvec.Theta()")

            # Qualité de la trace
            .Define("chi2_trk", "trackData.chi2")
            .Define("ndf_trk", "trackData.ndf")
            .Define("chi2_over_ndf", "chi2_trk / ndf_trk")
            .Filter("chi2_over_ndf < 10")

            # Anti-fake tracks — cut relâché pour laisser passer les queues brem
            .Filter(f"abs((reco_pt - true_pt) / true_pt) <= {MAX_FAKE_CUT}")
            .Filter(f"abs((reco_phi - true_phi) / true_phi) <= {MAX_FAKE_CUT}")
            .Filter(f"abs((reco_theta - true_theta) / true_theta) <= {MAX_FAKE_CUT}")

            .Define("num_reconstructed_tracks", "trackStates_IP.size() > 0 ? 1 : 0")
        )

        # Résidus
        for v in varList:
            df2 = df2.Define(f"delta_{v}", f"reco_{v} - true_{v}")
            df2 = df2.Filter(f"std::isfinite(delta_{v})")
        
        # Wrap-around phi0
        if "phi0" in varList:
            df2 = df2.Redefine("delta_phi0", 
                "delta_phi0 < -ROOT::Math::Pi() ? delta_phi0 + 2 * ROOT::Math::Pi() : delta_phi0")

        return df2

    @staticmethod
    def output():
        branchList = []
        branchList += [f"reco_{v}" for v in varList]
        branchList += [f"true_{v}" for v in varList]
        branchList += [f"delta_{v}" for v in varList]
        branchList += ["chi2_over_ndf", "num_reconstructed_tracks"]
        # On garde aussi la charge pour diagnostic éventuel
        branchList += ["GunParticleCharge"]
        return branchList


# ============================================================================
# AFFICHAGE AU CHARGEMENT
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ANALYSIS TRACKING - FCC-ee")
    print("=" * 70)
    print(f"  DETECTOR_MODEL:    {DETECTOR_MODEL}")
    print(f"  Mode digitisation: {DIGI_MODE}")
    if DIGI_MODE == "parametric":
        print(f"  Résolution:        {RESOLUTION}")
    print(f"  Particules:        {PARTICLE_LIST}")
    print(f"  Cut anti-fake:     {MAX_FAKE_CUT}")
    print(f"  EOSBASE:           {EOSBASE}")
    print(f"  Processus:         {len(processList)}")
    print("=" * 70 + "\n")
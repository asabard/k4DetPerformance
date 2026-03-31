"""
Analysis tracking pour FCC-ee.
Extrait les résidus des paramètres de trace à partir des fichiers de reconstruction.

Usage:
    DIGI_MODE=detailed fccanalysis run analysis_tracking.py
    DIGI_MODE=parametric RESOLUTION=3um fccanalysis run analysis_tracking.py
"""
import os
import sys

# Import de la configuration centrale
# Ajuster le chemin si nécessaire
try:
    from config_tracking import (
        DIGI_MODE, RESOLUTION, EOSBASE, DETECTOR_MODEL, NEVTS, NEVTS_PER_JOB,
        PARTICLE_LIST, THETA_LIST, MOMENTUM_LIST,
        get_reco_input_dir, get_analysis_output_dir, get_reco_file_path,
        file_exists, ensure_dir, VAR_LIST, RESIDUAL_LIST, SPECIAL_LIST
    )
    CONFIG_LOADED = True
except ImportError:
    print("[WARNING] config_tracking.py non trouvé, utilisation de la config locale")
    CONFIG_LOADED = False
    
    # Configuration locale de fallback
    DIGI_MODE = os.environ.get("DIGI_MODE", "detailed")
    RESOLUTION = os.environ.get("RESOLUTION", "3um")
    EOSBASE = "/eos/user/a/asabard/DigiPerformance"
    DETECTOR_MODEL = "CLD_o2_v07"
    NEVTS = "2000"
    NEVTS_PER_JOB = "2000"
    
    PARTICLE_LIST = ["mu"]
    THETA_LIST = ["10", "20", "30", "40", "50", "60", "70", "80"]
    MOMENTUM_LIST = ["1", "3", "5", "10", "20", "30", "60", "100"]
    
    RESIDUAL_LIST = ["d0", "z0", "phi0", "omega", "tanLambda", "phi", "theta"]
    SPECIAL_LIST = ["pt", "p"]

# ============================================================================
# CONFIGURATION DES CHEMINS
# ============================================================================

# Sous-dossier optionnel pour theta (ex: "ThetaNotFixed" ou "")
THETA_FOLDER = ""

# Construction des chemins
if CONFIG_LOADED:
    inputDir = get_reco_input_dir(particle="mu", theta_folder=THETA_FOLDER)
    outputDir = get_analysis_output_dir(particle="mu")
else:
    inputDir = os.path.join(EOSBASE, f"REC_{DIGI_MODE}", "mu-", THETA_FOLDER).rstrip('/')
    outputDir = f"{EOSBASE}/ANALYSIS/{DIGI_MODE}/mu/"

# ============================================================================
# CONSTRUCTION DE LA LISTE DES PROCESSUS AVEC VÉRIFICATION
# ============================================================================

def build_process_list_safe():
    """
    Construit la liste des processus en vérifiant l'existence des fichiers.
    Les fichiers manquants sont ignorés avec un warning.
    """
    process_list = {}
    missing_files = []
    
    for theta in THETA_LIST:
        for momentum in MOMENTUM_LIST:
            # Construction du chemin selon le mode de digitalisation
            if DIGI_MODE == "parametric":
                path_prefix = f"{momentum}GeV/{RESOLUTION}/{NEVTS}evts"
            else:
                path_prefix = f"{momentum}GeV/{NEVTS}evts"
            
            # Nom du fichier (l'extension .root est ajoutée par fccanalysis)
            fileName = f"{path_prefix}/REC_{DIGI_MODE}_mu-_{momentum}GeV_theta{theta}_{NEVTS}evts_REC.edm4hep"
            
            # Chemin complet pour vérification
            full_path = os.path.join(inputDir, fileName + ".root")
            
            # Nom de sortie
            outputName = f"mu_{theta}deg_{momentum}GeV_{NEVTS}evts"
            
            # Vérifier si le fichier existe
            if os.path.isfile(full_path):
                process_list[fileName] = {"output": outputName}
            else:
                missing_files.append((theta, momentum, full_path))
    
    # Afficher les warnings pour les fichiers manquants
    if missing_files:
        print("\n" + "=" * 70)
        print(f"[WARNING] {len(missing_files)} fichiers d'entrée manquants:")
        print("=" * 70)
        for theta, momentum, path in missing_files:
            print(f"  - theta={theta}°, p={momentum}GeV")
            # print(f"    {path}")  # Décommenter pour voir les chemins complets
        print("=" * 70)
        print(f"[INFO] {len(process_list)} fichiers seront traités.\n")
    
    if not process_list:
        print("[ERROR] Aucun fichier d'entrée trouvé!")
        print(f"        Répertoire recherché: {inputDir}")
        sys.exit(1)
    
    return process_list

# Construire la liste des processus
processList = build_process_list_safe()

# Nombre de CPUs (-1 = tous)
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
# LISTE DES VARIABLES À ANALYSER
# ============================================================================

varList = ["pt", "d0", "z0", "phi0", "omega", "tanLambda", "p", "phi", "theta"]

# ============================================================================
# CLASSE D'ANALYSE RDataFrame
# ============================================================================

class RDFanalysis():
    
    @staticmethod
    def analysers(df):
        """Définit les transformations RDataFrame pour l'analyse."""
        
        df2 = (df
            # Alias pour les collections
            .Alias("MCTrackAssociations0", "_SiTracksMCTruthLink_from.index")
            .Alias("MCTrackAssociations1", "_SiTracksMCTruthLink_to.index")
            .Alias("SiTracks_Refitted_1", "_SiTracks_Refitted_trackStates")

            # Particule générée (gun particle)
            .Define("GunParticle_index", "MCParticles.generatorStatus == 1")
            .Define("GunParticle", "MCParticles[GunParticle_index][0]")

            # Track states au point d'impact (IP)
            .Define("trackStates_IP", "SiTracks_Refitted_1[SiTracks_Refitted_1.location == 1]")
            .Define("MC2TrackIndex", "MCTruthTrackIndex(MCTrackAssociations0, MCTrackAssociations1, MCParticles)")
            .Define("GunParticleTrackIndex", "MC2TrackIndex[GunParticle_index][0]")
            .Define("GunParticleTSIP", "trackStates_IP[GunParticleTrackIndex]")

            # Particules matchées
            .Define("MatchedGunParticle_1", "MCParticles[MC2TrackIndex != -1]")
            .Define("MatchedGunParticle", "FCCAnalyses::MCParticle::sel_genStatus(1)(MatchedGunParticle_1)")

            # Données de la trace
            .Define("trackData", "SiTracks_Refitted[GunParticleTrackIndex]")

            # Calculs d'hélice pour les paramètres reconstruits
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

            # Calculs d'hélice pour les paramètres vrais (MC truth)
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
                h.Initialize_VP(GunParticleMCPos.data(), GunParticleMCMom.data(), -1, 2); 
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

            # Suppression des fausses traces
            .Filter("abs((reco_pt - true_pt) / true_pt) <= 0.20")
            .Filter("abs((reco_phi - true_phi) / true_phi) <= 0.20")
            .Filter("abs((reco_theta - true_theta) / true_theta) <= 0.20")

            # Compteur de traces reconstruites
            .Define("num_reconstructed_tracks", "trackStates_IP.size() > 0 ? 1 : 0")
        )

        # Définir les résidus pour chaque variable
        for v in varList:
            df2 = df2.Define(f"delta_{v}", f"reco_{v} - true_{v}")
            df2 = df2.Filter(f"std::isfinite(delta_{v})")
        
        # Correction du wrap-around pour phi0
        if "phi0" in varList:
            df2 = df2.Redefine("delta_phi0", 
                "delta_phi0 < -ROOT::Math::Pi() ? delta_phi0 + 2 * ROOT::Math::Pi() : delta_phi0")

        return df2

    @staticmethod
    def output():
        """Liste des branches à sauvegarder."""
        branchList = []
        branchList += [f"reco_{v}" for v in varList]
        branchList += [f"true_{v}" for v in varList]
        branchList += [f"delta_{v}" for v in varList]
        branchList += ["chi2_over_ndf"]
        branchList += ["num_reconstructed_tracks"]
        return branchList


# ============================================================================
# AFFICHAGE DE LA CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ANALYSIS TRACKING - FCC-ee")
    print("=" * 70)
    print(f"  Mode digitisation: {DIGI_MODE}")
    if DIGI_MODE == "parametric":
        print(f"  Résolution:        {RESOLUTION}")
    print(f"  Input dir:         {inputDir}")
    print(f"  Output dir:        {outputDir}")
    print(f"  Processus:         {len(processList)}")
    print("=" * 70 + "\n")
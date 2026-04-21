"""
Configuration centrale pour l'analyse de tracking FCC-ee.
Ce fichier est importé par tous les scripts de la chaîne d'analyse.

CHANGEMENTS vs version précédente :
- DETECTOR_MODEL lu via variable d'environnement (comme config.sh)
- EOSBASE dérivé automatiquement : /eos/.../DigiPerformance/${DETECTOR_MODEL}/
- PARTICLE_LIST étendu à ["mu", "e", "pi"] par défaut
- Ajout de SIGMA_EFF_FRACTION et FAKE_CUT (par particule)
"""
import os
import ROOT
import math

# ============================================================================
# CONFIGURATION GLOBALE — synchronisée avec config.sh
# ============================================================================

# Mode de digitisation: "detailed" ou "parametric"
DIGI_MODE = os.environ.get("DIGI_MODE", "detailed")

# Résolution pour le mode parametric
RESOLUTION = os.environ.get("RESOLUTION", "3um")

# Modèle de détecteur (lu depuis l'env, même convention que config.sh)
DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "CLD_o2_v07")

# Base EOS — inclut maintenant le modèle de détecteur pour séparer les prod
EOSBASE = f"/eos/user/a/asabard/DigiPerformance/{DETECTOR_MODEL}"

# Nombre d'événements
NEVTS = os.environ.get("NEVTS", "2000")
NEVTS_PER_JOB = "2000"

# ============================================================================
# MODE D'AFFICHAGE DE L'AXE X (p ou pT)
# ============================================================================

X_AXIS_MODE = os.environ.get("X_AXIS_MODE", "p")

def get_x_value(momentum, theta):
    """Valeur à mettre en abscisse des plots vs impulsion."""
    if X_AXIS_MODE == "pt":
        return float(momentum) * math.sin(math.radians(float(theta)))
    return float(momentum)

def get_x_label():
    return "p_{T} [GeV]" if X_AXIS_MODE == "pt" else "p [GeV]"

# ============================================================================
# LISTES DE PARAMÈTRES CINÉMATIQUES
# ============================================================================

# Particules disponibles - défaut étendu aux 3 particules
# Note : l'ordre compte pour les plots comparatifs
PARTICLE_LIST = os.environ.get("PARTICLE_LIST", "mu,e,pi").split(",")

# Angles theta disponibles (en degrés)
THETA_LIST = ["10", "20", "30", "40", "50", "60", "70", "80", "90"]

# Impulsions disponibles (en GeV)
MOMENTUM_LIST = ["1", "2", "3", "5", "10", "15", "20", "30", "50", "60", "100", "150"]

# Listes pour les plots superposés
STACK_MOMENTUM_LIST = ["1", "10", "100"]
STACK_THETA_LIST = ["10", "30", "50", "70", "90"]

# ============================================================================
# CUTS ANTI-FAKE PAR PARTICULE
# ============================================================================
# Raison : pour les e⁻, le bremsstrahlung peut faire perdre > 20 % d'énergie
# de façon physique. Le cut historique à 0.20 jetait ces événements et
# biaisait la résolution. On relâche à 0.50 pour garder les queues brem,
# tout en rejetant les vraies fake tracks (perte complète de suivi).

FAKE_CUT = {
    "mu":  0.20,  # muons : distribution propre, cut strict OK
    "e":   0.50,  # électrons : queue brem, cut large nécessaire
    "pi":  0.30,  # pions : MS + hadronic interactions à basse p
    "mu-": 0.20,  # alias avec la charge
    "e-":  0.50,
    "pi-": 0.30,
}

def get_fake_cut(particle):
    """Retourne le cut anti-fake à appliquer pour une particule donnée."""
    return FAKE_CUT.get(particle, 0.50)

# ============================================================================
# SIGMA EFFECTIF (métrique model-free)
# ============================================================================

# Fraction cible pour σ_eff (0.6827 = équivalent ±1σ gaussien)
SIGMA_EFF_FRACTION = 0.6827

# Seuil au-delà duquel on considère que les queues sont importantes
# (ratio sigma_eff / sigma_gauss > ce seuil => queue significative)
TAIL_WARNING_THRESHOLD = 1.30

# ============================================================================
# CHEMINS D'ENTRÉE/SORTIE
# ============================================================================

def get_reco_input_dir(particle="mu", theta_folder=""):
    """Chemin vers les fichiers de reconstruction."""
    base_path = os.path.join(EOSBASE, f"REC_{DIGI_MODE}", f"{particle}-", theta_folder)
    return base_path.rstrip('/')


def get_analysis_output_dir(particle="mu"):
    """Chemin de sortie pour les fichiers d'analyse (résidus)."""
    return f"{EOSBASE}/ANALYSIS/{DIGI_MODE}/{particle}/"


def get_plots_output_dir(particle="mu"):
    """Chemin de sortie pour les plots finaux."""
    suffix = "_pt" if X_AXIS_MODE == "pt" else ""
    return f"{EOSBASE}/ANALYSIS/{DIGI_MODE}/{particle}/plots{suffix}/"


def get_reco_file_path(particle, theta, momentum, theta_folder=""):
    """Construit le chemin complet vers un fichier de reconstruction."""
    if DIGI_MODE == "parametric":
        path_prefix = f"{momentum}GeV/{RESOLUTION}/{NEVTS}evts"
    else:
        path_prefix = f"{momentum}GeV/{NEVTS}evts"
    
    file_name = f"{path_prefix}/REC_{DIGI_MODE}_{particle}-_{momentum}GeV_theta{theta}_{NEVTS}evts_REC.edm4hep"
    output_name = f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts"
    
    return file_name, output_name


def get_analysis_file_path(particle, theta, momentum):
    """Chemin vers un fichier d'analyse."""
    output_dir = get_analysis_output_dir(particle)
    file_name = f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts.root"
    return os.path.join(output_dir, file_name)


# ============================================================================
# VÉRIFICATION DES FICHIERS
# ============================================================================

def file_exists(file_path):
    return os.path.isfile(file_path)


def check_root_file(file_path, tree_name="events"):
    if not file_exists(file_path):
        return False
    try:
        f = ROOT.TFile.Open(file_path)
        if not f or f.IsZombie():
            return False
        tree = f.Get(tree_name)
        is_valid = tree is not None and tree.GetEntries() > 0
        f.Close()
        return is_valid
    except Exception:
        return False


def get_available_processes(particle_list=None, theta_list=None, momentum_list=None, 
                           input_dir=None, verbose=True):
    if particle_list is None:
        particle_list = PARTICLE_LIST
    if theta_list is None:
        theta_list = THETA_LIST
    if momentum_list is None:
        momentum_list = MOMENTUM_LIST
    
    available = {}
    missing = []
    
    for particle in particle_list:
        if input_dir is None:
            base_dir = get_analysis_output_dir(particle)
        else:
            base_dir = input_dir
            
        for theta in theta_list:
            for momentum in momentum_list:
                process_name = f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts"
                file_path = os.path.join(base_dir, f"{process_name}.root")
                
                if file_exists(file_path):
                    available[process_name] = {}
                else:
                    missing.append(process_name)
    
    if verbose and missing:
        print(f"[WARNING] {len(missing)} fichiers manquants sur {len(missing) + len(available)}:")
        for m in missing[:10]:
            print(f"  - {m}")
        if len(missing) > 10:
            print(f"  ... et {len(missing) - 10} autres")
    
    return available


def filter_existing_files(file_list, verbose=True):
    existing = []
    missing = []
    for f in file_list:
        if file_exists(f):
            existing.append(f)
        else:
            missing.append(f)
    if verbose and missing:
        print(f"[WARNING] {len(missing)} fichiers manquants:")
        for m in missing:
            print(f"  - {m}")
    return existing


# ============================================================================
# VARIABLES ET TITRES POUR LES PLOTS
# ============================================================================

RESIDUAL_LIST = ["d0", "z0", "phi0", "omega", "tanLambda", "phi", "theta"]
SPECIAL_LIST = ["pt", "p"]
VAR_LIST = [f"delta_{v}" for v in RESIDUAL_LIST] + [f"sdelta_{v}" for v in SPECIAL_LIST]

AXIS_TITLES = {
    "delta_d0": "#sigma(#Deltad_{0}) [#mum]",
    "delta_z0": "#sigma(#Deltaz_{0}) [#mum]",
    "delta_phi0": "#Delta#phi_{0}",
    "delta_omega": "#Delta#Omega",
    "delta_tanLambda": "tan #Lambda",
    "delta_phi": "#sigma(#Delta#phi) [mrad]",
    "delta_theta": "#sigma(#Delta#theta) [mrad]",
    "sdelta_pt": "#sigma(#Deltap_{T}/p_{T,true}^{2}) [GeV^{-1}]",
    "sdelta_p": "#sigma(#Deltap/p_{true}^{2}) [GeV^{-1}]",
}

UNIT_SCALE = {
    "delta_d0": 1e3, "delta_z0": 1e3,
    "delta_phi0": 1.0, "delta_omega": 1.0, "delta_tanLambda": 1.0,
    "delta_phi": 1e3, "delta_theta": 1e3,
    "sdelta_pt": 1.0, "sdelta_p": 1.0,
}

# Variables pour lesquelles une Crystal Ball est préférable à une gaussienne
# (queues non-gaussiennes dues au brem / interactions hadroniques)
CB_VARIABLES = ["delta_omega", "sdelta_pt", "sdelta_p"]

def should_use_crystalball(particle, variable):
    """
    Décide si on doit utiliser une Crystal Ball au lieu d'une gaussienne.
    
    - Électrons : oui pour les variables d'impulsion (brem)
    - Pions : oui aussi pour les variables d'impulsion (hadronic interactions)
    - Muons : jamais (distribution bien gaussienne)
    """
    if variable not in CB_VARIABLES:
        return False
    # Normalisation du nom de particule (peut être "e", "e-", "electron"...)
    p = particle.lower().rstrip("-+")
    if p in ("e", "electron"):
        return True
    if p in ("pi", "pion"):
        return True
    return False


# ============================================================================
# STYLES DE PLOTS
# ============================================================================

MARKER_STYLES = [ROOT.kOpenTriangleUp, ROOT.kOpenSquare, ROOT.kOpenDiamond, 
                 ROOT.kOpenCross, ROOT.kOpenCircle]
MARKER_STYLES_FULL = [ROOT.kFullTriangleUp, ROOT.kFullSquare, ROOT.kFullDiamond, 
                      ROOT.kFullCross, ROOT.kFullCircle]
COLORS = [ROOT.kBlue, ROOT.kRed, ROOT.kMagenta, ROOT.kGreen, ROOT.kBlack]

# Couleurs dédiées pour la comparaison par particule
PARTICLE_COLORS = {
    "mu": ROOT.kBlue,
    "e":  ROOT.kRed,
    "pi": ROOT.kBlack,
}

PARTICLE_MARKERS_GAUSS = {
    "mu": ROOT.kFullCircle,
    "e":  ROOT.kFullSquare,
    "pi": ROOT.kFullTriangleUp,
}

PARTICLE_MARKERS_EFF = {
    "mu": ROOT.kOpenCircle,
    "e":  ROOT.kOpenSquare,
    "pi": ROOT.kOpenTriangleUp,
}

CANVAS_WIDTH = 900
CANVAS_HEIGHT = 800
PLOT_MARGIN_LEFT = 0.15
PLOT_MARGIN_BOTTOM = 0.15

# ============================================================================
# RANGES DES AXES Y
# ============================================================================

Y_AXIS_RANGE_THETA = {
    "Canvas_delta_d0": (0.5, 1e4),
    "Canvas_delta_z0": (0.5, 1e4),
    "Canvas_delta_phi0": (1e-5, 1),
    "Canvas_delta_omega": (1e-8, 1e-2),
    "Canvas_delta_tanLambda": (1e-5, 10),
    "Canvas_delta_phi": (1e-2, 1e3),
    "Canvas_delta_theta": (1e-2, 1e3),
    "Canvas_sdelta_pt": (1e-5, 1e2),
    "Canvas_sdelta_p": (1e-5, 1e2),
}

Y_AXIS_RANGE_MOMENTUM = {
    "Canvas_delta_d0": (0.5, 1e3),
    "Canvas_delta_z0": (0.5, 1e4),
    "Canvas_delta_phi0": (1e-5, 1e-1),
    "Canvas_delta_omega": (1e-8, 1e-3),
    "Canvas_delta_tanLambda": (1e-5, 10),
    "Canvas_delta_phi": (1e-2, 1e2),
    "Canvas_delta_theta": (1e-2, 10),
    "Canvas_sdelta_pt": (1e-5, 10),
    "Canvas_sdelta_p": (1e-5, 1),
}

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def pname(particle, theta, momentum):
    """Nom standardisé d'un processus."""
    return f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts"


def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"[INFO] Répertoire créé: {directory}")


def setup_root_style():
    ROOT.gStyle.SetOptFit(1111)
    ROOT.gROOT.SetBatch(True)


def get_particle_symbol(particle):
    symbols = {"mu": r"\mu", "pi": r"\pi", "e": r"e"}
    return symbols.get(particle, particle)


CANVAS_NAMES = [
    "Canvas_delta_d0", "Canvas_delta_z0", "Canvas_delta_phi0", "Canvas_delta_omega",
    "Canvas_delta_tanLambda", "Canvas_delta_phi", "Canvas_delta_theta",
    "Canvas_sdelta_pt", "Canvas_sdelta_p"
]


# ============================================================================
# AFFICHAGE AU CHARGEMENT
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Configuration Tracking FCC-ee")
    print("=" * 60)
    print(f"  DETECTOR_MODEL: {DETECTOR_MODEL}")
    print(f"  DIGI_MODE:      {DIGI_MODE}")
    print(f"  RESOLUTION:     {RESOLUTION}")
    print(f"  NEVTS:          {NEVTS}")
    print(f"  PARTICLE_LIST:  {PARTICLE_LIST}")
    print(f"  THETA_LIST:     {THETA_LIST}")
    print(f"  MOMENTUM_LIST:  {MOMENTUM_LIST}")
    print(f"  FAKE_CUT:       {FAKE_CUT}")
    print("-" * 60)
    print(f"  EOSBASE:        {EOSBASE}")
    print(f"  Analysis out:   {get_analysis_output_dir()}")
    print(f"  Plots out:      {get_plots_output_dir()}")
    print("=" * 60)
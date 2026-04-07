"""
Configuration centrale pour l'analyse de tracking FCC-ee.
Ce fichier est importé par tous les scripts de la chaîne d'analyse.
"""
import os
import ROOT

# ============================================================================
# CONFIGURATION GLOBALE
# ============================================================================

# Mode de digitisation: "detailed" ou "parametric"
DIGI_MODE = os.environ.get("DIGI_MODE", "detailed")

# Résolution pour le mode parametric
RESOLUTION = os.environ.get("RESOLUTION", "3um")

# Base EOS
EOSBASE = "/eos/user/a/asabard/DigiPerformance"

# Modèle de détecteur
DETECTOR_MODEL = "CLD_o2_v07"

# Nombre d'événements
NEVTS = "2000"
NEVTS_PER_JOB = "2000"

# ============================================================================
# LISTES DE PARAMÈTRES CINÉMATIQUES
# ============================================================================

# Particules disponibles
PARTICLE_LIST = ["mu"]  # Peut être étendu: ["mu", "e", "pi"]

# Angles theta disponibles (en degrés)
# Note: 89° n'est pas inclus par défaut car pb de simulation dans thetanotfixed ca devient 90°
THETA_LIST = ["10", "20", "30", "40", "50", "60", "70", "80", "90"]
#THETA_LIST = ["10", "20", "30", "40", "50", "60", "70", "80", "89"]


# Impulsions disponibles (en GeV)
#MOMENTUM_LIST = ["1", "3", "5", "10", "20", "30", "60", "100"]
MOMENTUM_LIST = ["1", "10", "100"]

# ============================================================================
# LISTES POUR LES PLOTS SUPERPOSÉS
# ============================================================================

# Impulsions pour les plots en fonction de theta
STACK_MOMENTUM_LIST = ["1", "10", "100"]

# Angles pour les plots en fonction de l'impulsion
STACK_THETA_LIST = ["10", "30", "50", "70", "90"]

# ============================================================================
# CHEMINS D'ENTRÉE/SORTIE
# ============================================================================

def get_reco_input_dir(particle="mu", theta_folder=""):
    """
    Chemin vers les fichiers de reconstruction (input pour analysis_tracking).
    
    Args:
        particle: particule ("mu", "e", "pi")
        theta_folder: sous-dossier optionnel (ex: "ThetaNotFixed")
    
    Returns:
        Chemin complet vers le répertoire d'entrée
    """
    base_path = os.path.join(EOSBASE, f"REC_{DIGI_MODE}", f"{particle}-", theta_folder)
    return base_path.rstrip('/')


def get_analysis_output_dir(particle="mu"):
    """
    Chemin de sortie pour les fichiers d'analyse (ROOT trees avec résidus).
    C'est aussi l'input pour plots_tracking.py.
    """
    return f"{EOSBASE}/ANALYSIS/{DIGI_MODE}/{particle}/"


def get_plots_output_dir(particle="mu"):
    """
    Chemin de sortie pour les plots finaux.
    """
    return f"{EOSBASE}/ANALYSIS/{DIGI_MODE}/{particle}/plots/"


def get_reco_file_path(particle, theta, momentum, theta_folder=""):
    """
    Construit le chemin complet vers un fichier de reconstruction.
    
    Returns:
        Tuple (chemin_relatif, nom_sortie) pour processList
    """
    if DIGI_MODE == "parametric":
        path_prefix = f"{momentum}GeV/{RESOLUTION}/{NEVTS}evts"
    else:
        path_prefix = f"{momentum}GeV/{NEVTS}evts"
    
    file_name = f"{path_prefix}/REC_{DIGI_MODE}_{particle}-_{momentum}GeV_theta{theta}_{NEVTS}evts_REC.edm4hep"
    output_name = f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts"
    
    return file_name, output_name


def get_analysis_file_path(particle, theta, momentum):
    """
    Chemin vers un fichier d'analyse (output de analysis_tracking, input de plots_tracking).
    """
    output_dir = get_analysis_output_dir(particle)
    file_name = f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts.root"
    return os.path.join(output_dir, file_name)


# ============================================================================
# FONCTIONS DE VÉRIFICATION DES FICHIERS
# ============================================================================

def file_exists(file_path):
    """Vérifie si un fichier existe."""
    return os.path.isfile(file_path)


def check_root_file(file_path, tree_name="events"):
    """
    Vérifie si un fichier ROOT existe et contient le TTree attendu.
    
    Returns:
        True si le fichier est valide, False sinon
    """
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
    """
    Retourne uniquement les processus dont les fichiers d'entrée existent.
    
    Args:
        particle_list: liste de particules (défaut: PARTICLE_LIST)
        theta_list: liste d'angles theta (défaut: THETA_LIST)
        momentum_list: liste d'impulsions (défaut: MOMENTUM_LIST)
        input_dir: répertoire d'entrée (défaut: analysis output dir)
        verbose: afficher les fichiers manquants
    
    Returns:
        dict: processList filtré avec seulement les fichiers existants
    """
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
        for m in missing[:10]:  # Afficher les 10 premiers
            print(f"  - {m}")
        if len(missing) > 10:
            print(f"  ... et {len(missing) - 10} autres")
    
    return available


def filter_existing_files(file_list, verbose=True):
    """
    Filtre une liste de chemins de fichiers pour ne garder que ceux qui existent.
    
    Args:
        file_list: liste de chemins de fichiers
        verbose: afficher les fichiers manquants
    
    Returns:
        Liste filtrée des fichiers existants
    """
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

# Variables résiduelles (paramètres d'hélice)
RESIDUAL_LIST = ["d0", "z0", "phi0", "omega", "tanLambda", "phi", "theta"]

# Variables spéciales (normalisées par p² ou pT²)
SPECIAL_LIST = ["pt", "p"]

# Liste complète des variables
VAR_LIST = [f"delta_{v}" for v in RESIDUAL_LIST] + [f"sdelta_{v}" for v in SPECIAL_LIST]

# Titres des axes Y
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

# Facteurs de conversion d'unités
UNIT_SCALE = {
    "delta_d0": 1e3,      # mm -> µm
    "delta_z0": 1e3,      # mm -> µm
    "delta_phi0": 1.0,
    "delta_omega": 1.0,
    "delta_tanLambda": 1.0,
    "delta_phi": 1e3,     # rad -> mrad
    "delta_theta": 1e3,   # rad -> mrad
    "sdelta_pt": 1.0,
    "sdelta_p": 1.0,
}

# ============================================================================
# STYLES DE PLOTS
# ============================================================================

# Styles de marqueurs
MARKER_STYLES = [ROOT.kOpenTriangleUp, ROOT.kOpenSquare, ROOT.kOpenDiamond, 
                 ROOT.kOpenCross, ROOT.kOpenCircle]
MARKER_STYLES_FULL = [ROOT.kFullTriangleUp, ROOT.kFullSquare, ROOT.kFullDiamond, 
                      ROOT.kFullCross, ROOT.kFullCircle]

# Couleurs
COLORS = [ROOT.kBlue, ROOT.kRed, ROOT.kMagenta, ROOT.kGreen, ROOT.kBlack]

# Dimensions du canvas
CANVAS_WIDTH = 900
CANVAS_HEIGHT = 800

# Marges
PLOT_MARGIN_LEFT = 0.15
PLOT_MARGIN_BOTTOM = 0.15

# ============================================================================
# RANGES DES AXES Y POUR LES DIFFÉRENTS TYPES DE PLOTS
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
    """Génère le nom standardisé d'un processus."""
    return f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts"


def ensure_dir(directory):
    """Crée un répertoire s'il n'existe pas."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"[INFO] Répertoire créé: {directory}")


def setup_root_style():
    """Configure le style ROOT pour les plots."""
    ROOT.gStyle.SetOptFit(1111)
    ROOT.gROOT.SetBatch(True)


def get_particle_symbol(particle):
    """Retourne le symbole LaTeX d'une particule."""
    symbols = {"mu": r"\mu", "pi": r"\pi", "e": r"e"}
    return symbols.get(particle, particle)


# ============================================================================
# LISTE DES CANVAS STANDARDS
# ============================================================================

CANVAS_NAMES = [
    "Canvas_delta_d0", "Canvas_delta_z0", "Canvas_delta_phi0", "Canvas_delta_omega",
    "Canvas_delta_tanLambda", "Canvas_delta_phi", "Canvas_delta_theta",
    "Canvas_sdelta_pt", "Canvas_sdelta_p"
]


# ============================================================================
# AFFICHAGE DE LA CONFIGURATION AU CHARGEMENT
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Configuration Tracking FCC-ee")
    print("=" * 60)
    print(f"  DIGI_MODE:      {DIGI_MODE}")
    print(f"  RESOLUTION:     {RESOLUTION}")
    print(f"  DETECTOR:       {DETECTOR_MODEL}")
    print(f"  NEVTS:          {NEVTS}")
    print(f"  Particles:      {PARTICLE_LIST}")
    print(f"  Theta list:     {THETA_LIST}")
    print(f"  Momentum list:  {MOMENTUM_LIST}")
    print("-" * 60)
    print(f"  RECO input:     {get_reco_input_dir()}")
    print(f"  Analysis out:   {get_analysis_output_dir()}")
    print(f"  Plots out:      {get_plots_output_dir()}")
    print("=" * 60)

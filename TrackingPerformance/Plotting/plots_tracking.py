"""
Plots tracking pour FCC-ee.
Génère les plots de résolution des paramètres de trace en fonction de p et theta.

Usage:
    DIGI_MODE=detailed python plots_tracking.py
    DIGI_MODE=parametric python plots_tracking.py
"""
import ROOT
import numpy as np
import os
import sys

# ============================================================================
# IMPORT DE LA CONFIGURATION
# ============================================================================

try:
    from config_tracking import (
        DIGI_MODE, NEVTS,
        PARTICLE_LIST, THETA_LIST, MOMENTUM_LIST,
        STACK_MOMENTUM_LIST, STACK_THETA_LIST,
        get_analysis_output_dir, get_plots_output_dir,
        get_available_processes, ensure_dir, pname, setup_root_style,
        VAR_LIST, RESIDUAL_LIST, SPECIAL_LIST, AXIS_TITLES, UNIT_SCALE,
        MARKER_STYLES, COLORS, CANVAS_WIDTH, CANVAS_HEIGHT,
        PLOT_MARGIN_LEFT, PLOT_MARGIN_BOTTOM,
        file_exists, filter_existing_files
    )
    CONFIG_LOADED = True
    print("[INFO] Configuration chargée depuis config_tracking.py")
except ImportError:
    print("[WARNING] config_tracking.py non trouvé, utilisation de la config locale")
    CONFIG_LOADED = False

# ============================================================================
# CONFIGURATION LOCALE (fallback)
# ============================================================================

if not CONFIG_LOADED:
    DIGI_MODE = os.environ.get("DIGI_MODE", "detailed")
    NEVTS = "2000"
    
    PARTICLE_LIST = ["mu"]
    THETA_LIST = ["10", "20", "30", "40", "50", "60", "70", "80"]
    MOMENTUM_LIST = ["1", "3", "5", "10", "20", "30", "60", "100"]
    STACK_MOMENTUM_LIST = ["1", "10", "100"]
    STACK_THETA_LIST = ["10", "30", "50", "70"]
    
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
        "delta_d0": 1e3, "delta_z0": 1e3, "delta_phi0": 1.0, "delta_omega": 1.0,
        "delta_tanLambda": 1.0, "delta_phi": 1e3, "delta_theta": 1e3,
        "sdelta_pt": 1.0, "sdelta_p": 1.0,
    }
    
    MARKER_STYLES = [ROOT.kOpenTriangleUp, ROOT.kOpenSquare, ROOT.kOpenDiamond, 
                     ROOT.kOpenCross, ROOT.kOpenCircle]
    COLORS = [ROOT.kBlue, ROOT.kRed, ROOT.kMagenta, ROOT.kGreen, ROOT.kBlack]
    CANVAS_WIDTH, CANVAS_HEIGHT = 900, 800
    PLOT_MARGIN_LEFT, PLOT_MARGIN_BOTTOM = 0.15, 0.15
    
    def pname(particle, theta, momentum):
        return f"{particle}_{theta}deg_{momentum}GeV_{NEVTS}evts"
    
    def get_analysis_output_dir(particle="mu"):
        return f"/eos/user/a/asabard/DigiPerformance/ANALYSIS/{DIGI_MODE}/{particle}/"
    
    def get_plots_output_dir(particle="mu"):
        return f"/eos/user/a/asabard/DigiPerformance/ANALYSIS/{DIGI_MODE}/{particle}/plots/"
    
    def ensure_dir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    def file_exists(path):
        return os.path.isfile(path)

# ============================================================================
# CONFIGURATION ROOT
# ============================================================================

ROOT.gStyle.SetOptFit(1111)
ROOT.gROOT.SetBatch(True)

# ============================================================================
# CHEMINS
# ============================================================================

inputDir = get_analysis_output_dir("mu")
outputDir = get_plots_output_dir("mu")
ensure_dir(outputDir)

print(f"\n[INFO] Input:  {inputDir}")
print(f"[INFO] Output: {outputDir}\n")

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def filter_data_std(data, threshold=2.5, n_selections=3):
    """Filtre itératif des données à ±threshold*sigma."""
    filtered_data = data
    for _ in range(n_selections):
        if len(filtered_data) < 3:
            break
        mean = np.mean(filtered_data)
        std = np.std(filtered_data)
        if std == 0:
            break
        filtered_data = [d for d in filtered_data if abs(d - mean) < threshold * std]
    return filtered_data


def check_process_files():
    """
    Vérifie quels fichiers de processus existent et retourne une liste filtrée.
    """
    available = {}
    missing = []
    
    for particle in PARTICLE_LIST:
        for theta in THETA_LIST:
            for momentum in MOMENTUM_LIST:
                proc_name = pname(particle, theta, momentum)
                file_path = os.path.join(inputDir, f"{proc_name}.root")
                
                if file_exists(file_path):
                    available[proc_name] = file_path
                else:
                    missing.append((particle, theta, momentum))
    
    if missing:
        print(f"[WARNING] {len(missing)} fichiers manquants sur {len(missing) + len(available)}:")
        for p, t, m in missing[:5]:
            print(f"  - {pname(p, t, m)}")
        if len(missing) > 5:
            print(f"  ... et {len(missing) - 5} autres")
        print()
    
    return available


# ============================================================================
# CHARGEMENT DES DONNÉES
# ============================================================================

print("[INFO] Vérification des fichiers d'entrée...")
available_processes = check_process_files()

if not available_processes:
    print("[ERROR] Aucun fichier d'entrée trouvé!")
    sys.exit(1)

processList = {p: {} for p in available_processes}
print(f"[INFO] {len(processList)} fichiers à traiter\n")

# Chargement des DataFrames
print("[INFO] Chargement des RDataFrames...")
df = {}
var_col_rp = {}

for p, fpath in available_processes.items():
    try:
        df[p] = ROOT.RDataFrame("events", fpath)
        
        # Définir les variables normalisées
        for v in SPECIAL_LIST:
            df[p] = df[p].Define(f"sdelta_{v}", f"delta_{v} / (true_{v} * true_{v})")
        
        var_col_rp[p] = {}
        for v in VAR_LIST:
            var_col_rp[p][v] = df[p].Take["double"](v)
            
    except Exception as e:
        print(f"[WARNING] Erreur lors du chargement de {p}: {e}")
        if p in df:
            del df[p]
        if p in var_col_rp:
            del var_col_rp[p]

# Mettre à jour processList avec seulement les fichiers chargés avec succès
processList = {p: {} for p in df.keys()}
print(f"[INFO] {len(processList)} fichiers chargés avec succès\n")

# ============================================================================
# FILTRAGE ET CRÉATION DES HISTOGRAMMES
# ============================================================================

print("[INFO] Création des histogrammes...")
var_col = {}
var_low = {}
var_high = {}
h = {}

for p in processList:
    var_col[p] = {}
    var_low[p] = {}
    var_high[p] = {}
    h[p] = {}
    
    for v in VAR_LIST:
        try:
            # Récupérer et filtrer les données
            data = sorted(var_col_rp[p][v].GetValue())
            filtered = filter_data_std(data, threshold=2.5, n_selections=3)
            
            if len(filtered) < 10:
                print(f"  [WARNING] {p}/{v}: pas assez de données après filtrage")
                continue
            
            var_col[p][v] = filtered
            var_low[p][v] = min(filtered)
            var_high[p][v] = max(filtered)
            
            # Créer l'histogramme
            h[p][v] = (df[p]
                .Filter(f"{v} > {var_low[p][v]} && {v} < {var_high[p][v]}")
                .Histo1D((v, f"{p};{AXIS_TITLES[v]}", 200, var_low[p][v], var_high[p][v]), v)
            )
        except Exception as e:
            print(f"  [WARNING] Erreur pour {p}/{v}: {e}")

# ============================================================================
# FITS ET SAUVEGARDE INDIVIDUELLE
# ============================================================================

print("[INFO] Ajustement des histogrammes et sauvegarde...")
mean = {}
mean_err = {}
sigma = {}
sigma_err = {}

for p in processList:
    fname = f"{outputDir}/{p}.pdf"
    root_fname = ROOT.TFile(f"{outputDir}/{p}.root", "RECREATE")
    
    mean[p] = {}
    mean_err[p] = {}
    sigma[p] = {}
    sigma_err[p] = {}
    
    c_hist = ROOT.TCanvas(f"c_{p}", f"Histograms {p}", 800, 600)
    root_fname.cd()
    c_hist.Print(f"{fname}[")
    
    for v in VAR_LIST:
        if v not in h[p]:
            # Valeurs par défaut si l'histogramme n'existe pas
            mean[p][v] = 0
            mean_err[p][v] = 0
            sigma[p][v] = 0
            sigma_err[p][v] = 0
            continue
            
        try:
            # Fit gaussien
            f = ROOT.TF1(f"f_{p}_{v}", "gaus", var_low[p][v], var_high[p][v])
            h[p][v].Fit(f, "RQ")
            
            mean[p][v] = f.GetParameter(1)
            mean_err[p][v] = f.GetParError(1)
            sigma[p][v] = f.GetParameter(2)
            sigma_err[p][v] = f.GetParError(2)
            
            h[p][v].Write(f"hist_{p}_{v}")
            h[p][v].Draw()
            c_hist.Print(fname)
            
        except Exception as e:
            print(f"  [WARNING] Erreur de fit pour {p}/{v}: {e}")
            mean[p][v] = 0
            mean_err[p][v] = 0
            sigma[p][v] = 0
            sigma_err[p][v] = 0
    
    c_hist.Print(f"{fname}]")
    root_fname.Close()
    del c_hist  # Nettoyer explicitement

# ============================================================================
# PLOTS COMBINÉS: RÉSOLUTION vs MOMENTUM
# ============================================================================

print("[INFO] Création des plots combinés (vs momentum)...")

# Texte pour les labels
latex_left = ROOT.TLatex()
latex_left.SetTextFont(42)
latex_left.SetTextSize(0.03)
text_left_x, text_left_y = 0.15, 0.86

outfile_p = ROOT.TFile(f"{outputDir}/p_dist.root", "recreate")
c_p = ROOT.TCanvas("canvas_momentum", "Plot vs momentum", CANVAS_WIDTH, CANVAS_HEIGHT)
c_p.SetLeftMargin(PLOT_MARGIN_LEFT)
c_p.SetBottomMargin(PLOT_MARGIN_BOTTOM)

p_dist = {}
p_dist_t = {}
fname = f"{outputDir}/p_dist.pdf"
c_p.Print(f"{fname}[")

legend = {}
for v in VAR_LIST:
    legend[v] = ROOT.TLegend(0.62, 0.62, 0.82, 0.82)
    legend[v].SetBorderSize(0)
    legend[v].SetFillStyle(0)
    legend[v].SetTextFont(62)
    
    p_dist[v] = ROOT.TMultiGraph()
    p_dist_t[v] = {}
    marker_idx = 0
    color_idx = 0
    
    for t in STACK_THETA_LIST:
        # Vérifier que tous les points existent pour cet angle
        y_vals = []
        y_errs = []
        x_vals = []
        
        for momentum in MOMENTUM_LIST:
            proc = pname("mu", t, momentum)
            if proc in sigma and v in sigma[proc] and sigma[proc][v] != 0:
                y_vals.append(sigma[proc][v])
                y_errs.append(sigma_err[proc][v])
                x_vals.append(float(momentum))
        
        if len(x_vals) < 2:
            print(f"  [WARNING] Pas assez de points pour theta={t}° / {v}")
            continue
        
        y = ROOT.std.vector["double"](y_vals)
        x = ROOT.std.vector["double"](x_vals)
        err_y = ROOT.std.vector["double"](y_errs)
        err_x = ROOT.std.vector["double"]([0] * len(x_vals))
        
        p_dist_t[v][t] = ROOT.TGraphErrors(len(x_vals), x.data(), y.data(), err_x.data(), err_y.data())
        p_dist_t[v][t].SetMarkerStyle(MARKER_STYLES[marker_idx % len(MARKER_STYLES)])
        p_dist_t[v][t].SetMarkerColor(COLORS[color_idx % len(COLORS)])
        p_dist_t[v][t].Scale(UNIT_SCALE[v])
        p_dist[v].Add(p_dist_t[v][t])
        legend[v].AddEntry(p_dist_t[v][t], f"#theta = {t} deg", "p")
        
        marker_idx += 1
        color_idx += 1
    
    if p_dist[v].GetListOfGraphs() is None or p_dist[v].GetListOfGraphs().GetSize() == 0:
        print(f"  [WARNING] Aucune donnée pour {v}")
        continue
    
    p_dist[v].SetTitle(f";p [GeV];{AXIS_TITLES[v]}")
    
    c_p.SetLogx()
    c_p.SetLogy()
    c_p.SetRightMargin(0.15)
    c_p.SetTopMargin(0.15)
    
    pad = c_p.GetPad(0)
    pad.SetTickx(1)
    pad.SetTicky(1)
    
    p_dist[v].Draw("APE")
    p_dist[v].GetXaxis().SetTitleSize(0.06)
    p_dist[v].GetYaxis().SetTitleSize(0.06)
    
    latex_left.DrawLatexNDC(text_left_x, text_left_y, "FCC-ee CLD")
    legend[v].Draw()
    c_p.Print(fname)
    c_p.Write(f"Canvas_{v}")

c_p.Print(f"{fname}]")
outfile_p.Close()

# Nettoyer le canvas pour éviter les conflits
del c_p

# ============================================================================
# PLOTS COMBINÉS: RÉSOLUTION vs THETA
# ============================================================================

print("[INFO] Création des plots combinés (vs theta)...")

outfile_t = ROOT.TFile(f"{outputDir}/t_dist.root", "recreate")
c_t = ROOT.TCanvas("canvas_theta", "Plot vs theta", CANVAS_WIDTH, CANVAS_HEIGHT)
c_t.SetLeftMargin(PLOT_MARGIN_LEFT)
c_t.SetBottomMargin(PLOT_MARGIN_BOTTOM)

t_dist = {}
t_dist_p = {}
fname = f"{outputDir}/t_dist.pdf"
c_t.Print(f"{fname}[")

legend = {}
for v in VAR_LIST:
    legend[v] = ROOT.TLegend(0.62, 0.62, 0.82, 0.82)
    legend[v].SetBorderSize(0)
    legend[v].SetFillStyle(0)
    legend[v].SetTextFont(62)
    
    t_dist[v] = ROOT.TMultiGraph()
    t_dist_p[v] = {}
    marker_idx = 0
    color_idx = 0
    
    for momentum in STACK_MOMENTUM_LIST:
        # Vérifier que tous les points existent pour cette impulsion
        y_vals = []
        y_errs = []
        x_vals = []
        
        for t in THETA_LIST:
            proc = pname("mu", t, momentum)
            if proc in sigma and v in sigma[proc] and sigma[proc][v] != 0:
                y_vals.append(sigma[proc][v])
                y_errs.append(sigma_err[proc][v])
                x_vals.append(float(t))
        
        if len(x_vals) < 2:
            print(f"  [WARNING] Pas assez de points pour p={momentum}GeV / {v}")
            continue
        
        y = ROOT.std.vector["double"](y_vals)
        x = ROOT.std.vector["double"](x_vals)
        err_y = ROOT.std.vector["double"](y_errs)
        err_x = ROOT.std.vector["double"]([0] * len(x_vals))
        
        t_dist_p[v][momentum] = ROOT.TGraphErrors(len(x_vals), x.data(), y.data(), err_x.data(), err_y.data())
        t_dist_p[v][momentum].SetMarkerStyle(MARKER_STYLES[marker_idx % len(MARKER_STYLES)])
        t_dist_p[v][momentum].SetMarkerColor(COLORS[color_idx % len(COLORS)])
        t_dist_p[v][momentum].Scale(UNIT_SCALE[v])
        t_dist[v].Add(t_dist_p[v][momentum])
        legend[v].AddEntry(t_dist_p[v][momentum], f"p = {momentum} GeV", "p")
        
        marker_idx += 1
        color_idx += 1
    
    if t_dist[v].GetListOfGraphs() is None or t_dist[v].GetListOfGraphs().GetSize() == 0:
        print(f"  [WARNING] Aucune donnée pour {v}")
        continue
    
    t_dist[v].SetTitle(f";#theta [deg];{AXIS_TITLES[v]}")
    
    c_t.SetLogx(False)
    c_t.SetLogy()
    c_t.SetRightMargin(0.15)
    c_t.SetTopMargin(0.15)
    
    pad = c_t.GetPad(0)
    pad.SetTickx(1)
    pad.SetTicky(1)
    
    t_dist[v].Draw("AP")
    t_dist[v].GetXaxis().SetTitleSize(0.06)
    t_dist[v].GetYaxis().SetTitleSize(0.06)
    
    latex_left.DrawLatexNDC(text_left_x, text_left_y, "FCC-ee CLD")
    legend[v].Draw()
    c_t.Print(fname)
    c_t.Write(f"Canvas_{v}")

c_t.Print(f"{fname}]")
outfile_t.Close()

print("\n[INFO] Terminé!")
print(f"[INFO] Plots sauvegardés dans: {outputDir}")
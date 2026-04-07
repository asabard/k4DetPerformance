"""
SuperimposedCanvas pour FCC-ee.
Superpose des plots de différentes configurations (résolutions, modèles de détecteur, etc.)

Usage:
    python SuperimposedCanvas.py
"""
import ROOT
import os
import sys

ROOT.gROOT.SetBatch(True)

# ============================================================================
# COMPTEUR GLOBAL POUR NOMS UNIQUES (évite les segfaults ROOT)
# ============================================================================

_unique_counter = 0

def unique_name(base):
    """Génère un nom unique pour éviter les conflits ROOT."""
    global _unique_counter
    _unique_counter += 1
    return f"{base}_{_unique_counter}"


# ============================================================================
# IMPORT DE LA CONFIGURATION
# ============================================================================

try:
    from config_tracking import (
        DIGI_MODE, get_plots_output_dir, file_exists,
        CANVAS_NAMES, Y_AXIS_RANGE_THETA, Y_AXIS_RANGE_MOMENTUM, AXIS_TITLES
    )
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    
    CANVAS_NAMES = [
        "Canvas_delta_d0", "Canvas_delta_z0", "Canvas_delta_phi0", "Canvas_delta_omega",
        "Canvas_delta_tanLambda", "Canvas_delta_phi", "Canvas_delta_theta",
        "Canvas_sdelta_pt", "Canvas_sdelta_p"
    ]
    
    def file_exists(path):
        return os.path.isfile(path)


# ============================================================================
# FONCTIONS POUR LES TITRES ET RANGES D'AXES
# ============================================================================

def set_y_axis_title(canvas_name):
    """Retourne le titre de l'axe Y pour un canvas donné."""
    y_axis_titles = {
        "Canvas_delta_d0": "#sigma(#Deltad_{0}) [#mum]",
        "Canvas_delta_z0": "#sigma(#Deltaz_{0}) [#mum]",
        "Canvas_delta_phi0": "#Delta#phi_{0}",
        "Canvas_delta_omega": "#Delta#Omega",
        "Canvas_delta_tanLambda": "tan#Lambda",
        "Canvas_delta_phi": "#sigma(#Delta#phi) [mrad]",
        "Canvas_delta_theta": "#sigma(#Delta#theta) [mrad]",
        "Canvas_sdelta_pt": "#sigma(#Deltap_{T}/p_{T,true}^{2}) [GeV^{-1}]",
        "Canvas_sdelta_p": "#sigma(#Deltap/p_{true}^{2}) [GeV^{-1}]"
    }
    return y_axis_titles.get(canvas_name, "Y-axis")


def set_y_axis_range_theta(canvas_name):
    """Retourne le range de l'axe Y pour les plots en fonction de theta."""
    y_axis_range = {
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
    return y_axis_range.get(canvas_name, (1, 100))


def set_y_axis_range_momentum(canvas_name):
    """Retourne le range de l'axe Y pour les plots en fonction du momentum."""
    y_axis_range = {
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
    return y_axis_range.get(canvas_name, (1, 100))


# ============================================================================
# FONCTIONS DE COPIE SÉCURISÉE
# ============================================================================

def safe_copy_graph(graph, name_prefix="graph"):
    """
    Copie un TGraphErrors de manière sécurisée.
    Copie point par point pour éviter les dangling pointers après Close().
    """
    n_points = graph.GetN()
    new_graph = ROOT.TGraphErrors(n_points)
    new_graph.SetName(unique_name(name_prefix))
    new_graph.SetTitle("")  # Pas de titre "Graph"
    
    for j in range(n_points):
        new_graph.SetPoint(j, graph.GetX()[j], graph.GetY()[j])
        if graph.GetEX() and graph.GetEY():
            new_graph.SetPointError(j, graph.GetEX()[j], graph.GetEY()[j])
    
    # Copier le style
    new_graph.SetMarkerStyle(graph.GetMarkerStyle())
    new_graph.SetMarkerColor(graph.GetMarkerColor())
    new_graph.SetMarkerSize(graph.GetMarkerSize())
    new_graph.SetLineColor(graph.GetLineColor())
    new_graph.SetLineStyle(graph.GetLineStyle())
    
    # Empêcher Python de supprimer l'objet
    ROOT.SetOwnership(new_graph, False)
    
    return new_graph


def extract_legend_labels(input_file, canvas_name):
    """Extrait les labels de la légende du canvas original."""
    labels = []
    
    if not file_exists(input_file):
        return labels
    
    input_root_file = None
    try:
        input_root_file = ROOT.TFile.Open(input_file, "READ")
        if not input_root_file or input_root_file.IsZombie():
            return labels
        
        input_canvas = input_root_file.Get(canvas_name)
        if input_canvas and input_canvas.InheritsFrom("TCanvas"):
            for prim in input_canvas.GetListOfPrimitives():
                if prim.InheritsFrom("TLegend"):
                    for idx, entry in enumerate(prim.GetListOfPrimitives()):
                        if idx == 0:  # Skip header
                            continue
                        if hasattr(entry, 'GetLabel'):
                            labels.append(entry.GetLabel())
                    break
    except Exception as e:
        print(f"  [WARNING] Erreur extraction légende: {e}")
    finally:
        if input_root_file and input_root_file.IsOpen():
            input_root_file.Close()
    
    return labels


# ============================================================================
# FONCTION PRINCIPALE DE COMBINAISON
# ============================================================================

def combine_canvases(input_files, output_file, marker_styles_func, legend_text, 
                     log_x=False, log_y=False, verbose=True):
    """
    Combine plusieurs fichiers ROOT contenant des TMultiGraph en un seul plot.
    """
    
    # Filtrer les fichiers existants
    existing_files = []
    missing_files = []
    
    for f in input_files:
        if file_exists(f):
            existing_files.append(f)
        else:
            missing_files.append(f)
    
    if missing_files and verbose:
        print(f"[WARNING] {len(missing_files)} fichiers manquants:")
        for m in missing_files:
            print(f"  - {m}")
    
    if not existing_files:
        print("[ERROR] Aucun fichier d'entrée trouvé!")
        return
    
    if verbose:
        print(f"[INFO] {len(existing_files)} fichiers à traiter")
    
    # Mise à jour des legend_text pour correspondre aux fichiers existants
    file_to_legend = dict(zip(input_files, legend_text))
    filtered_legend_text = [file_to_legend[f] for f in existing_files]
    
    # Liste pour garder les objets en vie
    keep_alive = []
    
    output_root_file = ROOT.TFile(output_file + ".root", "recreate")
    output_pdf_file = output_file + ".pdf"
    
    # Premier canvas pour ouvrir le PDF
    first_canvas = ROOT.TCanvas(unique_name("first"), "First", 800, 650)
    first_canvas.Print(output_pdf_file + "[")

    for canvas_name in CANVAS_NAMES:
        # TMultiGraph avec nom UNIQUE et SANS TITRE
        superposed_multigraph = ROOT.TMultiGraph()
        superposed_multigraph.SetName(unique_name(f"mg_{canvas_name}"))
        superposed_multigraph.SetTitle("")  # IMPORTANT: pas de titre "Graph"
        
        # =====================================================================
        # LÉGENDE - en haut à droite, DANS le canvas (x2 <= 0.94)
        # =====================================================================
        output_legend = ROOT.TLegend(0.52, 0.60, 0.94, 0.91)
        output_legend.SetTextFont(42)
        output_legend.SetTextSize(0.028)
        output_legend.SetFillStyle(0)
        output_legend.SetBorderSize(0)
        output_legend.SetMargin(0.20)
        keep_alive.append(output_legend)

        for input_file_idx, input_file in enumerate(existing_files):
            input_root_file = None
            try:
                input_root_file = ROOT.TFile.Open(input_file, "READ")
                if not input_root_file or input_root_file.IsZombie():
                    if verbose:
                        print(f"  [WARNING] Impossible d'ouvrir {input_file}")
                    continue
                
                input_canvas = input_root_file.Get(canvas_name)
                
                if not input_canvas or not input_canvas.InheritsFrom("TCanvas"):
                    continue

                primitives = input_canvas.GetListOfPrimitives()
                marker_styles, marker_colors = marker_styles_func(input_file_idx)
                
                for i in range(primitives.GetSize()):
                    obj = primitives.At(i)
                    if obj.InheritsFrom("TMultiGraph"):
                        original_graphs = obj.GetListOfGraphs()
                        
                        for j in range(original_graphs.GetSize()):
                            graph = original_graphs.At(j)
                            
                            # Copie sécurisée point par point
                            new_graph = safe_copy_graph(graph, f"graph_{canvas_name}_{input_file_idx}_{j}")
                            
                            # Appliquer le nouveau style
                            new_marker_style = marker_styles[j % len(marker_styles)]
                            new_marker_color = marker_colors[j % len(marker_colors)]
                            new_graph.SetMarkerStyle(new_marker_style)
                            new_graph.SetMarkerColor(new_marker_color)
                            new_graph.SetMarkerSize(1.0)  # Taille modérée
                            
                            superposed_multigraph.Add(new_graph)
                            keep_alive.append(new_graph)
                        
                        break

                # Récupérer les labels de la légende originale
                labels = extract_legend_labels(input_file, canvas_name)
                for idx, label in enumerate(labels):
                    if idx < len(marker_styles):
                        dummy = ROOT.TGraph(1)
                        dummy.SetName(unique_name("dummy_legend"))
                        dummy.SetMarkerStyle(marker_styles[idx])
                        dummy.SetMarkerColor(marker_colors[idx])
                        dummy.SetMarkerSize(1.0)
                        
                        legend_label = f"{label}{filtered_legend_text[input_file_idx]}"
                        output_legend.AddEntry(dummy, legend_label, "P")
                        keep_alive.append(dummy)

            except Exception as e:
                if verbose:
                    print(f"  [WARNING] Erreur pour {input_file}: {e}")
                    import traceback
                    traceback.print_exc()
            finally:
                if input_root_file and input_root_file.IsOpen():
                    input_root_file.Close()

        # =====================================================================
        # CANVAS - dimensions et marges harmonisées
        # =====================================================================
        output_canvas = ROOT.TCanvas(unique_name(canvas_name), canvas_name, 800, 650)

        # Marges pour voir tous les axes sans qu'ils soient coupés
        output_canvas.SetLeftMargin(0.14)
        output_canvas.SetRightMargin(0.04)
        output_canvas.SetTopMargin(0.06)
        output_canvas.SetBottomMargin(0.12)

        if log_x:
            output_canvas.SetLogx()
        if log_y:
            output_canvas.SetLogy()

        output_canvas.SetTickx(1)
        output_canvas.SetTicky(1)

        graphs_list = superposed_multigraph.GetListOfGraphs()
        if graphs_list and graphs_list.GetSize() > 0:
            superposed_multigraph.Draw("APE")
            
            # =================================================================
            # AXES - tailles harmonisées et lisibles
            # =================================================================
            if marker_styles_func.__name__ == "set_styles_and_colors_momentum":
                superposed_multigraph.GetXaxis().SetTitle("p [GeV]")
                y_axis_range = set_y_axis_range_momentum(canvas_name)
            else:
                superposed_multigraph.GetXaxis().SetTitle("#theta [deg]")
                y_axis_range = set_y_axis_range_theta(canvas_name)
            
            # Axe X
            superposed_multigraph.GetXaxis().SetTitleSize(0.050)
            superposed_multigraph.GetXaxis().SetTitleOffset(1.0)
            superposed_multigraph.GetXaxis().SetLabelSize(0.042)
            superposed_multigraph.GetXaxis().SetTitleFont(42)
            superposed_multigraph.GetXaxis().SetLabelFont(42)
            
            # Axe Y
            superposed_multigraph.GetYaxis().SetTitle(set_y_axis_title(canvas_name))
            superposed_multigraph.GetYaxis().SetTitleSize(0.050)
            superposed_multigraph.GetYaxis().SetTitleOffset(1.2)
            superposed_multigraph.GetYaxis().SetLabelSize(0.042)
            superposed_multigraph.GetYaxis().SetTitleFont(42)
            superposed_multigraph.GetYaxis().SetLabelFont(42)
            superposed_multigraph.GetYaxis().SetRangeUser(y_axis_range[0], y_axis_range[1])

        output_legend.Draw()

        # Texte en haut à gauche
        latex_left = ROOT.TLatex()
        latex_left.SetNDC()
        latex_left.SetTextFont(42)
        latex_left.SetTextSize(0.040)
        latex_left.DrawLatexNDC(0.15, 0.95, "FCC-ee CLD")

        output_canvas.Update()
        
        output_root_file.cd()
        output_canvas.Write()
        
        # Imprimer directement ce canvas dans le PDF
        output_canvas.Print(output_pdf_file, "pdf")
        
        keep_alive.append(superposed_multigraph)
        keep_alive.append(output_canvas)

    # Fermer le PDF
    first_canvas.Print(output_pdf_file + "]")
    output_root_file.Close()
    
    if verbose:
        print(f"[INFO] Sauvegardé: {output_file}.root et {output_file}.pdf")


# ============================================================================
# FONCTIONS DE STYLE
# ============================================================================

def set_styles_and_colors_momentum(input_file_idx):
    """Styles et couleurs pour les plots en fonction du momentum."""
    marker_styles_full = [ROOT.kFullTriangleUp, ROOT.kFullSquare, ROOT.kFullDiamond, 
                          ROOT.kFullCross, ROOT.kFullCircle]
    marker_styles_open = [ROOT.kOpenTriangleUp, ROOT.kOpenSquare, ROOT.kOpenDiamond, 
                          ROOT.kOpenCross, ROOT.kOpenCircle]
    colors1 = [ROOT.kBlue, ROOT.kRed, ROOT.kMagenta, ROOT.kGreen+2, ROOT.kBlack]
    colors2 = [ROOT.kCyan+1, ROOT.kOrange+1, ROOT.kMagenta+2, ROOT.kGreen+3, ROOT.kGray+1]

    style_map = {
        0: (marker_styles_full, colors1),
        1: (marker_styles_open, colors1),
        2: (marker_styles_full, colors2),
    }
    return style_map.get(input_file_idx, (marker_styles_full, colors1))


def set_styles_and_colors_theta(input_file_idx):
    """Styles et couleurs pour les plots en fonction de theta."""
    marker_styles_full = [ROOT.kFullCircle, ROOT.kFullSquare, ROOT.kFullTriangleUp]
    marker_styles_open = [ROOT.kOpenCircle, ROOT.kOpenSquare, ROOT.kOpenTriangleUp]
    colors1 = [ROOT.kBlack, ROOT.kRed, ROOT.kBlue]
    colors2 = [ROOT.kGray+1, ROOT.kMagenta, ROOT.kCyan+1]

    style_map = {
        0: (marker_styles_open, colors1),
        1: (marker_styles_full, colors1),
        2: (marker_styles_full, colors2),
    }
    return style_map.get(input_file_idx, (marker_styles_full, colors1))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    
    print("\n" + "=" * 70)
    print("SuperimposedCanvas - FCC-ee Tracking")
    print("=" * 70 + "\n")
    
    # Alias pour les fonctions de style
    momentum_styles = set_styles_and_colors_momentum
    theta_styles = set_styles_and_colors_theta
    
    # =========================================================================
    # EXEMPLE 1: Tracking performances vs Momentum
    # =========================================================================
    
    print("[INFO] Création des plots combinés vs momentum...")
    
    input_files = [
        '/eos/user/a/asabard/DigiPerformance/ANALYSIS/detailed/mu/plots/p_dist.root',
        '/eos/user/a/asabard/DigiPerformance/ANALYSIS/parametric/mu/plots/p_dist.root',
    ]
    output_file = "combined_canvas_momentum"
    legend_text = [", detailed digi", ", parametric digi"]
    
    combine_canvases(input_files, output_file, momentum_styles, legend_text, 
                     log_x=True, log_y=True)

    # =========================================================================
    # EXEMPLE 2: Tracking performances vs Theta
    # =========================================================================
    
    print("\n[INFO] Création des plots combinés vs theta...")
    
    input_files = [
        '/eos/user/a/asabard/DigiPerformance/ANALYSIS/detailed/mu/plots/t_dist.root',
        '/eos/user/a/asabard/DigiPerformance/ANALYSIS/parametric/mu/plots/t_dist.root',
    ]
    output_file = "combined_canvas_theta"
    legend_text = [", detailed digi", ", parametric digi"]
    
    combine_canvases(input_files, output_file, theta_styles, legend_text, 
                     log_x=False, log_y=True)
    
    print("\n[INFO] Terminé!")
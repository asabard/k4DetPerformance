"""
SuperimposedCanvas avec ratios pour FCC-ee.
Compare deux configurations avec plots de ratio.

Usage:
    python SuperimposedCanvas_ratio.py
"""
import ROOT
import os
import math
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
# FONCTIONS POUR LES TITRES ET RANGES D'AXES
# ============================================================================

def set_y_axis_title(canvas_name):
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
    y_axis_range = {
        "Canvas_delta_d0": (0.5, 10**4),
        "Canvas_delta_z0": (0.5, 10**4),
        "Canvas_delta_phi0": (0.15*(10**-4), 1),
        "Canvas_delta_omega": (0.15*(10**-7), 10**-2),
        "Canvas_delta_tanLambda": (0.15*(10**-4), 10),
        "Canvas_delta_phi": (0.15*(10**-1), 10**3),
        "Canvas_delta_theta": (0.15*(10**-1), 10**3),
        "Canvas_sdelta_pt": (0.15*(10**-4), 5),
        "Canvas_sdelta_p": (0.15*(10**-4), 5),
    }
    return y_axis_range.get(canvas_name, (1, 100))


def set_y_axis_range_momentum(canvas_name):
    y_axis_range = {
        "Canvas_delta_d0": (0.5, 10**3),
        "Canvas_delta_z0": (0.5, 10**4),
        "Canvas_delta_phi0": (0.15*(10**-4), 10**-1),
        "Canvas_delta_omega": (0.15*(10**-7), 10**-3),
        "Canvas_delta_tanLambda": (0.15*(10**-4), 10),
        "Canvas_delta_phi": (0.15*(10**-1), 10**2),
        "Canvas_delta_theta": (0.15*(10**-1), 10),
        "Canvas_sdelta_pt": (0.15*(10**-4), 10),
        "Canvas_sdelta_p": (0.15*(10**-4), 1),
    }
    return y_axis_range.get(canvas_name, (1, 100))


# ============================================================================
# FONCTIONS DE STYLE
# ============================================================================

def marker_styles_func(file_identifier, graph_type, canvas_style):
    """Retourne les styles et couleurs selon l'identifiant et le type de graphe."""
    if canvas_style == 'theta':
        styles = {
            '1': {'a': [ROOT.kOpenCircle], 'b': [ROOT.kFullCircle], 'color': ROOT.kBlack},
            '10': {'a': [ROOT.kOpenSquare], 'b': [ROOT.kFullSquare], 'color': ROOT.kRed},
            '100': {'a': [ROOT.kOpenTriangleUp], 'b': [ROOT.kFullTriangleUp], 'color': ROOT.kBlue},
        }
    elif canvas_style == 'momentum':
        styles = {
            '10': {'a': [ROOT.kOpenTriangleUp], 'b': [ROOT.kFullTriangleUp], 'color': ROOT.kBlue},
            '30': {'a': [ROOT.kOpenSquare], 'b': [ROOT.kFullSquare], 'color': ROOT.kRed},
            '50': {'a': [ROOT.kOpenDiamond], 'b': [ROOT.kFullDiamond], 'color': ROOT.kMagenta},
            '70': {'a': [ROOT.kOpenCross], 'b': [ROOT.kFullCross], 'color': ROOT.kGreen},
            '89': {'a': [ROOT.kOpenCircle], 'b': [ROOT.kFullCircle], 'color': ROOT.kBlack},
        }
    else:
        raise ValueError(f"Invalid canvas style: {canvas_style}")

    if file_identifier not in styles:
        raise ValueError(f"Unknown file identifier: {file_identifier}")

    selected_style = styles[file_identifier][graph_type]
    selected_color = styles[file_identifier]['color']

    return selected_style, [selected_color]


def extract_file_identifier(file_name, canvas_style):
    """Extrait l'identifiant (momentum ou theta) du nom de fichier."""
    if canvas_style == 'theta':
        if '1.root' in file_name and '10.root' not in file_name and '100.root' not in file_name:
            return '1'
        elif '10.root' in file_name and '100.root' not in file_name:
            return '10'
        elif '100.root' in file_name:
            return '100'
        else:
            raise ValueError(f"Unable to extract file identifier from {file_name}")
    elif canvas_style == 'momentum':
        if '10.root' in file_name:
            return '10'
        elif '30.root' in file_name:
            return '30'
        elif '50.root' in file_name:
            return '50'
        elif '70.root' in file_name:
            return '70'
        elif '89.root' in file_name:
            return '89'
        else:
            raise ValueError(f"Unable to extract file identifier from {file_name}")
    else:
        raise ValueError(f"Invalid canvas style: {canvas_style}")


# ============================================================================
# FONCTIONS DE TRAITEMENT SÉCURISÉES
# ============================================================================

def process_canvas(input_file, canvas_name, graph_type, file_identifier, canvas_style, keep_alive):
    """
    Extrait les graphes d'un canvas avec copie sécurisée des données.
    """
    new_graphs = []
    
    if not os.path.isfile(input_file):
        return new_graphs
    
    input_root_file = None
    try:
        input_root_file = ROOT.TFile.Open(input_file, "READ")
        if not input_root_file or input_root_file.IsZombie():
            return new_graphs
        
        input_canvas = input_root_file.Get(canvas_name)

        if input_canvas and input_canvas.InheritsFrom("TCanvas"):
            primitives = input_canvas.GetListOfPrimitives()
            for obj in primitives:
                if obj.InheritsFrom("TMultiGraph"):
                    multigraph = obj
                    for i, graph in enumerate(multigraph.GetListOfGraphs()):
                        selected_style, selected_color = marker_styles_func(
                            file_identifier, graph_type, canvas_style
                        )
                        new_marker_style = selected_style[i % len(selected_style)]
                        new_marker_color = selected_color[0]
                        
                        # Copie point par point
                        n_points = graph.GetN()
                        new_graph = ROOT.TGraphErrors(n_points)
                        new_graph.SetName(unique_name(f"graph_{graph_type}_{file_identifier}"))
                        new_graph.SetTitle("")  # PAS DE TITRE
                        
                        for j in range(n_points):
                            new_graph.SetPoint(j, graph.GetX()[j], graph.GetY()[j])
                            new_graph.SetPointError(j, graph.GetEX()[j], graph.GetEY()[j])
                        
                        new_graph.SetMarkerStyle(new_marker_style)
                        new_graph.SetMarkerColor(new_marker_color)
                        new_graph.SetLineColor(new_marker_color)
                        
                        ROOT.SetOwnership(new_graph, False)
                        keep_alive.append(new_graph)
                        new_graphs.append(new_graph)
                    break
    except Exception as e:
        print(f"  [WARNING] Erreur lors du traitement de {input_file}: {e}")
    finally:
        if input_root_file and input_root_file.IsOpen():
            input_root_file.Close()
    
    return new_graphs


def extract_legend_labels(input_file, canvas_name):
    """Extrait les labels de la légende du canvas original."""
    labels = []
    
    if not os.path.isfile(input_file):
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


def add_entries_to_legend(output_legend, labels, styles, colors, additional_text, keep_alive):
    """Ajoute des entrées à la légende avec les labels originaux."""
    for idx, label in enumerate(labels):
        dummy = ROOT.TGraph(1)
        dummy.SetName(unique_name("dummy_legend"))
        dummy.SetMarkerStyle(styles[idx % len(styles)])
        dummy.SetMarkerColor(colors[idx % len(colors)])
        dummy.SetMarkerSize(1.2)
        
        legend_label = f"{label}{additional_text}"
        output_legend.AddEntry(dummy, legend_label, "P")
        
        ROOT.SetOwnership(dummy, False)
        keep_alive.append(dummy)


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def process_and_compare_graphs(output_file_path, canvas_names, folder_a, folder_b, 
                                file_names, canvas_style, legend_txt, top_left_txt):
    """Compare deux configurations et génère des plots avec ratios."""
    
    # Filtrer les fichiers existants
    existing_files = []
    for file_name in file_names:
        file_a = os.path.join(folder_a, file_name)
        file_b = os.path.join(folder_b, file_name)
        if os.path.isfile(file_a) and os.path.isfile(file_b):
            existing_files.append(file_name)
        else:
            if not os.path.isfile(file_a):
                print(f"  [WARNING] Fichier manquant: {file_a}")
            if not os.path.isfile(file_b):
                print(f"  [WARNING] Fichier manquant: {file_b}")
    
    if not existing_files:
        print(f"[ERROR] Aucune paire de fichiers trouvée!")
        return
    
    print(f"[INFO] {len(existing_files)}/{len(file_names)} paires de fichiers trouvées")
    
    # Fichier de sortie
    output_root_file = ROOT.TFile(output_file_path, "RECREATE")
    output_pdf_file = output_file_path[:-5] + ".pdf"
    
    # Canvas pour ouvrir/fermer le PDF
    pdf_opener = ROOT.TCanvas(unique_name("pdf_opener"), "PDF", 600, 700)
    pdf_opener.Print(output_pdf_file + "[")
    
    # Structures de données
    keep_alive = []
    
    for canvas_name in canvas_names:
        graphs_from_a = []
        graphs_from_b = []
        ratio_graphs_list = []
        legends_from_graphs = []
        
        # Limites Y pour le ratio (calcul dynamique)
        ratio_min = float('inf')
        ratio_max = -float('inf')
        
        for file_name in existing_files:
            file_path_a = os.path.join(folder_a, file_name)
            file_path_b = os.path.join(folder_b, file_name)
            
            try:
                file_identifier_a = extract_file_identifier(file_path_a, canvas_style)
                file_identifier_b = extract_file_identifier(file_path_b, canvas_style)
            except ValueError as e:
                print(f"  [WARNING] {e}")
                continue
            
            # Extraire les graphes
            graphs_a = process_canvas(file_path_a, canvas_name, 'a', file_identifier_a, canvas_style, keep_alive)
            graphs_b = process_canvas(file_path_b, canvas_name, 'b', file_identifier_b, canvas_style, keep_alive)
            
            if not graphs_a or not graphs_b:
                print(f"  [WARNING] Pas de graphes pour {canvas_name} dans {file_name}")
                continue
            
            graphs_from_a.extend(graphs_a)
            graphs_from_b.extend(graphs_b)
            
            # === CANVAS DE COMPARAISON INDIVIDUEL ===
            output_root_file.cd()
            comparison_canvas = ROOT.TCanvas(
                unique_name(f"{canvas_name}_{file_name[:-5]}"),
                f"{canvas_name}", 600, 700
            )
            
            # === PAD SUPÉRIEUR (70% de la hauteur) ===
            pad1 = ROOT.TPad(unique_name("pad1"), "pad1", 0, 0.35, 1, 1.0)
            pad1.SetBottomMargin(0.02)  # Petit espace entre les pads
            pad1.SetLeftMargin(0.14)
            pad1.SetRightMargin(0.04)
            pad1.SetTopMargin(0.08)
            pad1.SetTickx(1)
            pad1.SetTicky(1)
            pad1.Draw()
            pad1.cd()
            
            # Dessiner graphs_a
            first = True
            # Calculer le range Y automatique avec marge (pour dézoomer)
            y_min_data = float('inf')
            y_max_data = -float('inf')
            for graph in graphs_a + graphs_b:
                for i in range(graph.GetN()):
                    val = graph.GetY()[i]
                    err = graph.GetEY()[i] if graph.GetEY() else 0
                    if val > 0:
                        y_min_data = min(y_min_data, val - err)
                        y_max_data = max(y_max_data, val + err)
            
            # Ajouter 30% de marge en échelle log (facteur multiplicatif)
            if y_min_data != float('inf') and y_min_data > 0:
                log_range = math.log10(y_max_data) - math.log10(y_min_data)
                margin = 0.15 * log_range  # 15% de marge de chaque côté
                y_min_plot = 10 ** (math.log10(y_min_data) - margin)
                y_max_plot = 10 ** (math.log10(y_max_data) + margin)
            else:
                y_min_plot = None
                y_max_plot = None
            
            for i, graph in enumerate(graphs_a):
                graph.SetTitle("")
                graph.GetYaxis().SetTitle(set_y_axis_title(canvas_name))
                graph.GetYaxis().SetTitleSize(0.055)
                graph.GetYaxis().SetTitleOffset(1.15)
                graph.GetYaxis().SetLabelSize(0.045)
                graph.GetYaxis().SetTitleFont(42)
                graph.GetYaxis().SetLabelFont(42)
                if y_min_plot is not None:
                    graph.GetYaxis().SetRangeUser(y_min_plot, y_max_plot)
                graph.GetXaxis().SetLabelSize(0)  # Pas de labels X sur le top pad
                graph.GetXaxis().SetTickLength(0.03)
                graph.Draw("AP" if first else "P SAME")
                first = False
            
            # Dessiner graphs_b
            for graph in graphs_b:
                graph.SetTitle("")
                graph.Draw("P SAME")
            
            pad1.SetLogy()
            if canvas_style == "momentum":
                pad1.SetLogx()
            pad1.Update()
            
            # === PAD INFÉRIEUR (RATIO) - 35% de la hauteur ===
            comparison_canvas.cd()
            pad2 = ROOT.TPad(unique_name("pad2"), "pad2", 0, 0.0, 1, 0.35)
            pad2.SetTopMargin(0.02)
            pad2.SetBottomMargin(0.30)  # Grand espace pour l'axe X
            pad2.SetLeftMargin(0.14)
            pad2.SetRightMargin(0.04)
            pad2.SetTickx(1)
            pad2.SetTicky(1)
            if canvas_style == "momentum":
                pad2.SetLogx()
            pad2.Draw()
            pad2.cd()
            
            # Calculer et dessiner le ratio
            if graphs_a and graphs_b:
                n_points = graphs_a[0].GetN()
                y_ratio = ROOT.TGraphErrors(n_points)
                y_ratio.SetName(unique_name(f"ratio_{canvas_name}_{file_identifier_b}"))
                y_ratio.SetTitle("")  # PAS DE TITRE "Graph"
                
                for i in range(n_points):
                    xa = graphs_a[0].GetX()[i]
                    ya = graphs_a[0].GetY()[i]
                    yb = graphs_b[0].GetY()[i]
                    eya = graphs_a[0].GetEY()[i]
                    eyb = graphs_b[0].GetEY()[i]
                    
                    ratio = ya / yb if yb != 0 else 0
                    error = ratio * ((eya/ya)**2 + (eyb/yb)**2)**0.5 if ya != 0 and yb != 0 else 0
                    
                    y_ratio.SetPoint(i, xa, ratio)
                    y_ratio.SetPointError(i, 0, error)
                    
                    # Mettre à jour les limites
                    if ratio > 0:
                        ratio_min = min(ratio_min, ratio - error)
                        ratio_max = max(ratio_max, ratio + error)
                
                # Style du ratio
                marker_styles, marker_colors = marker_styles_func(file_identifier_b, 'b', canvas_style)
                y_ratio.SetMarkerStyle(marker_styles[0])
                y_ratio.SetMarkerColor(marker_colors[0])
                y_ratio.SetLineColor(marker_colors[0])
                
                # Configuration des axes du ratio pad
                y_ratio.GetXaxis().SetTitleSize(0.11)
                y_ratio.GetXaxis().SetTitleOffset(1.0)
                y_ratio.GetXaxis().SetLabelSize(0.09)
                y_ratio.GetXaxis().SetTickLength(0.05)
                y_ratio.GetXaxis().SetTitleFont(42)
                y_ratio.GetXaxis().SetLabelFont(42)
                
                y_ratio.GetYaxis().SetTitle("Ratio")
                y_ratio.GetYaxis().SetTitleSize(0.09)
                y_ratio.GetYaxis().SetTitleOffset(0.60)
                y_ratio.GetYaxis().SetLabelSize(0.08)
                y_ratio.GetYaxis().SetNdivisions(505)
                y_ratio.GetYaxis().SetTitleFont(42)
                y_ratio.GetYaxis().SetLabelFont(42)
                
                # Calculer le range Y local pour ce canvas (dézoomer)
                # ET s'assurer que y=1 est toujours visible
                local_min = float('inf')
                local_max = -float('inf')
                for i in range(y_ratio.GetN()):
                    val = y_ratio.GetY()[i]
                    err = y_ratio.GetEY()[i]
                    if val > 0:
                        local_min = min(local_min, val - err)
                        local_max = max(local_max, val + err)
                if local_min != float('inf'):
                    # Inclure y=1 dans le range
                    local_min = min(local_min, 1.0)
                    local_max = max(local_max, 1.0)
                    local_buffer = (local_max - local_min) * 0.30
                    y_ratio.GetYaxis().SetRangeUser(
                        max(0, local_min - local_buffer), 
                        local_max + local_buffer
                    )
                
                if canvas_style == "theta":
                    y_ratio.GetXaxis().SetTitle("#theta [deg]")
                else:
                    y_ratio.GetXaxis().SetTitle("p [GeV]")
                
                y_ratio.Draw("AP")
                
                ratio_graphs_list.append(y_ratio)
                ROOT.SetOwnership(y_ratio, False)
                keep_alive.append(y_ratio)
                
                # Ligne à y=1
                x_min = y_ratio.GetXaxis().GetXmin()
                x_max = y_ratio.GetXaxis().GetXmax()
                line = ROOT.TLine(x_min, 1, x_max, 1)
                line.SetLineColor(ROOT.kBlack)
                line.SetLineStyle(2)
                line.Draw("same")
                keep_alive.append(line)
                
                pad2.Update()
            
            # === LÉGENDE (en haut à droite du top pad) ===
            labels_a = extract_legend_labels(file_path_a, canvas_name)
            labels_b = extract_legend_labels(file_path_b, canvas_name)
            
            output_legend = ROOT.TLegend(0.52, 0.60, 0.94, 0.91)
            output_legend.SetTextFont(42)
            output_legend.SetTextSize(0.038)
            output_legend.SetFillStyle(0)
            output_legend.SetBorderSize(0)
            output_legend.SetMargin(0.20)
            output_legend.SetHeader("Single #mu^{-}")
            
            marker_styles_a, marker_colors_a = marker_styles_func(file_identifier_a, 'a', canvas_style)
            marker_styles_b, marker_colors_b = marker_styles_func(file_identifier_b, 'b', canvas_style)
            
            add_entries_to_legend(output_legend, labels_a, marker_styles_a, marker_colors_a, legend_txt[0], keep_alive)
            add_entries_to_legend(output_legend, labels_b, marker_styles_b, marker_colors_b, legend_txt[1], keep_alive)
            
            legends_from_graphs.append(output_legend)
            keep_alive.append(output_legend)
            
            pad1.cd()
            output_legend.Draw()
            
            # Texte en haut à gauche
            latex_left = ROOT.TLatex()
            latex_left.SetNDC()
            latex_left.SetTextFont(42)
            latex_left.SetTextSize(0.045)
            latex_left.DrawLatexNDC(0.15, 0.93, top_left_txt)
            
            # Sauvegarder
            output_root_file.cd()
            comparison_canvas.Write()
            comparison_canvas.Print(output_pdf_file, "pdf")
            
            keep_alive.append(comparison_canvas)
            keep_alive.append(pad1)
            keep_alive.append(pad2)
        
        # === CANVAS COMBINÉ pour tous les fichiers ===
        if graphs_from_a and graphs_from_b:
            combined_canvas = ROOT.TCanvas(
                unique_name(f"combined_{canvas_name}"), 
                f"combined_{canvas_name}", 600, 700
            )
            
            # Pad supérieur
            top_pad = ROOT.TPad(unique_name("top_pad"), "top_pad", 0.0, 0.35, 1.0, 1.0)
            top_pad.SetBottomMargin(0.02)
            top_pad.SetLeftMargin(0.14)
            top_pad.SetRightMargin(0.04)
            top_pad.SetTopMargin(0.08)
            top_pad.SetTickx(1)
            top_pad.SetTicky(1)
            top_pad.Draw()
            top_pad.cd()
            
            first_graph = True
            for graph in graphs_from_a + graphs_from_b:
                y_axis_range = set_y_axis_range_theta(canvas_name) if canvas_style == "theta" else set_y_axis_range_momentum(canvas_name)
                graph.SetTitle("")
                graph.GetYaxis().SetRangeUser(y_axis_range[0], y_axis_range[1])
                graph.GetYaxis().SetTitle(set_y_axis_title(canvas_name))
                graph.GetYaxis().SetTitleSize(0.055)
                graph.GetYaxis().SetTitleOffset(1.15)
                graph.GetYaxis().SetLabelSize(0.045)
                graph.GetYaxis().SetTitleFont(42)
                graph.GetYaxis().SetLabelFont(42)
                graph.GetXaxis().SetLabelSize(0)
                draw_option = "APE" if first_graph else "PE same"
                graph.Draw(draw_option)
                first_graph = False
            
            top_pad.SetLogy()
            if canvas_style == "momentum":
                top_pad.SetLogx()
            
            # Légende combinée (en haut à droite, plus à droite pour les angles multiples)
            combined_legend = ROOT.TLegend(0.58, 0.48, 0.96, 0.91)
            combined_legend.SetTextFont(42)
            combined_legend.SetTextSize(0.026)
            combined_legend.SetFillStyle(0)
            combined_legend.SetBorderSize(0)
            combined_legend.SetMargin(0.18)
            combined_legend.SetHeader("Single #mu^{-}")
            
            for legend in legends_from_graphs:
                for entry in legend.GetListOfPrimitives():
                    if isinstance(entry, ROOT.TLegendEntry) and entry.GetLabel() != "Single #mu^{-}":
                        obj = entry.GetObject()
                        if obj:
                            combined_legend.AddEntry(obj, entry.GetLabel(), entry.GetOption())
            
            top_pad.cd()
            combined_legend.Draw()
            keep_alive.append(combined_legend)
            top_pad.Update()
            
            # Pad inférieur (ratios)
            combined_canvas.cd()
            bottom_pad = ROOT.TPad(unique_name("bottom_pad"), "bottom_pad", 0, 0.0, 1, 0.35)
            bottom_pad.SetTopMargin(0.02)
            bottom_pad.SetBottomMargin(0.30)
            bottom_pad.SetLeftMargin(0.14)
            bottom_pad.SetRightMargin(0.04)
            bottom_pad.SetTickx(1)
            bottom_pad.SetTicky(1)
            if canvas_style == "momentum":
                bottom_pad.SetLogx()
            bottom_pad.Draw()
            bottom_pad.cd()
            
            # Calculer le range Y dynamique avec marge (dézoomer)
            # ET s'assurer que y=1 est toujours visible
            if ratio_min != float('inf') and ratio_max != -float('inf'):
                # Inclure y=1 dans le range
                ratio_min = min(ratio_min, 1.0)
                ratio_max = max(ratio_max, 1.0)
                buffer = (ratio_max - ratio_min) * 0.30
                y_min_adjusted = max(0, ratio_min - buffer)
                y_max_adjusted = ratio_max + buffer
            else:
                y_min_adjusted = 0.5
                y_max_adjusted = 1.5
            
            first_graph = True
            for y_ratio in ratio_graphs_list:
                y_ratio.SetTitle("")
                y_ratio.GetYaxis().SetRangeUser(y_min_adjusted, y_max_adjusted)
                y_ratio.GetYaxis().SetTitle("Ratio")
                y_ratio.GetYaxis().SetTitleSize(0.09)
                y_ratio.GetYaxis().SetTitleOffset(0.60)
                y_ratio.GetYaxis().SetLabelSize(0.08)
                y_ratio.GetYaxis().SetNdivisions(505)
                y_ratio.GetYaxis().SetTitleFont(42)
                y_ratio.GetYaxis().SetLabelFont(42)
                y_ratio.GetXaxis().SetTitleSize(0.11)
                y_ratio.GetXaxis().SetTitleOffset(1.0)
                y_ratio.GetXaxis().SetLabelSize(0.09)
                y_ratio.GetXaxis().SetTickLength(0.05)
                y_ratio.GetXaxis().SetTitleFont(42)
                y_ratio.GetXaxis().SetLabelFont(42)
                
                if canvas_style == "theta":
                    y_ratio.GetXaxis().SetTitle("#theta [deg]")
                else:
                    y_ratio.GetXaxis().SetTitle("p [GeV]")
                
                draw_option = "APE" if first_graph else "PE same"
                y_ratio.Draw(draw_option)
                first_graph = False
            
            if ratio_graphs_list:
                last_ratio = ratio_graphs_list[-1]
                x_min = last_ratio.GetXaxis().GetXmin()
                x_max = last_ratio.GetXaxis().GetXmax()
                line = ROOT.TLine(x_min, 1, x_max, 1)
                line.SetLineColor(ROOT.kBlack)
                line.SetLineStyle(2)
                line.Draw("same")
                keep_alive.append(line)
            
            bottom_pad.Update()
            
            # Texte
            top_pad.cd()
            latex_left = ROOT.TLatex()
            latex_left.SetNDC()
            latex_left.SetTextFont(42)
            latex_left.SetTextSize(0.045)
            latex_left.DrawLatexNDC(0.15, 0.93, top_left_txt)
            
            output_root_file.cd()
            combined_canvas.Write()
            combined_canvas.Print(output_pdf_file, "pdf")
            
            keep_alive.append(combined_canvas)
            keep_alive.append(top_pad)
            keep_alive.append(bottom_pad)
    
    # Fermer le PDF
    pdf_opener.Print(output_pdf_file + "]")
    output_root_file.Close()
    
    print(f"[INFO] Sauvegardé: {output_file_path}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    
    print("\n" + "=" * 70)
    print("SuperimposedCanvas Ratio - FCC-ee Tracking")
    print("=" * 70 + "\n")
    
    # Configuration des dossiers
    folder_a = "/eos/user/a/asabard/DigiPerformance/ANALYSIS/detailed/mu/plots/"
    folder_b = "/eos/user/a/asabard/DigiPerformance/ANALYSIS/parametric/mu/plots/"
    
    legend_txt = [", detailed digi", ", param. (3 #mum)"]
    top_left_txt = "FCC-ee CLD"
    
    canvas_names = [
        "Canvas_delta_d0", "Canvas_delta_z0", "Canvas_delta_phi0", "Canvas_delta_omega",
        "Canvas_delta_tanLambda", "Canvas_delta_phi", "Canvas_delta_theta",
        "Canvas_sdelta_pt", "Canvas_sdelta_p"
    ]
    
    # =========================================================================
    # Comparaison en fonction de Theta
    # =========================================================================
    
    print("[INFO] Création des plots de ratio vs theta...")
    
    output_file_path = './ratio_theta.root'
    file_names = ['t_dist_1.root', 't_dist_10.root', 't_dist_100.root']
    
    process_and_compare_graphs(output_file_path, canvas_names, folder_a, folder_b, 
                               file_names, 'theta', legend_txt, top_left_txt)

    # =========================================================================
    # Comparaison en fonction du Momentum
    # =========================================================================
    
    print("\n[INFO] Création des plots de ratio vs momentum...")
    
    output_file_path = './ratio_momentum.root'
    file_names = ['p_dist_10.root', 'p_dist_30.root', 'p_dist_50.root', 'p_dist_70.root']
    
    process_and_compare_graphs(output_file_path, canvas_names, folder_a, folder_b, 
                               file_names, 'momentum', legend_txt, top_left_txt)
    
    print("\n[INFO] Terminé!")
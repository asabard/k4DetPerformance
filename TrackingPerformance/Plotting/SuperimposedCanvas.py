"""
SuperimposedCanvas pour FCC-ee.
Superpose des plots de différentes configurations (digi, détecteurs, etc.)

CHANGEMENTS vs version précédente :
- Chemins basés sur EOSBASE (qui inclut DETECTOR_MODEL)
- Titre du plot inclut DETECTOR_MODEL

Usage:
    python SuperimposedCanvas.py                      # CLD_o2_v07 par défaut
    DETECTOR_MODEL=CLD_o2_v05 python SuperimposedCanvas.py
"""
import ROOT
import os
import sys

ROOT.gROOT.SetBatch(True)

_unique_counter = 0
def unique_name(base):
    global _unique_counter
    _unique_counter += 1
    return f"{base}_{_unique_counter}"


try:
    from config_tracking import (
        DIGI_MODE, DETECTOR_MODEL, EOSBASE,
        get_plots_output_dir, file_exists,
        CANVAS_NAMES, Y_AXIS_RANGE_THETA, Y_AXIS_RANGE_MOMENTUM, AXIS_TITLES,
        X_AXIS_MODE, get_x_label,
    )
    CONFIG_LOADED = True
except ImportError:
    print("[ERROR] config_tracking.py introuvable")
    sys.exit(1)


# ============================================================================
# AXES
# ============================================================================

def set_y_axis_title(canvas_name):
    titles = {
        "Canvas_delta_d0": "#sigma(#Deltad_{0}) [#mum]",
        "Canvas_delta_z0": "#sigma(#Deltaz_{0}) [#mum]",
        "Canvas_delta_phi0": "#Delta#phi_{0}",
        "Canvas_delta_omega": "#Delta#Omega",
        "Canvas_delta_tanLambda": "#Delta#tanLambda",
        "Canvas_delta_phi": "#sigma(#Delta#phi) [mrad]",
        "Canvas_delta_theta": "#sigma(#Delta#theta) [mrad]",
        "Canvas_sdelta_pt": "#sigma(#Deltap_{T}/p_{T,true}^{2}) [GeV^{-1}]",
        "Canvas_sdelta_p": "#sigma(#Deltap/p_{true}^{2}) [GeV^{-1}]",
    }
    return titles.get(canvas_name, "Y-axis")


def set_y_axis_range_theta(canvas_name):
    return Y_AXIS_RANGE_THETA.get(canvas_name, (1, 100))


def set_y_axis_range_momentum(canvas_name):
    return Y_AXIS_RANGE_MOMENTUM.get(canvas_name, (1, 100))


# ============================================================================
# COPIE SÉCURISÉE
# ============================================================================

def safe_copy_graph(graph, name_prefix="graph"):
    n = graph.GetN()
    new_graph = ROOT.TGraphErrors(n)
    new_graph.SetName(unique_name(name_prefix))
    new_graph.SetTitle("")
    for j in range(n):
        new_graph.SetPoint(j, graph.GetX()[j], graph.GetY()[j])
        if graph.GetEX() and graph.GetEY():
            new_graph.SetPointError(j, graph.GetEX()[j], graph.GetEY()[j])
    new_graph.SetMarkerStyle(graph.GetMarkerStyle())
    new_graph.SetMarkerColor(graph.GetMarkerColor())
    new_graph.SetMarkerSize(graph.GetMarkerSize())
    new_graph.SetLineColor(graph.GetLineColor())
    new_graph.SetLineStyle(graph.GetLineStyle())
    ROOT.SetOwnership(new_graph, False)
    return new_graph


def extract_legend_labels(input_file, canvas_name):
    labels = []
    if not file_exists(input_file):
        return labels
    f = None
    try:
        f = ROOT.TFile.Open(input_file, "READ")
        if not f or f.IsZombie():
            return labels
        cv = f.Get(canvas_name)
        if cv and cv.InheritsFrom("TCanvas"):
            for prim in cv.GetListOfPrimitives():
                if prim.InheritsFrom("TLegend"):
                    for idx, entry in enumerate(prim.GetListOfPrimitives()):
                        if idx == 0:
                            continue
                        if hasattr(entry, 'GetLabel'):
                            labels.append(entry.GetLabel())
                    break
    except Exception as e:
        print(f"  [WARNING] Legend: {e}")
    finally:
        if f and f.IsOpen():
            f.Close()
    return labels


# ============================================================================
# COMBINAISON DE CANVAS
# ============================================================================

def combine_canvases(input_files, output_file, marker_styles_func, legend_text,
                     log_x=False, log_y=False, verbose=True,
                     top_left_txt=None):
    
    if top_left_txt is None:
        top_left_txt = f"FCC-ee {DETECTOR_MODEL}"
    
    existing_files = [f for f in input_files if file_exists(f)]
    missing_files = [f for f in input_files if not file_exists(f)]
    
    if missing_files and verbose:
        print(f"[WARNING] {len(missing_files)} fichiers manquants:")
        for m in missing_files:
            print(f"  - {m}")
    
    if not existing_files:
        print("[ERROR] Aucun fichier d'entrée trouvé!")
        return
    
    if verbose:
        print(f"[INFO] {len(existing_files)} fichiers à traiter")
    
    file_to_legend = dict(zip(input_files, legend_text))
    filtered_legend_text = [file_to_legend[f] for f in existing_files]
    
    keep_alive = []
    output_root = ROOT.TFile(output_file + ".root", "recreate")
    output_pdf = output_file + ".pdf"
    
    first_canvas = ROOT.TCanvas(unique_name("first"), "First", 800, 650)
    first_canvas.Print(output_pdf + "[")
    
    for canvas_name in CANVAS_NAMES:
        mg = ROOT.TMultiGraph()
        mg.SetName(unique_name(f"mg_{canvas_name}"))
        mg.SetTitle("")
        
        legend = ROOT.TLegend(0.52, 0.60, 0.94, 0.91)
        legend.SetTextFont(42); legend.SetTextSize(0.028)
        legend.SetFillStyle(0); legend.SetBorderSize(0); legend.SetMargin(0.20)
        keep_alive.append(legend)
        
        for idx_f, input_file in enumerate(existing_files):
            in_root = None
            try:
                in_root = ROOT.TFile.Open(input_file, "READ")
                if not in_root or in_root.IsZombie():
                    continue
                cv = in_root.Get(canvas_name)
                if not cv or not cv.InheritsFrom("TCanvas"):
                    continue
                
                styles, colors = marker_styles_func(idx_f)
                
                for obj in cv.GetListOfPrimitives():
                    if obj.InheritsFrom("TMultiGraph"):
                        for j, g in enumerate(obj.GetListOfGraphs()):
                            ng = safe_copy_graph(g, f"g_{canvas_name}_{idx_f}_{j}")
                            ng.SetMarkerStyle(styles[j % len(styles)])
                            ng.SetMarkerColor(colors[j % len(colors)])
                            ng.SetMarkerSize(1.0)
                            mg.Add(ng)
                            keep_alive.append(ng)
                        break
                
                labels = extract_legend_labels(input_file, canvas_name)
                for li, lab in enumerate(labels):
                    if li < len(styles):
                        dummy = ROOT.TGraph(1)
                        dummy.SetName(unique_name("dummy"))
                        dummy.SetMarkerStyle(styles[li])
                        dummy.SetMarkerColor(colors[li])
                        dummy.SetMarkerSize(1.0)
                        legend.AddEntry(dummy, f"{lab}{filtered_legend_text[idx_f]}", "P")
                        keep_alive.append(dummy)
            except Exception as e:
                if verbose:
                    print(f"  [WARNING] {input_file}: {e}")
            finally:
                if in_root and in_root.IsOpen():
                    in_root.Close()
        
        out_cv = ROOT.TCanvas(unique_name(canvas_name), canvas_name, 800, 650)
        out_cv.SetLeftMargin(0.14); out_cv.SetRightMargin(0.04)
        out_cv.SetTopMargin(0.06); out_cv.SetBottomMargin(0.12)
        if log_x:
            out_cv.SetLogx()
        if log_y:
            out_cv.SetLogy()
        out_cv.SetTickx(1); out_cv.SetTicky(1)
        
        if mg.GetListOfGraphs() and mg.GetListOfGraphs().GetSize() > 0:
            mg.Draw("APE")
            if marker_styles_func.__name__ == "set_styles_and_colors_momentum":
                mg.GetXaxis().SetTitle(get_x_label())
                y_range = set_y_axis_range_momentum(canvas_name)
            else:
                mg.GetXaxis().SetTitle("#theta [deg]")
                y_range = set_y_axis_range_theta(canvas_name)
            
            mg.GetXaxis().SetTitleSize(0.050)
            mg.GetXaxis().SetTitleOffset(1.0)
            mg.GetXaxis().SetLabelSize(0.042)
            mg.GetXaxis().SetTitleFont(42); mg.GetXaxis().SetLabelFont(42)
            
            mg.GetYaxis().SetTitle(set_y_axis_title(canvas_name))
            mg.GetYaxis().SetTitleSize(0.050)
            mg.GetYaxis().SetTitleOffset(1.2)
            mg.GetYaxis().SetLabelSize(0.042)
            mg.GetYaxis().SetTitleFont(42); mg.GetYaxis().SetLabelFont(42)
            mg.GetYaxis().SetRangeUser(y_range[0], y_range[1])
        
        legend.Draw()
        
        latex = ROOT.TLatex()
        latex.SetNDC(); latex.SetTextFont(42); latex.SetTextSize(0.040)
        latex.DrawLatexNDC(0.15, 0.95, top_left_txt)
        
        out_cv.Update()
        output_root.cd()
        out_cv.Write()
        out_cv.Print(output_pdf, "pdf")
        
        keep_alive.append(mg)
        keep_alive.append(out_cv)
    
    first_canvas.Print(output_pdf + "]")
    output_root.Close()
    
    if verbose:
        print(f"[INFO] Sauvegardé: {output_file}.root et {output_file}.pdf")


# ============================================================================
# STYLES
# ============================================================================

def set_styles_and_colors_momentum(idx):
    full = [ROOT.kFullTriangleUp, ROOT.kFullSquare, ROOT.kFullDiamond,
            ROOT.kFullCross, ROOT.kFullCircle]
    open_ = [ROOT.kOpenTriangleUp, ROOT.kOpenSquare, ROOT.kOpenDiamond,
             ROOT.kOpenCross, ROOT.kOpenCircle]
    c1 = [ROOT.kBlue, ROOT.kRed, ROOT.kMagenta, ROOT.kGreen+2, ROOT.kBlack]
    c2 = [ROOT.kCyan+1, ROOT.kOrange+1, ROOT.kMagenta+2, ROOT.kGreen+3, ROOT.kGray+1]
    return {0: (full, c1), 1: (open_, c1), 2: (full, c2)}.get(idx, (full, c1))


def set_styles_and_colors_theta(idx):
    full = [ROOT.kFullCircle, ROOT.kFullSquare, ROOT.kFullTriangleUp]
    open_ = [ROOT.kOpenCircle, ROOT.kOpenSquare, ROOT.kOpenTriangleUp]
    c1 = [ROOT.kBlack, ROOT.kRed, ROOT.kBlue]
    c2 = [ROOT.kGray+1, ROOT.kMagenta, ROOT.kCyan+1]
    return {0: (open_, c1), 1: (full, c1), 2: (full, c2)}.get(idx, (full, c1))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(f"SuperimposedCanvas — FCC-ee {DETECTOR_MODEL}")
    print("=" * 70 + "\n")
    
    plots_subdir = "plots_pt" if X_AXIS_MODE == "pt" else "plots"
    suffix_out = "_pt" if X_AXIS_MODE == "pt" else ""
    
    # Les chemins utilisent EOSBASE (qui contient DETECTOR_MODEL)
    base_detailed = f"{EOSBASE}/ANALYSIS/detailed/mu/{plots_subdir}"
    base_param = f"{EOSBASE}/ANALYSIS/parametric/mu/{plots_subdir}"
    
    # --- Plots vs momentum ---
    print("[INFO] Plots combinés vs momentum...")
    input_files = [
        f"{base_detailed}/p_dist.root",
        f"{base_param}/p_dist.root",
    ]
    output_file = f"combined_canvas_momentum{suffix_out}_{DETECTOR_MODEL}"
    legend_text = [", detailed digi", ", parametric digi"]
    combine_canvases(input_files, output_file,
                     set_styles_and_colors_momentum, legend_text,
                     log_x=True, log_y=True)
    
    # --- Plots vs theta ---
    print("\n[INFO] Plots combinés vs theta...")
    input_files = [
        f"{base_detailed}/t_dist.root",
        f"{base_param}/t_dist.root",
    ]
    output_file = f"combined_canvas_theta{suffix_out}_{DETECTOR_MODEL}"
    combine_canvases(input_files, output_file,
                     set_styles_and_colors_theta, legend_text,
                     log_x=False, log_y=True)
    
    print("\n[INFO] Terminé !")
"""
SuperimposedCanvas avec ratios pour FCC-ee.

CHANGEMENTS vs version précédente :
- Chemins basés sur EOSBASE (qui inclut DETECTOR_MODEL)
- Titre inclut DETECTOR_MODEL
- Boucle sur PARTICLE_LIST : un PDF/ROOT par particule (mu, e, pi)
- legend_header paramétrable (plus de "Single #mu^{-}" hardcodé)

Usage:
    python SuperimposedCanvas_ratio.py
    DETECTOR_MODEL=CLD_o2_v05 python SuperimposedCanvas_ratio.py
    PARTICLE_LIST=mu python SuperimposedCanvas_ratio.py
"""
import ROOT
import os
import sys
import math
ROOT.gROOT.SetBatch(True)

try:
    from config_tracking import (
        DETECTOR_MODEL, EOSBASE, PARTICLE_LIST,
        X_AXIS_MODE, get_x_label,
        Y_AXIS_RANGE_THETA, Y_AXIS_RANGE_MOMENTUM,
    )
except ImportError:
    print("[ERROR] config_tracking.py introuvable")
    sys.exit(1)


# Symboles ROOT TLatex pour les particules
ROOT_SYMBOLS = {"mu": "#mu^{-}", "e": "e^{-}", "pi": "#pi^{-}"}


_unique_counter = 0
def unique_name(base):
    global _unique_counter
    _unique_counter += 1
    return f"{base}_{_unique_counter}"


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
        "Canvas_sdelta_p": "#sigma(#Deltap/p_{true}^{2}) [GeV^{-1}]"
    }
    return titles.get(canvas_name, "Y-axis")


def set_y_axis_range_theta(canvas_name):
    ranges = {
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
    return ranges.get(canvas_name, (1, 100))


def set_y_axis_range_momentum(canvas_name):
    ranges = {
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
    return ranges.get(canvas_name, (1, 100))


def marker_styles_func(file_identifier, graph_type, canvas_style):
    if canvas_style == 'theta':
        styles = {
            '1':   {'a': [ROOT.kOpenCircle],     'b': [ROOT.kFullCircle],     'color': ROOT.kBlack},
            '10':  {'a': [ROOT.kOpenSquare],     'b': [ROOT.kFullSquare],     'color': ROOT.kRed},
            '100': {'a': [ROOT.kOpenTriangleUp], 'b': [ROOT.kFullTriangleUp], 'color': ROOT.kBlue},
        }
    elif canvas_style == 'momentum':
        styles = {
            '10':  {'a': [ROOT.kOpenTriangleUp], 'b': [ROOT.kFullTriangleUp], 'color': ROOT.kBlue},
            '30':  {'a': [ROOT.kOpenSquare],     'b': [ROOT.kFullSquare],     'color': ROOT.kRed},
            '50':  {'a': [ROOT.kOpenDiamond],    'b': [ROOT.kFullDiamond],    'color': ROOT.kMagenta},
            '70':  {'a': [ROOT.kOpenCross],      'b': [ROOT.kFullCross],      'color': ROOT.kGreen},
            '89':  {'a': [ROOT.kOpenCircle],     'b': [ROOT.kFullCircle],     'color': ROOT.kBlack},
            '90':  {'a': [ROOT.kOpenStar],       'b': [ROOT.kFullStar],       'color': ROOT.kOrange},
        }
    else:
        raise ValueError(f"Invalid canvas_style: {canvas_style}")
    
    if file_identifier not in styles:
        raise ValueError(f"Unknown file_identifier: {file_identifier}")
    
    return styles[file_identifier][graph_type], [styles[file_identifier]['color']]


def extract_file_identifier(file_name, canvas_style):
    if canvas_style == 'theta':
        if '1.root' in file_name and '10.root' not in file_name and '100.root' not in file_name:
            return '1'
        elif '10.root' in file_name and '100.root' not in file_name:
            return '10'
        elif '100.root' in file_name:
            return '100'
        else:
            raise ValueError(f"Unable to extract from {file_name}")
    elif canvas_style == 'momentum':
        for val in ['10', '30', '50', '70', '89', '90']:
            if f'{val}.root' in file_name:
                return val
        raise ValueError(f"Unable to extract from {file_name}")
    else:
        raise ValueError(f"Invalid canvas_style: {canvas_style}")


def process_canvas(input_file, canvas_name, graph_type, file_identifier,
                   canvas_style, keep_alive):
    new_graphs = []
    if not os.path.isfile(input_file):
        return new_graphs
    
    in_root = None
    try:
        in_root = ROOT.TFile.Open(input_file, "READ")
        if not in_root or in_root.IsZombie():
            return new_graphs
        cv = in_root.Get(canvas_name)
        if cv and cv.InheritsFrom("TCanvas"):
            for obj in cv.GetListOfPrimitives():
                if obj.InheritsFrom("TMultiGraph"):
                    for i, g in enumerate(obj.GetListOfGraphs()):
                        sstyle, scol = marker_styles_func(file_identifier, graph_type, canvas_style)
                        n = g.GetN()
                        ng = ROOT.TGraphErrors(n)
                        ng.SetName(unique_name(f"graph_{graph_type}_{file_identifier}"))
                        ng.SetTitle("")
                        for j in range(n):
                            ng.SetPoint(j, g.GetX()[j], g.GetY()[j])
                            ng.SetPointError(j, g.GetEX()[j], g.GetEY()[j])
                        ng.SetMarkerStyle(sstyle[i % len(sstyle)])
                        ng.SetMarkerColor(scol[0])
                        ng.SetLineColor(scol[0])
                        ROOT.SetOwnership(ng, False)
                        keep_alive.append(ng)
                        new_graphs.append(ng)
                    break
    except Exception as e:
        print(f"  [WARNING] {input_file}: {e}")
    finally:
        if in_root and in_root.IsOpen():
            in_root.Close()
    return new_graphs


def extract_legend_labels(input_file, canvas_name):
    labels = []
    if not os.path.isfile(input_file):
        return labels
    in_root = None
    try:
        in_root = ROOT.TFile.Open(input_file, "READ")
        if not in_root or in_root.IsZombie():
            return labels
        cv = in_root.Get(canvas_name)
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
        print(f"  [WARNING] legend: {e}")
    finally:
        if in_root and in_root.IsOpen():
            in_root.Close()
    return labels


def add_entries_to_legend(legend, labels, styles, colors, additional_text, keep_alive):
    for idx, label in enumerate(labels):
        dummy = ROOT.TGraph(1)
        dummy.SetName(unique_name("dummy"))
        dummy.SetMarkerStyle(styles[idx % len(styles)])
        dummy.SetMarkerColor(colors[idx % len(colors)])
        dummy.SetMarkerSize(1.2)
        legend.AddEntry(dummy, f"{label}{additional_text}", "P")
        ROOT.SetOwnership(dummy, False)
        keep_alive.append(dummy)


def process_and_compare_graphs(output_file_path, canvas_names, folder_a, folder_b,
                                file_names, canvas_style, legend_txt, top_left_txt,
                                legend_header="Single #mu^{-}"):
    
    existing = []
    for fn in file_names:
        a = os.path.join(folder_a, fn)
        b = os.path.join(folder_b, fn)
        if os.path.isfile(a) and os.path.isfile(b):
            existing.append(fn)
        else:
            if not os.path.isfile(a):
                print(f"  [WARNING] Manquant: {a}")
            if not os.path.isfile(b):
                print(f"  [WARNING] Manquant: {b}")
    
    if not existing:
        print("[ERROR] Aucune paire de fichiers")
        return
    
    print(f"[INFO] {len(existing)}/{len(file_names)} paires trouvées")
    
    output_root = ROOT.TFile(output_file_path, "RECREATE")
    output_pdf = output_file_path[:-5] + ".pdf"
    
    opener = ROOT.TCanvas(unique_name("opener"), "PDF", 600, 700)
    opener.Print(output_pdf + "[")
    
    keep_alive = []
    
    for canvas_name in canvas_names:
        graphs_a_all, graphs_b_all, ratio_list, legs = [], [], [], []
        ratio_min, ratio_max = float('inf'), -float('inf')
        
        for fn in existing:
            fpa, fpb = os.path.join(folder_a, fn), os.path.join(folder_b, fn)
            try:
                id_a = extract_file_identifier(fpa, canvas_style)
                id_b = extract_file_identifier(fpb, canvas_style)
            except ValueError as e:
                print(f"  [WARNING] {e}")
                continue
            
            ga = process_canvas(fpa, canvas_name, 'a', id_a, canvas_style, keep_alive)
            gb = process_canvas(fpb, canvas_name, 'b', id_b, canvas_style, keep_alive)
            if not ga or not gb:
                continue
            
            graphs_a_all.extend(ga)
            graphs_b_all.extend(gb)
            
            # Canvas comparatif
            output_root.cd()
            cmp_cv = ROOT.TCanvas(unique_name(f"{canvas_name}_{fn[:-5]}"),
                                 f"{canvas_name}", 600, 700)
            
            pad1 = ROOT.TPad(unique_name("pad1"), "pad1", 0, 0.35, 1, 1.0)
            pad1.SetBottomMargin(0.02); pad1.SetLeftMargin(0.14)
            pad1.SetRightMargin(0.04); pad1.SetTopMargin(0.08)
            pad1.SetTickx(1); pad1.SetTicky(1)
            pad1.Draw(); pad1.cd()
            
            # Range Y
            y_min_d, y_max_d = float('inf'), -float('inf')
            for g in ga + gb:
                for i in range(g.GetN()):
                    v = g.GetY()[i]
                    e = g.GetEY()[i] if g.GetEY() else 0
                    if v > 0:
                        y_min_d = min(y_min_d, v - e)
                        y_max_d = max(y_max_d, v + e)
            
            if y_min_d != float('inf') and y_min_d > 0:
                lr = math.log10(y_max_d) - math.log10(y_min_d)
                margin = 0.15 * lr
                y_min_p = 10 ** (math.log10(y_min_d) - margin)
                y_max_p = 10 ** (math.log10(y_max_d) + margin)
            else:
                y_min_p = y_max_p = None
            
            first = True
            for g in ga:
                g.SetTitle("")
                g.GetYaxis().SetTitle(set_y_axis_title(canvas_name))
                g.GetYaxis().SetTitleSize(0.055); g.GetYaxis().SetTitleOffset(1.15)
                g.GetYaxis().SetLabelSize(0.045)
                g.GetYaxis().SetTitleFont(42); g.GetYaxis().SetLabelFont(42)
                if y_min_p is not None:
                    g.GetYaxis().SetRangeUser(y_min_p, y_max_p)
                g.GetXaxis().SetLabelSize(0)
                g.GetXaxis().SetTickLength(0.03)
                g.Draw("AP" if first else "P SAME")
                first = False
            for g in gb:
                g.SetTitle("")
                g.Draw("P SAME")
            
            pad1.SetLogy()
            if canvas_style == "momentum":
                pad1.SetLogx()
            pad1.Update()
            
            cmp_cv.cd()
            pad2 = ROOT.TPad(unique_name("pad2"), "pad2", 0, 0.0, 1, 0.35)
            pad2.SetTopMargin(0.02); pad2.SetBottomMargin(0.30)
            pad2.SetLeftMargin(0.14); pad2.SetRightMargin(0.04)
            pad2.SetTickx(1); pad2.SetTicky(1)
            if canvas_style == "momentum":
                pad2.SetLogx()
            pad2.Draw(); pad2.cd()
            
            if ga and gb:
                n = ga[0].GetN()
                y_ratio = ROOT.TGraphErrors(n)
                y_ratio.SetName(unique_name(f"ratio_{canvas_name}_{id_b}"))
                y_ratio.SetTitle("")
                
                for i in range(n):
                    xa, ya = ga[0].GetX()[i], ga[0].GetY()[i]
                    yb = gb[0].GetY()[i]
                    eya, eyb = ga[0].GetEY()[i], gb[0].GetEY()[i]
                    r = ya / yb if yb != 0 else 0
                    e = r * ((eya/ya)**2 + (eyb/yb)**2)**0.5 if ya != 0 and yb != 0 else 0
                    y_ratio.SetPoint(i, xa, r)
                    y_ratio.SetPointError(i, 0, e)
                    if r > 0:
                        ratio_min = min(ratio_min, r - e)
                        ratio_max = max(ratio_max, r + e)
                
                sstyle, scol = marker_styles_func(id_b, 'b', canvas_style)
                y_ratio.SetMarkerStyle(sstyle[0])
                y_ratio.SetMarkerColor(scol[0])
                y_ratio.SetLineColor(scol[0])
                
                y_ratio.GetXaxis().SetTitleSize(0.11)
                y_ratio.GetXaxis().SetTitleOffset(1.0)
                y_ratio.GetXaxis().SetLabelSize(0.09)
                y_ratio.GetXaxis().SetTickLength(0.05)
                y_ratio.GetXaxis().SetTitleFont(42); y_ratio.GetXaxis().SetLabelFont(42)
                
                y_ratio.GetYaxis().SetTitle("Ratio")
                y_ratio.GetYaxis().SetTitleSize(0.09)
                y_ratio.GetYaxis().SetTitleOffset(0.60)
                y_ratio.GetYaxis().SetLabelSize(0.08)
                y_ratio.GetYaxis().SetNdivisions(505)
                y_ratio.GetYaxis().SetTitleFont(42); y_ratio.GetYaxis().SetLabelFont(42)
                
                l_min, l_max = float('inf'), -float('inf')
                for i in range(y_ratio.GetN()):
                    v = y_ratio.GetY()[i]
                    e = y_ratio.GetEY()[i]
                    if v > 0:
                        l_min = min(l_min, v - e)
                        l_max = max(l_max, v + e)
                if l_min != float('inf'):
                    l_min = min(l_min, 1.0); l_max = max(l_max, 1.0)
                    buf = (l_max - l_min) * 0.30
                    y_ratio.GetYaxis().SetRangeUser(max(0, l_min - buf), l_max + buf)
                
                if canvas_style == "theta":
                    y_ratio.GetXaxis().SetTitle("#theta [deg]")
                else:
                    y_ratio.GetXaxis().SetTitle(get_x_label())
                
                y_ratio.Draw("AP")
                ratio_list.append(y_ratio)
                ROOT.SetOwnership(y_ratio, False)
                keep_alive.append(y_ratio)
                
                x_min = y_ratio.GetXaxis().GetXmin()
                x_max = y_ratio.GetXaxis().GetXmax()
                line = ROOT.TLine(x_min, 1, x_max, 1)
                line.SetLineColor(ROOT.kBlack); line.SetLineStyle(2)
                line.Draw("same")
                keep_alive.append(line)
                
                pad2.Update()
            
            labels_a = extract_legend_labels(fpa, canvas_name)
            labels_b = extract_legend_labels(fpb, canvas_name)
            
            leg = ROOT.TLegend(0.52, 0.60, 0.94, 0.91)
            leg.SetTextFont(42); leg.SetTextSize(0.038)
            leg.SetFillStyle(0); leg.SetBorderSize(0); leg.SetMargin(0.20)
            leg.SetHeader(legend_header)
            
            sa, ca = marker_styles_func(id_a, 'a', canvas_style)
            sb, cb = marker_styles_func(id_b, 'b', canvas_style)
            add_entries_to_legend(leg, labels_a, sa, ca, legend_txt[0], keep_alive)
            add_entries_to_legend(leg, labels_b, sb, cb, legend_txt[1], keep_alive)
            
            legs.append(leg)
            keep_alive.append(leg)
            pad1.cd(); leg.Draw()
            
            latex = ROOT.TLatex()
            latex.SetNDC(); latex.SetTextFont(42); latex.SetTextSize(0.045)
            latex.DrawLatexNDC(0.15, 0.93, top_left_txt)
            
            output_root.cd()
            cmp_cv.Write()
            cmp_cv.Print(output_pdf, "pdf")
            
            keep_alive.extend([cmp_cv, pad1, pad2])
        
        # Canvas combiné pour toutes les valeurs
        if graphs_a_all and graphs_b_all:
            comb_cv = ROOT.TCanvas(unique_name(f"combined_{canvas_name}"),
                                   f"combined_{canvas_name}", 600, 700)
            top = ROOT.TPad(unique_name("top"), "top", 0.0, 0.35, 1.0, 1.0)
            top.SetBottomMargin(0.02); top.SetLeftMargin(0.14)
            top.SetRightMargin(0.04); top.SetTopMargin(0.08)
            top.SetTickx(1); top.SetTicky(1)
            top.Draw(); top.cd()
            
            first = True
            for g in graphs_a_all + graphs_b_all:
                y_range = (set_y_axis_range_theta(canvas_name) if canvas_style == "theta"
                           else set_y_axis_range_momentum(canvas_name))
                g.SetTitle("")
                g.GetYaxis().SetRangeUser(y_range[0], y_range[1])
                g.GetYaxis().SetTitle(set_y_axis_title(canvas_name))
                g.GetYaxis().SetTitleSize(0.055); g.GetYaxis().SetTitleOffset(1.15)
                g.GetYaxis().SetLabelSize(0.045)
                g.GetYaxis().SetTitleFont(42); g.GetYaxis().SetLabelFont(42)
                g.GetXaxis().SetLabelSize(0)
                g.Draw("APE" if first else "PE same")
                first = False
            
            top.SetLogy()
            if canvas_style == "momentum":
                top.SetLogx()
            
            comb_leg = ROOT.TLegend(0.58, 0.48, 0.96, 0.91)
            comb_leg.SetTextFont(42); comb_leg.SetTextSize(0.026)
            comb_leg.SetFillStyle(0); comb_leg.SetBorderSize(0); comb_leg.SetMargin(0.18)
            comb_leg.SetHeader(legend_header)
            
            for leg in legs:
                for entry in leg.GetListOfPrimitives():
                    if isinstance(entry, ROOT.TLegendEntry) and entry.GetLabel() != legend_header:
                        obj = entry.GetObject()
                        if obj:
                            comb_leg.AddEntry(obj, entry.GetLabel(), entry.GetOption())
            
            top.cd(); comb_leg.Draw()
            keep_alive.append(comb_leg)
            top.Update()
            
            comb_cv.cd()
            bot = ROOT.TPad(unique_name("bot"), "bot", 0, 0.0, 1, 0.35)
            bot.SetTopMargin(0.02); bot.SetBottomMargin(0.30)
            bot.SetLeftMargin(0.14); bot.SetRightMargin(0.04)
            bot.SetTickx(1); bot.SetTicky(1)
            if canvas_style == "momentum":
                bot.SetLogx()
            bot.Draw(); bot.cd()
            
            if ratio_min != float('inf') and ratio_max != -float('inf'):
                ratio_min = min(ratio_min, 1.0); ratio_max = max(ratio_max, 1.0)
                buf = (ratio_max - ratio_min) * 0.30
                y_min_adj = max(0, ratio_min - buf)
                y_max_adj = ratio_max + buf
            else:
                y_min_adj, y_max_adj = 0.5, 1.5
            
            first = True
            for yr in ratio_list:
                yr.SetTitle("")
                yr.GetYaxis().SetRangeUser(y_min_adj, y_max_adj)
                yr.GetYaxis().SetTitle("Ratio")
                yr.GetYaxis().SetTitleSize(0.09); yr.GetYaxis().SetTitleOffset(0.60)
                yr.GetYaxis().SetLabelSize(0.08); yr.GetYaxis().SetNdivisions(505)
                yr.GetYaxis().SetTitleFont(42); yr.GetYaxis().SetLabelFont(42)
                yr.GetXaxis().SetTitleSize(0.11); yr.GetXaxis().SetTitleOffset(1.0)
                yr.GetXaxis().SetLabelSize(0.09); yr.GetXaxis().SetTickLength(0.05)
                yr.GetXaxis().SetTitleFont(42); yr.GetXaxis().SetLabelFont(42)
                if canvas_style == "theta":
                    yr.GetXaxis().SetTitle("#theta [deg]")
                else:
                    yr.GetXaxis().SetTitle(get_x_label())
                yr.Draw("APE" if first else "PE same")
                first = False
            
            if ratio_list:
                last = ratio_list[-1]
                x_min = last.GetXaxis().GetXmin()
                x_max = last.GetXaxis().GetXmax()
                line = ROOT.TLine(x_min, 1, x_max, 1)
                line.SetLineColor(ROOT.kBlack); line.SetLineStyle(2)
                line.Draw("same")
                keep_alive.append(line)
            
            bot.Update()
            
            top.cd()
            latex = ROOT.TLatex()
            latex.SetNDC(); latex.SetTextFont(42); latex.SetTextSize(0.045)
            latex.DrawLatexNDC(0.15, 0.93, top_left_txt)
            
            output_root.cd()
            comb_cv.Write()
            comb_cv.Print(output_pdf, "pdf")
            
            keep_alive.extend([comb_cv, top, bot])
    
    opener.Print(output_pdf + "]")
    output_root.Close()
    
    print(f"[INFO] Sauvegardé: {output_file_path}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(f"SuperimposedCanvas Ratio — FCC-ee {DETECTOR_MODEL}")
    print(f"Particules : {PARTICLE_LIST}")
    print("=" * 70 + "\n")
    
    plots_subdir = "plots_pt" if X_AXIS_MODE == "pt" else "plots"
    suffix_out = "_pt" if X_AXIS_MODE == "pt" else ""
    
    legend_txt = [", detailed digi", ", param. (res 3 #mum)"]
    
    canvas_names = [
        "Canvas_delta_d0", "Canvas_delta_z0", "Canvas_delta_phi0", "Canvas_delta_omega",
        "Canvas_delta_tanLambda", "Canvas_delta_phi", "Canvas_delta_theta",
        "Canvas_sdelta_pt", "Canvas_sdelta_p"
    ]
    
    for particle in PARTICLE_LIST:
        p_sym = ROOT_SYMBOLS.get(particle, particle)
        
        print("\n" + "#" * 70)
        print(f"### Particule : {particle}  ({p_sym})")
        print("#" * 70)
        
        folder_a = f"{EOSBASE}/ANALYSIS/detailed/{particle}/{plots_subdir}/"
        folder_b = f"{EOSBASE}/ANALYSIS/parametric/{particle}/{plots_subdir}/"
        top_left_txt = f"FCC-ee {DETECTOR_MODEL}"
        legend_header = f"Single {p_sym}"
        
        print(f"\n[INFO] [{particle}] Ratio vs theta...")
        output_file_path = f'./ratio_theta{suffix_out}_{DETECTOR_MODEL}_{particle}.root'
        file_names = ['t_dist_1.root', 't_dist_10.root', 't_dist_100.root']
        process_and_compare_graphs(output_file_path, canvas_names, folder_a, folder_b,
                                   file_names, 'theta', legend_txt, top_left_txt,
                                   legend_header=legend_header)
        
        print(f"\n[INFO] [{particle}] Ratio vs momentum...")
        output_file_path = f'./ratio_momentum{suffix_out}_{DETECTOR_MODEL}_{particle}.root'
        file_names = ['p_dist_10.root', 'p_dist_30.root', 'p_dist_50.root',
                      'p_dist_70.root', 'p_dist_90.root']
        process_and_compare_graphs(output_file_path, canvas_names, folder_a, folder_b,
                                   file_names, 'momentum', legend_txt, top_left_txt,
                                   legend_header=legend_header)
        
        print(f"\n[INFO] [{particle}] Ratio vs theta à pT constant...")
        output_file_path = f'./ratio_theta_ptconst{suffix_out}_{DETECTOR_MODEL}_{particle}.root'
        file_names = ['t_dist_ptconst_1.root', 't_dist_ptconst_10.root', 't_dist_ptconst_100.root']
        process_and_compare_graphs(output_file_path, canvas_names, folder_a, folder_b,
                                   file_names, 'theta', legend_txt, top_left_txt,
                                   legend_header=legend_header)
    
    print("\n[INFO] Terminé !")
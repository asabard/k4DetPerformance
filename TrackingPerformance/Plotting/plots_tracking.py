"""
Plots tracking (version combinée) pour FCC-ee.

CHANGEMENTS vs version précédente :
- Boucle sur toutes les particules de PARTICLE_LIST
- Crystal Ball pour e⁻ et π⁻ sur variables d'impulsion (comme _sep.py)
- Fix init CB (sigma = RMS), SetParLimits
- σ_eff en parallèle, accessible via suffix "_eff" dans les fichiers de sortie
- DETECTOR_MODEL propagé correctement dans les chemins

Usage:
    DIGI_MODE=detailed python plots_tracking.py
    DETECTOR_MODEL=CLD_o2_v05 python plots_tracking.py
"""
import ROOT
import numpy as np
import os
import sys
import math as _math

# ============================================================================
# IMPORT CONFIG
# ============================================================================

try:
    from config_tracking import (
        DIGI_MODE, NEVTS, DETECTOR_MODEL, EOSBASE,
        PARTICLE_LIST, THETA_LIST, MOMENTUM_LIST,
        STACK_MOMENTUM_LIST, STACK_THETA_LIST,
        get_analysis_output_dir, get_plots_output_dir,
        ensure_dir, pname,
        VAR_LIST, RESIDUAL_LIST, SPECIAL_LIST, AXIS_TITLES, UNIT_SCALE,
        MARKER_STYLES, COLORS, CANVAS_WIDTH, CANVAS_HEIGHT,
        PLOT_MARGIN_LEFT, PLOT_MARGIN_BOTTOM,
        file_exists, X_AXIS_MODE, get_x_value, get_x_label,
        should_use_crystalball, SIGMA_EFF_FRACTION,
    )
    print(f"[INFO] DETECTOR_MODEL = {DETECTOR_MODEL}, DIGI_MODE = {DIGI_MODE}")
except ImportError:
    print("[ERROR] config_tracking.py introuvable")
    sys.exit(1)

ROOT.gStyle.SetOptFit(1111)
ROOT.gROOT.SetBatch(True)

# ============================================================================
# σ_eff
# ============================================================================

def sigma_eff_68(data):
    data = np.sort(np.asarray(data, dtype=float))
    n = len(data)
    if n < 20:
        return 0.0, 0.0
    nk = int(round(SIGMA_EFF_FRACTION * n))
    if nk < 1 or nk >= n:
        return 0.0, 0.0
    widths = data[nk:] - data[:n - nk]
    sigma = float(np.min(widths)) / 2.0
    err = sigma / _math.sqrt(2.0 * n)
    return sigma, err


def filter_data_std(data, threshold=2.5, n_selections=3):
    filtered = list(data)
    for _ in range(n_selections):
        if len(filtered) < 3:
            break
        m = np.mean(filtered)
        s = np.std(filtered)
        if s == 0:
            break
        filtered = [d for d in filtered if abs(d - m) < threshold * s]
    return filtered


# ============================================================================
# FIT
# ============================================================================

def fit_histogram(h, particle, variable, var_low, var_high):
    """Même logique que plots_tracking_sep.py."""
    use_cb = should_use_crystalball(particle, variable)
    fit_type = "CB" if use_cb else "gauss"
    
    try:
        if use_cb:
            f = ROOT.TF1(
                f"f_{particle}_{variable}_{id(h)}",
                "ROOT::Math::crystalball_function(x, [0], [1], [2], [3])*[4]",
                var_low, var_high
            )
            rms = h.GetRMS()
            if rms <= 0:
                rms = (var_high - var_low) / 10.0
            f.SetParameters(1.5, 2.0, rms, 0.0, h.GetMaximum())
            f.SetParLimits(0, 0.1, 10.0)
            f.SetParLimits(1, 1.01, 30.0)
            f.SetParLimits(2, 1e-6 * rms, 100 * rms)
            f.SetParLimits(3, var_low, var_high)
        else:
            f = ROOT.TF1(f"f_{particle}_{variable}_{id(h)}", "gaus", var_low, var_high)
        
        h.Fit(f, "RQ")
        return {
            "sigma": f.GetParameter(2),
            "sigma_err": f.GetParError(2),
            "mean": f.GetParameter(3) if use_cb else f.GetParameter(1),
            "mean_err": f.GetParError(3) if use_cb else f.GetParError(1),
            "fit_type": fit_type,
            "fit_obj": f,
        }
    except Exception as e:
        print(f"    [WARNING] Fit failed {particle}/{variable}: {e}")
        return {"sigma": 0.0, "sigma_err": 0.0, "mean": 0.0, "mean_err": 0.0,
                "fit_type": fit_type, "fit_obj": None}


# ============================================================================
# TRAITEMENT D'UNE PARTICULE
# ============================================================================

def process_particle(particle):
    """Charge, filtre, fitte. Retourne dict de résultats ou None."""
    print(f"\n--- Particule: {particle} ---")
    input_dir = get_analysis_output_dir(particle)
    output_dir = get_plots_output_dir(particle)
    ensure_dir(output_dir)
    
    # Check fichiers
    available = {}
    for theta in THETA_LIST:
        for momentum in MOMENTUM_LIST:
            proc = pname(particle, theta, momentum)
            fp = os.path.join(input_dir, f"{proc}.root")
            if file_exists(fp):
                available[proc] = fp
    
    if not available:
        print(f"  [SKIP] Aucun fichier pour {particle}")
        return None
    
    print(f"  [INFO] {len(available)} fichiers à traiter")
    
    # Chargement
    df = {}
    var_col_rp = {}
    for p, fp in available.items():
        try:
            df[p] = ROOT.RDataFrame("events", fp)
            for v in SPECIAL_LIST:
                df[p] = df[p].Define(f"sdelta_{v}", f"delta_{v} / (true_{v} * true_{v})")
            var_col_rp[p] = {v: df[p].Take["double"](v) for v in VAR_LIST}
        except Exception as e:
            print(f"  [WARNING] {p}: {e}")
            if p in df:
                del df[p]
    
    # Histos + fits
    sigma = {}
    sigma_err = {}
    sigma_eff = {}
    sigma_eff_err = {}
    
    for p in df:
        sigma[p] = {}
        sigma_err[p] = {}
        sigma_eff[p] = {}
        sigma_eff_err[p] = {}
        
        fname = f"{output_dir}/{p}.pdf"
        root_fname = ROOT.TFile(f"{output_dir}/{p}.root", "RECREATE")
        c_hist = ROOT.TCanvas(f"c_{p}", f"Histos {p}", 800, 600)
        root_fname.cd()
        c_hist.Print(f"{fname}[")
        
        for v in VAR_LIST:
            try:
                data = sorted(var_col_rp[p][v].GetValue())
                filtered = filter_data_std(data, 2.5, 3)
                if len(filtered) < 10:
                    sigma[p][v] = 0; sigma_err[p][v] = 0
                    sigma_eff[p][v] = 0; sigma_eff_err[p][v] = 0
                    continue
                
                lo, hi = min(filtered), max(filtered)
                h = (df[p]
                     .Filter(f"{v} > {lo} && {v} < {hi}")
                     .Histo1D((v, f"{p};{AXIS_TITLES[v]}", 200, lo, hi), v)
                    ).GetPtr()  # force la matérialisation
                
                h.Scale(1.0, "width")
                fit = fit_histogram(h, particle, v, lo, hi)
                sigma[p][v] = fit["sigma"]
                sigma_err[p][v] = fit["sigma_err"]
                
                raw = list(var_col_rp[p][v].GetValue())
                s_eff, s_eff_err = sigma_eff_68(raw)
                sigma_eff[p][v] = s_eff
                sigma_eff_err[p][v] = s_eff_err
                
                h.Write(f"hist_{p}_{v}")
                h.Draw()
                c_hist.Print(fname)
            except Exception as e:
                print(f"    [WARNING] {p}/{v}: {e}")
                sigma[p][v] = 0; sigma_err[p][v] = 0
                sigma_eff[p][v] = 0; sigma_eff_err[p][v] = 0
        
        c_hist.Print(f"{fname}]")
        root_fname.Close()
        del c_hist
    
    return {
        "sigma": sigma, "sigma_err": sigma_err,
        "sigma_eff": sigma_eff, "sigma_eff_err": sigma_eff_err,
        "output_dir": output_dir,
    }


# ============================================================================
# PLOTS COMBINÉS (TMultiGraph) pour UNE particule
# ============================================================================

def make_combined_vs_momentum(particle, results, metric="sigma"):
    if results is None:
        return
    sigma = results[metric]
    sigma_err = results[f"{metric}_err"]
    output_dir = results["output_dir"]
    
    suffix = "" if metric == "sigma" else "_eff"
    
    outfile = ROOT.TFile(f"{output_dir}/p_dist{suffix}.root", "recreate")
    c = ROOT.TCanvas(f"canvas_momentum_{particle}{suffix}",
                    f"{particle} vs momentum {metric}",
                    CANVAS_WIDTH, CANVAS_HEIGHT)
    c.SetLeftMargin(PLOT_MARGIN_LEFT)
    c.SetBottomMargin(PLOT_MARGIN_BOTTOM)
    
    fname = f"{output_dir}/p_dist{suffix}.pdf"
    c.Print(f"{fname}[")
    
    latex_left = ROOT.TLatex()
    latex_left.SetTextFont(42); latex_left.SetTextSize(0.03)
    
    for v in VAR_LIST:
        mg = ROOT.TMultiGraph()
        leg = ROOT.TLegend(0.62, 0.55, 0.82, 0.82)
        leg.SetBorderSize(0); leg.SetFillStyle(0); leg.SetTextFont(62)
        symbols = {"mu": r"\mu", "pi": r"\pi", "e": r"e"}
        leg.SetHeader(f"Single {symbols.get(particle, particle)}^{{-}}")
        
        graphs_by_t = {}
        for i, t in enumerate(STACK_THETA_LIST):
            y_vals, y_errs, x_vals = [], [], []
            for m in MOMENTUM_LIST:
                proc = pname(particle, t, m)
                if proc in sigma and sigma[proc].get(v, 0) != 0:
                    y_vals.append(sigma[proc][v])
                    y_errs.append(sigma_err[proc][v])
                    x_vals.append(get_x_value(m, t))
            if len(x_vals) < 2:
                continue
            y = ROOT.std.vector["double"](y_vals)
            x = ROOT.std.vector["double"](x_vals)
            err_y = ROOT.std.vector["double"](y_errs)
            err_x = ROOT.std.vector["double"]([0]*len(x_vals))
            gr = ROOT.TGraphErrors(len(x_vals), x.data(), y.data(),
                                   err_x.data(), err_y.data())
            gr.SetMarkerStyle(MARKER_STYLES[i % len(MARKER_STYLES)])
            gr.SetMarkerColor(COLORS[i % len(COLORS)])
            gr.Scale(UNIT_SCALE[v])
            mg.Add(gr)
            leg.AddEntry(gr, f"#theta = {t} deg", "p")
            graphs_by_t[t] = gr
        
        if mg.GetListOfGraphs() is None or mg.GetListOfGraphs().GetSize() == 0:
            continue
        
        metric_label = "#sigma" if metric == "sigma" else "#sigma_{eff}"
        mg.SetTitle(f";{get_x_label()};{AXIS_TITLES[v]} [{metric_label}]")
        c.SetLogx(); c.SetLogy()
        c.SetRightMargin(0.15); c.SetTopMargin(0.15)
        c.GetPad(0).SetTickx(1); c.GetPad(0).SetTicky(1)
        mg.Draw("APE")
        mg.GetXaxis().SetTitleSize(0.06)
        mg.GetYaxis().SetTitleSize(0.06)
        latex_left.DrawLatexNDC(0.15, 0.86, f"FCC-ee {DETECTOR_MODEL}")
        leg.Draw()
        c.Print(fname)
        c.Write(f"Canvas_{v}")
    
    c.Print(f"{fname}]")
    outfile.Close()


def make_combined_vs_theta(particle, results, metric="sigma"):
    if results is None:
        return
    sigma = results[metric]
    sigma_err = results[f"{metric}_err"]
    output_dir = results["output_dir"]
    
    suffix = "" if metric == "sigma" else "_eff"
    
    outfile = ROOT.TFile(f"{output_dir}/t_dist{suffix}.root", "recreate")
    c = ROOT.TCanvas(f"canvas_theta_{particle}{suffix}",
                    f"{particle} vs theta {metric}",
                    CANVAS_WIDTH, CANVAS_HEIGHT)
    c.SetLeftMargin(PLOT_MARGIN_LEFT)
    c.SetBottomMargin(PLOT_MARGIN_BOTTOM)
    
    fname = f"{output_dir}/t_dist{suffix}.pdf"
    c.Print(f"{fname}[")
    
    latex_left = ROOT.TLatex()
    latex_left.SetTextFont(42); latex_left.SetTextSize(0.03)
    
    for v in VAR_LIST:
        mg = ROOT.TMultiGraph()
        leg = ROOT.TLegend(0.62, 0.62, 0.82, 0.82)
        leg.SetBorderSize(0); leg.SetFillStyle(0); leg.SetTextFont(62)
        symbols = {"mu": r"\mu", "pi": r"\pi", "e": r"e"}
        leg.SetHeader(f"Single {symbols.get(particle, particle)}^{{-}}")
        
        for i, m in enumerate(STACK_MOMENTUM_LIST):
            y_vals, y_errs, x_vals = [], [], []
            for t in THETA_LIST:
                proc = pname(particle, t, m)
                if proc in sigma and sigma[proc].get(v, 0) != 0:
                    y_vals.append(sigma[proc][v])
                    y_errs.append(sigma_err[proc][v])
                    x_vals.append(float(t))
            if len(x_vals) < 2:
                continue
            y = ROOT.std.vector["double"](y_vals)
            x = ROOT.std.vector["double"](x_vals)
            err_y = ROOT.std.vector["double"](y_errs)
            err_x = ROOT.std.vector["double"]([0]*len(x_vals))
            gr = ROOT.TGraphErrors(len(x_vals), x.data(), y.data(),
                                   err_x.data(), err_y.data())
            gr.SetMarkerStyle(MARKER_STYLES[i % len(MARKER_STYLES)])
            gr.SetMarkerColor(COLORS[i % len(COLORS)])
            gr.Scale(UNIT_SCALE[v])
            mg.Add(gr)
            leg.AddEntry(gr, f"p = {m} GeV", "p")
        
        if mg.GetListOfGraphs() is None or mg.GetListOfGraphs().GetSize() == 0:
            continue
        
        metric_label = "#sigma" if metric == "sigma" else "#sigma_{eff}"
        mg.SetTitle(f";#theta [deg];{AXIS_TITLES[v]} [{metric_label}]")
        c.SetLogx(False); c.SetLogy()
        c.SetRightMargin(0.15); c.SetTopMargin(0.15)
        c.GetPad(0).SetTickx(1); c.GetPad(0).SetTicky(1)
        mg.Draw("AP")
        mg.GetXaxis().SetTitleSize(0.06)
        mg.GetYaxis().SetTitleSize(0.06)
        latex_left.DrawLatexNDC(0.15, 0.86, f"FCC-ee {DETECTOR_MODEL}")
        leg.Draw()
        c.Print(fname)
        c.Write(f"Canvas_{v}")
    
    c.Print(f"{fname}]")
    outfile.Close()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(f"PLOTS TRACKING COMBINÉ — {DETECTOR_MODEL} / {DIGI_MODE}")
    print("=" * 70)
    
    for particle in PARTICLE_LIST:
        results = process_particle(particle)
        if results is not None:
            make_combined_vs_momentum(particle, results, metric="sigma")
            make_combined_vs_momentum(particle, results, metric="sigma_eff")
            make_combined_vs_theta(particle, results, metric="sigma")
            make_combined_vs_theta(particle, results, metric="sigma_eff")
    
    print("\n[INFO] Terminé !")
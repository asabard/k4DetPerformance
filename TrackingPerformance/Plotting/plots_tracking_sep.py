"""
Plots tracking (version séparée) pour FCC-ee.

CHANGEMENTS vs version précédente :
- Boucle sur toutes les particules de PARTICLE_LIST (plus que mu)
- Crystal Ball étendue : électrons ET pions sur variables d'impulsion
- Fix initialisation CB : σ_init = h.GetRMS() (pas |mean|)
- Ajout de SetParLimits pour stabiliser le fit
- Nouvelle métrique σ_eff 68% (model-free) en parallèle du fit
- Stockage de tail_ratio = σ_eff / σ_fit pour diagnostiquer les queues
- Export d'un fichier JSON récapitulatif par particule pour compare_particles.py

Usage:
    DIGI_MODE=detailed python plots_tracking_sep.py
    DIGI_MODE=parametric python plots_tracking_sep.py
    DETECTOR_MODEL=CLD_o2_v05 python plots_tracking_sep.py
"""
import ROOT
import numpy as np
import os
import sys
import json
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
        file_exists,
        X_AXIS_MODE, get_x_value, get_x_label,
        should_use_crystalball,
        SIGMA_EFF_FRACTION, TAIL_WARNING_THRESHOLD,
    )
    CONFIG_LOADED = True
    print("[INFO] Configuration chargée depuis config_tracking.py")
    print(f"[INFO] DETECTOR_MODEL = {DETECTOR_MODEL}")
    print(f"[INFO] PARTICLE_LIST  = {PARTICLE_LIST}")
except ImportError:
    print("[ERROR] config_tracking.py introuvable — ce script ne peut pas tourner sans")
    sys.exit(1)

# ============================================================================
# SETUP ROOT
# ============================================================================

ROOT.gStyle.SetOptFit(1111)
ROOT.gROOT.SetBatch(True)

plot_width = 0.09
plot_height = 0.09

# ============================================================================
# σ_eff : demi-largeur du plus petit intervalle contenant 68.27% des données
# ============================================================================

def sigma_eff_68(data, fraction=None):
    """
    Sigma effectif model-free.
    
    Retourne (sigma, err). err est approximé par σ/√(2n) (valable pour une
    distribution à peu près normale ; pour les queues fortes il faudrait
    un bootstrap mais c'est un ordre de grandeur raisonnable).
    """
    if fraction is None:
        fraction = SIGMA_EFF_FRACTION
    
    data = np.sort(np.asarray(data, dtype=float))
    n = len(data)
    if n < 20:
        return 0.0, 0.0
    
    nk = int(round(fraction * n))
    if nk < 1 or nk >= n:
        return 0.0, 0.0
    
    widths = data[nk:] - data[:n - nk]
    sigma = float(np.min(widths)) / 2.0
    err = sigma / _math.sqrt(2.0 * n)
    return sigma, err


def filter_data_std(data, threshold=2.5, n_selections=3):
    """Filtre itératif à ±threshold*sigma."""
    filtered_data = list(data)
    for _ in range(n_selections):
        if len(filtered_data) < 3:
            break
        m = np.mean(filtered_data)
        s = np.std(filtered_data)
        if s == 0:
            break
        filtered_data = [d for d in filtered_data if abs(d - m) < threshold * s]
    return filtered_data


# ============================================================================
# CHEMINS — on boucle sur les particules, donc plus de inputDir global
# ============================================================================

def get_input_output_dirs(particle):
    """Retourne (inputDir, outputDir) pour une particule."""
    in_dir = get_analysis_output_dir(particle)
    out_dir = get_plots_output_dir(particle)
    ensure_dir(out_dir)
    return in_dir, out_dir


# ============================================================================
# VÉRIFICATION DES FICHIERS
# ============================================================================

def check_process_files(particle, input_dir):
    """Vérifie quels fichiers existent pour une particule donnée."""
    available = {}
    missing = []
    
    for theta in THETA_LIST:
        for momentum in MOMENTUM_LIST:
            proc_name = pname(particle, theta, momentum)
            file_path = os.path.join(input_dir, f"{proc_name}.root")
            if file_exists(file_path):
                available[proc_name] = file_path
            else:
                missing.append((particle, theta, momentum))
    
    if missing:
        print(f"  [{particle}] {len(missing)} manquants / "
              f"{len(missing) + len(available)} total")
    
    return available


# ============================================================================
# FIT D'UN HISTOGRAMME (gauss ou Crystal Ball selon contexte)
# ============================================================================

def fit_histogram(h, particle, variable, var_low, var_high):
    """
    Fitte un histogramme avec la fonction appropriée.
    
    Returns:
        dict avec keys: sigma, sigma_err, mean, mean_err, fit_type, fit_quality
    """
    use_cb = should_use_crystalball(particle, variable)
    fit_type = "CB" if use_cb else "gauss"
    
    try:
        if use_cb:
            f = ROOT.TF1(
                f"f_{particle}_{variable}_{id(h)}",
                "ROOT::Math::crystalball_function(x, [0], [1], [2], [3])*[4]",
                var_low, var_high
            )
            # Init CORRIGÉE : σ = RMS (pas |mean|), α=1.5, n=2.0
            rms = h.GetRMS()
            if rms <= 0:
                rms = (var_high - var_low) / 10.0
            f.SetParameters(
                1.5,              # [0] alpha (transition seuil)
                2.0,              # [1] n (exposant queue)
                rms,              # [2] sigma (cœur gaussien)
                0.0,              # [3] mu (centre)
                h.GetMaximum(),   # [4] norm
            )
            # Contraintes pour éviter divergence
            f.SetParLimits(0, 0.1, 10.0)           # alpha > 0
            f.SetParLimits(1, 1.01, 30.0)          # n > 1 (normalisable)
            f.SetParLimits(2, 1e-6 * rms, 100 * rms)  # sigma borné
            f.SetParLimits(3, var_low, var_high)   # mu dans la plage
        else:
            f = ROOT.TF1(f"f_{particle}_{variable}_{id(h)}", "gaus", var_low, var_high)
        
        # "RQ" = range restreint, quiet. "S" ajouté pour avoir le résultat
        fit_result = h.Fit(f, "RQS")
        
        sigma_val = f.GetParameter(2)
        sigma_err = f.GetParError(2)
        mean_val = f.GetParameter(1) if not use_cb else f.GetParameter(3)
        mean_err = f.GetParError(1) if not use_cb else f.GetParError(3)
        
        # Qualité du fit
        fit_quality = "OK"
        if fit_result and fit_result.Get():
            if fit_result.Status() != 0:
                fit_quality = f"STATUS={fit_result.Status()}"
        
        return {
            "sigma": sigma_val,
            "sigma_err": sigma_err,
            "mean": mean_val,
            "mean_err": mean_err,
            "fit_type": fit_type,
            "fit_quality": fit_quality,
            "fit_obj": f,  # pour pouvoir dessiner
        }
    except Exception as e:
        print(f"    [WARNING] Fit failed for {particle}/{variable}: {e}")
        return {
            "sigma": 0.0, "sigma_err": 0.0,
            "mean": 0.0, "mean_err": 0.0,
            "fit_type": fit_type, "fit_quality": f"ERROR: {e}",
            "fit_obj": None,
        }


# ============================================================================
# TRAITEMENT D'UNE PARTICULE
# ============================================================================

def process_particle(particle):
    """
    Traitement complet pour une particule :
    - Chargement des RDataFrames
    - Création des histogrammes filtrés
    - Fits (gauss ou CB) + σ_eff en parallèle
    - Export des résultats (plots + JSON)
    
    Returns:
        dict contenant sigma, sigma_err, sigma_eff, sigma_eff_err,
        tail_ratio indexés par [proc_name][variable]
    """
    print(f"\n{'='*70}\n[INFO] Traitement de la particule: {particle}\n{'='*70}")
    
    input_dir, output_dir = get_input_output_dirs(particle)
    print(f"  Input:  {input_dir}")
    print(f"  Output: {output_dir}")
    
    available = check_process_files(particle, input_dir)
    if not available:
        print(f"  [SKIP] Aucun fichier pour {particle}")
        return None
    
    # --- Chargement RDataFrames ---
    df = {}
    var_col_rp = {}
    
    for p, fpath in available.items():
        try:
            df[p] = ROOT.RDataFrame("events", fpath)
            for v in SPECIAL_LIST:
                df[p] = df[p].Define(f"sdelta_{v}", f"delta_{v} / (true_{v} * true_{v})")
            var_col_rp[p] = {v: df[p].Take["double"](v) for v in VAR_LIST}
        except Exception as e:
            print(f"  [WARNING] Erreur chargement {p}: {e}")
            if p in df:
                del df[p]
    
    # --- Données filtrées + histos ---
    var_col, var_low, var_high, h = {}, {}, {}, {}
    for p in df:
        var_col[p], var_low[p], var_high[p], h[p] = {}, {}, {}, {}
        for v in VAR_LIST:
            try:
                data = sorted(var_col_rp[p][v].GetValue())
                filtered = filter_data_std(data, threshold=2.5, n_selections=3)
                if len(filtered) < 10:
                    continue
                var_col[p][v] = filtered
                var_low[p][v] = min(filtered)
                var_high[p][v] = max(filtered)
                h[p][v] = (df[p]
                    .Filter(f"{v} > {var_low[p][v]} && {v} < {var_high[p][v]}")
                    .Histo1D((v, f"{p};{AXIS_TITLES[v]}", 200,
                              var_low[p][v], var_high[p][v]), v))
            except Exception as e:
                print(f"  [WARNING] Histo {p}/{v}: {e}")
    
    # --- Fits + σ_eff ---
    print(f"  [INFO] Fits et extraction σ_eff...")
    results = {
        "sigma": {}, "sigma_err": {},
        "mean": {}, "mean_err": {},
        "sigma_eff": {}, "sigma_eff_err": {},
        "tail_ratio": {},
        "fit_type": {}, "fit_quality": {},
    }
    
    for p in df:
        for key in results:
            results[key][p] = {}
        
        fname_pdf = f"{output_dir}/{p}.pdf"
        root_fname = ROOT.TFile(f"{output_dir}/{p}.root", "RECREATE")
        
        c_hist = ROOT.TCanvas(f"c_{p}", f"Histograms {p}", 800, 600)
        root_fname.cd()
        c_hist.Print(f"{fname_pdf}[")
        
        for v in VAR_LIST:
            if v not in h[p]:
                # valeurs par défaut
                for key in ("sigma", "sigma_err", "mean", "mean_err",
                            "sigma_eff", "sigma_eff_err", "tail_ratio"):
                    results[key][p][v] = 0.0
                results["fit_type"][p][v] = "N/A"
                results["fit_quality"][p][v] = "NO_HISTO"
                continue
            
            # Normalisation par width (important pour la CB)
            h[p][v].Scale(1.0, "width")
            
            # Fit
            fit = fit_histogram(h[p][v], particle, v, var_low[p][v], var_high[p][v])
            results["sigma"][p][v] = fit["sigma"]
            results["sigma_err"][p][v] = fit["sigma_err"]
            results["mean"][p][v] = fit["mean"]
            results["mean_err"][p][v] = fit["mean_err"]
            results["fit_type"][p][v] = fit["fit_type"]
            results["fit_quality"][p][v] = fit["fit_quality"]
            
            # σ_eff sur les données NON clippées (pour capturer les queues)
            raw = list(var_col_rp[p][v].GetValue())
            s_eff, s_eff_err = sigma_eff_68(raw)
            results["sigma_eff"][p][v] = s_eff
            results["sigma_eff_err"][p][v] = s_eff_err
            
            # Ratio révélateur de queues
            if fit["sigma"] > 0:
                ratio = s_eff / fit["sigma"]
            else:
                ratio = 0.0
            results["tail_ratio"][p][v] = ratio
            
            # Warning si queue significative
            if ratio > TAIL_WARNING_THRESHOLD:
                print(f"    [TAIL] {p}/{v}: σ_eff/σ_{fit['fit_type']} = {ratio:.2f}")
            
            # Sauvegarde
            h[p][v].Write(f"hist_{p}_{v}")
            h[p][v].Draw()
            c_hist.Print(fname_pdf)
        
        c_hist.Print(f"{fname_pdf}]")
        root_fname.Close()
        del c_hist
    
    # --- Export JSON récapitulatif pour compare_particles.py ---
    summary = {
        "detector_model": DETECTOR_MODEL,
        "digi_mode": DIGI_MODE,
        "particle": particle,
        "nevts": NEVTS,
        "theta_list": THETA_LIST,
        "momentum_list": MOMENTUM_LIST,
        "var_list": VAR_LIST,
        "results": {},  # [proc_name][variable] -> {sigma, sigma_eff, ...}
    }
    for p in df:
        summary["results"][p] = {}
        for v in VAR_LIST:
            summary["results"][p][v] = {
                "sigma":         results["sigma"][p].get(v, 0.0),
                "sigma_err":     results["sigma_err"][p].get(v, 0.0),
                "sigma_eff":     results["sigma_eff"][p].get(v, 0.0),
                "sigma_eff_err": results["sigma_eff_err"][p].get(v, 0.0),
                "tail_ratio":    results["tail_ratio"][p].get(v, 0.0),
                "fit_type":      results["fit_type"][p].get(v, "N/A"),
                "fit_quality":   results["fit_quality"][p].get(v, "N/A"),
            }
    
    json_path = os.path.join(output_dir, "summary.json")
    with open(json_path, "w") as fjson:
        json.dump(summary, fjson, indent=2)
    print(f"  [INFO] Résumé JSON: {json_path}")
    
    results["_output_dir"] = output_dir
    return results


# ============================================================================
# PLOTS : pour une particule, σ vs p à θ fixé
# ============================================================================

def make_plots_vs_momentum(particle, results, metric="sigma"):
    """
    Plots de σ (ou σ_eff) en fonction de p, un fichier par angle θ.
    metric ∈ {"sigma", "sigma_eff"} pour choisir la métrique.
    """
    if results is None:
        return
    output_dir = results["_output_dir"]
    sigma = results[metric]
    sigma_err = results[f"{metric}_err"]
    
    suffix = "" if metric == "sigma" else "_eff"
    
    latex_left = ROOT.TLatex()
    latex_left.SetTextFont(42)
    latex_left.SetTextSize(0.03)
    
    for t in STACK_THETA_LIST:
        # Vérifier qu'il y a des données
        has_data = any(
            pname(particle, t, m) in sigma
            and any(sigma[pname(particle, t, m)].get(v, 0) != 0 for v in VAR_LIST)
            for m in MOMENTUM_LIST
        )
        if not has_data:
            continue
        
        outfile = ROOT.TFile(f"{output_dir}/p_dist{suffix}_{t}.root", "recreate")
        c = ROOT.TCanvas(f"canvas_{particle}_{t}{suffix}",
                        f"{particle} {t} deg {metric}",
                        CANVAS_WIDTH, CANVAS_HEIGHT)
        c.SetLeftMargin(PLOT_MARGIN_LEFT)
        c.SetBottomMargin(PLOT_MARGIN_BOTTOM)
        
        fname = f"{output_dir}/p_dist{suffix}_{t}.pdf"
        c.Print(f"{fname}[")
        
        for v in VAR_LIST:
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
            err_x = ROOT.std.vector["double"]([0] * len(x_vals))
            
            gr = ROOT.TGraphErrors(len(x_vals), x.data(), y.data(),
                                   err_x.data(), err_y.data())
            gr.SetMarkerStyle(MARKER_STYLES[0])
            gr.SetMarkerColor(COLORS[0])
            gr.Scale(UNIT_SCALE[v])
            
            mg = ROOT.TMultiGraph()
            mg.Add(gr)
            metric_label = "#sigma" if metric == "sigma" else "#sigma_{eff}"
            mg.SetTitle(f";{get_x_label()};{AXIS_TITLES[v]} [{metric_label}]")
            
            c.SetLogx()
            c.SetLogy()
            c.SetRightMargin(0.15)
            c.SetTopMargin(0.15)
            c.GetPad(0).SetTickx(1)
            c.GetPad(0).SetTicky(1)
            
            mg.Draw("APE")
            mg.GetXaxis().SetTitleSize(0.06)
            mg.GetYaxis().SetTitleSize(0.06)
            
            latex_left.DrawLatexNDC(0.15, 0.86, f"FCC-ee {DETECTOR_MODEL}")
            
            leg = ROOT.TLegend(0.62, 0.62, 0.82, 0.82)
            leg.SetBorderSize(0)
            leg.SetFillStyle(0)
            symbols = {"mu": r"\mu", "pi": r"\pi", "e": r"e"}
            leg.SetHeader(f"Single {symbols.get(particle, particle)}^{{-}} ({metric})")
            leg.AddEntry(gr, f"#theta = {t} deg", "p")
            leg.Draw()
            
            c.Print(fname)
            outfile.cd()
            c.Write(f"Canvas_{v}")
        
        c.Print(f"{fname}]")
        outfile.Close()


# ============================================================================
# PLOTS : pour une particule, σ vs θ à p fixé
# ============================================================================

def make_plots_vs_theta(particle, results, metric="sigma"):
    """Plots de σ vs θ, un fichier par impulsion p."""
    if results is None:
        return
    output_dir = results["_output_dir"]
    sigma = results[metric]
    sigma_err = results[f"{metric}_err"]
    
    suffix = "" if metric == "sigma" else "_eff"
    
    latex_left = ROOT.TLatex()
    latex_left.SetTextFont(42)
    latex_left.SetTextSize(0.03)
    
    for momentum in STACK_MOMENTUM_LIST:
        has_data = any(
            pname(particle, t, momentum) in sigma
            and any(sigma[pname(particle, t, momentum)].get(v, 0) != 0 for v in VAR_LIST)
            for t in THETA_LIST
        )
        if not has_data:
            continue
        
        outfile = ROOT.TFile(f"{output_dir}/t_dist{suffix}_{momentum}.root", "recreate")
        c = ROOT.TCanvas(f"canvas_{particle}_{momentum}{suffix}",
                        f"{particle} {momentum} GeV {metric}",
                        CANVAS_WIDTH, CANVAS_HEIGHT)
        c.SetLeftMargin(PLOT_MARGIN_LEFT)
        c.SetBottomMargin(PLOT_MARGIN_BOTTOM)
        
        fname = f"{output_dir}/t_dist{suffix}_{momentum}.pdf"
        c.Print(f"{fname}[")
        
        for v in VAR_LIST:
            y_vals, y_errs, x_vals = [], [], []
            for t in THETA_LIST:
                proc = pname(particle, t, momentum)
                if proc in sigma and sigma[proc].get(v, 0) != 0:
                    y_vals.append(sigma[proc][v])
                    y_errs.append(sigma_err[proc][v])
                    x_vals.append(float(t))
            
            if len(x_vals) < 2:
                continue
            
            y = ROOT.std.vector["double"](y_vals)
            x = ROOT.std.vector["double"](x_vals)
            err_y = ROOT.std.vector["double"](y_errs)
            err_x = ROOT.std.vector["double"]([0] * len(x_vals))
            
            gr = ROOT.TGraphErrors(len(x_vals), x.data(), y.data(),
                                   err_x.data(), err_y.data())
            gr.SetMarkerStyle(MARKER_STYLES[0])
            gr.SetMarkerColor(COLORS[0])
            gr.Scale(UNIT_SCALE[v])
            
            mg = ROOT.TMultiGraph()
            mg.Add(gr)
            metric_label = "#sigma" if metric == "sigma" else "#sigma_{eff}"
            mg.SetTitle(f";#theta [deg];{AXIS_TITLES[v]} [{metric_label}]")
            
            c.SetLogy()
            c.SetRightMargin(0.15)
            c.SetTopMargin(0.15)
            c.GetPad(0).SetTickx(1)
            c.GetPad(0).SetTicky(1)
            
            mg.Draw("AP")
            mg.GetXaxis().SetTitleSize(0.06)
            mg.GetYaxis().SetTitleSize(0.06)
            
            latex_left.DrawLatexNDC(0.15, 0.86, f"FCC-ee {DETECTOR_MODEL}")
            
            leg = ROOT.TLegend(0.62, 0.62, 0.82, 0.82)
            leg.SetBorderSize(0)
            leg.SetFillStyle(0)
            symbols = {"mu": r"\mu", "pi": r"\pi", "e": r"e"}
            leg.SetHeader(f"Single {symbols.get(particle, particle)}^{{-}} ({metric})")
            leg.AddEntry(gr, f"p = {momentum} GeV", "p")
            leg.Draw()
            
            c.Print(fname)
            outfile.cd()
            c.Write(f"Canvas_{v}")
        
        c.Print(f"{fname}]")
        outfile.Close()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(f"PLOTS TRACKING SEP — {DETECTOR_MODEL} / {DIGI_MODE}")
    print("=" * 70)
    
    all_results = {}
    
    for particle in PARTICLE_LIST:
        results = process_particle(particle)
        if results is not None:
            all_results[particle] = results
            make_plots_vs_momentum(particle, results, metric="sigma")
            make_plots_vs_momentum(particle, results, metric="sigma_eff")
            make_plots_vs_theta(particle, results, metric="sigma")
            make_plots_vs_theta(particle, results, metric="sigma_eff")
    
    print("\n" + "=" * 70)
    print("[INFO] Résumé : qualité des fits (particules × % de fits réussis)")
    print("=" * 70)
    for particle, results in all_results.items():
        total = 0
        ok = 0
        tails = 0
        for proc in results["fit_quality"]:
            for v in results["fit_quality"][proc]:
                total += 1
                if results["fit_quality"][proc][v] == "OK":
                    ok += 1
                if results["tail_ratio"][proc].get(v, 0) > TAIL_WARNING_THRESHOLD:
                    tails += 1
        if total:
            print(f"  {particle}: {ok}/{total} fits OK ({100*ok/total:.0f}%), "
                  f"{tails} points avec queues > {TAIL_WARNING_THRESHOLD}")
    
    print("\n[INFO] Terminé !")
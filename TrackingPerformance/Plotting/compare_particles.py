"""
compare_particles.py — Figure thèse : μ vs e vs π (σ fit vs σ_eff).

Lit les summary.json produits par plots_tracking_sep.py et génère des figures
qui superposent les 3 particules, avec σ issu du fit (gauss ou CB) ET σ_eff
en marqueur ouvert. Permet de visualiser où les queues non-gaussiennes sont
importantes et donc où la métrique importe.

Usage:
    DETECTOR_MODEL=CLD_o2_v07 DIGI_MODE=detailed python compare_particles.py

Produit:
    - compare_vs_theta_{momentum}GeV.{pdf,root} pour chaque p dans STACK_MOMENTUM_LIST
    - compare_vs_momentum_theta{deg}deg.{pdf,root} pour chaque θ dans STACK_THETA_LIST
"""
import ROOT
import os
import sys
import json
import math as _math

try:
    from config_tracking import (
        DIGI_MODE, NEVTS, DETECTOR_MODEL, EOSBASE,
        PARTICLE_LIST, THETA_LIST, MOMENTUM_LIST,
        STACK_MOMENTUM_LIST, STACK_THETA_LIST,
        get_plots_output_dir, ensure_dir, pname,
        VAR_LIST, AXIS_TITLES, UNIT_SCALE,
        CANVAS_WIDTH, CANVAS_HEIGHT,
        PARTICLE_COLORS, PARTICLE_MARKERS_GAUSS, PARTICLE_MARKERS_EFF,
        X_AXIS_MODE, get_x_value, get_x_label,
    )
except ImportError:
    print("[ERROR] config_tracking.py introuvable")
    sys.exit(1)

ROOT.gROOT.SetBatch(True)

# ============================================================================
# CHARGEMENT DES SUMMARIES
# ============================================================================

def load_summaries():
    """Charge le summary.json de chaque particule disponible."""
    summaries = {}
    for particle in PARTICLE_LIST:
        plots_dir = get_plots_output_dir(particle)
        json_path = os.path.join(plots_dir, "summary.json")
        if not os.path.isfile(json_path):
            print(f"  [WARNING] Pas de summary.json pour {particle}: {json_path}")
            print(f"            Relance plots_tracking_sep.py d'abord.")
            continue
        try:
            with open(json_path) as f:
                summaries[particle] = json.load(f)
            print(f"  [OK] {particle}: chargé depuis {json_path}")
        except Exception as e:
            print(f"  [ERROR] {particle}: {e}")
    return summaries


def get_value(summary, particle, theta, momentum, variable, field):
    """Extrait une valeur (sigma, sigma_eff, ...) du summary."""
    proc = pname(particle, theta, momentum)
    try:
        return summary["results"][proc][variable][field]
    except (KeyError, TypeError):
        return 0.0


# ============================================================================
# FIGURE : σ vs θ à p fixé, 3 particules × 2 métriques
# ============================================================================

def make_comparison_vs_theta(summaries, momentum, output_dir):
    """
    Pour chaque variable, trace σ et σ_eff en fonction de θ, pour μ/e/π.
    6 graphes par canvas : 3 particules × 2 métriques (fit marker plein, eff marker ouvert).
    """
    outfile = ROOT.TFile(f"{output_dir}/compare_vs_theta_{momentum}GeV.root", "recreate")
    c = ROOT.TCanvas(f"compare_theta_{momentum}",
                    f"Comparison vs theta — p={momentum}GeV",
                    CANVAS_WIDTH, CANVAS_HEIGHT)
    c.SetLeftMargin(0.15)
    c.SetBottomMargin(0.15)
    c.SetRightMargin(0.05)
    c.SetTopMargin(0.08)
    
    fname = f"{output_dir}/compare_vs_theta_{momentum}GeV.pdf"
    c.Print(f"{fname}[")
    
    latex_left = ROOT.TLatex()
    latex_left.SetTextFont(42)
    latex_left.SetTextSize(0.035)
    latex_left.SetNDC()
    
    for v in VAR_LIST:
        mg = ROOT.TMultiGraph()
        leg = ROOT.TLegend(0.58, 0.60, 0.93, 0.92)
        leg.SetBorderSize(0); leg.SetFillStyle(0); leg.SetTextFont(42)
        leg.SetTextSize(0.028)
        leg.SetHeader(f"Single particle, p = {momentum} GeV")
        
        kept_graphs = []  # pour garder en vie
        
        for particle in PARTICLE_LIST:
            if particle not in summaries:
                continue
            
            symbol = {"mu": r"#mu", "pi": r"#pi", "e": r"e"}.get(particle, particle)
            color = PARTICLE_COLORS.get(particle, ROOT.kBlack)
            
            # --- Graphe σ du fit (marker plein) ---
            y_f, yerr_f, x_f = [], [], []
            fit_type_seen = "gauss"
            for t in THETA_LIST:
                s = get_value(summaries[particle], particle, t, momentum, v, "sigma")
                se = get_value(summaries[particle], particle, t, momentum, v, "sigma_err")
                ft = get_value(summaries[particle], particle, t, momentum, v, "fit_type")
                if s > 0:
                    y_f.append(s)
                    yerr_f.append(se)
                    x_f.append(float(t))
                    if ft == "CB":
                        fit_type_seen = "CB"
            
            if len(x_f) >= 2:
                y = ROOT.std.vector["double"](y_f)
                x = ROOT.std.vector["double"](x_f)
                ey = ROOT.std.vector["double"](yerr_f)
                ex = ROOT.std.vector["double"]([0]*len(x_f))
                g_fit = ROOT.TGraphErrors(len(x_f), x.data(), y.data(), ex.data(), ey.data())
                g_fit.SetMarkerStyle(PARTICLE_MARKERS_GAUSS.get(particle, ROOT.kFullCircle))
                g_fit.SetMarkerColor(color)
                g_fit.SetLineColor(color)
                g_fit.SetMarkerSize(1.2)
                g_fit.Scale(UNIT_SCALE[v])
                mg.Add(g_fit)
                leg.AddEntry(g_fit, f"{symbol}^{{-}}  #sigma ({fit_type_seen})", "p")
                kept_graphs.append(g_fit)
            
            # --- Graphe σ_eff (marker ouvert) ---
            y_e, yerr_e, x_e = [], [], []
            for t in THETA_LIST:
                s = get_value(summaries[particle], particle, t, momentum, v, "sigma_eff")
                se = get_value(summaries[particle], particle, t, momentum, v, "sigma_eff_err")
                if s > 0:
                    y_e.append(s)
                    yerr_e.append(se)
                    x_e.append(float(t))
            
            if len(x_e) >= 2:
                y = ROOT.std.vector["double"](y_e)
                x = ROOT.std.vector["double"](x_e)
                ey = ROOT.std.vector["double"](yerr_e)
                ex = ROOT.std.vector["double"]([0]*len(x_e))
                g_eff = ROOT.TGraphErrors(len(x_e), x.data(), y.data(), ex.data(), ey.data())
                g_eff.SetMarkerStyle(PARTICLE_MARKERS_EFF.get(particle, ROOT.kOpenCircle))
                g_eff.SetMarkerColor(color)
                g_eff.SetLineColor(color)
                g_eff.SetLineStyle(2)  # pointillé pour distinguer
                g_eff.SetMarkerSize(1.2)
                g_eff.Scale(UNIT_SCALE[v])
                mg.Add(g_eff)
                leg.AddEntry(g_eff, f"{symbol}^{{-}}  #sigma_{{eff}} (68%)", "p")
                kept_graphs.append(g_eff)
        
        if mg.GetListOfGraphs() is None or mg.GetListOfGraphs().GetSize() == 0:
            continue
        
        mg.SetTitle(f";#theta [deg];{AXIS_TITLES[v]}")
        c.SetLogx(False); c.SetLogy()
        c.GetPad(0).SetTickx(1); c.GetPad(0).SetTicky(1)
        mg.Draw("APE")
        mg.GetXaxis().SetTitleSize(0.05)
        mg.GetYaxis().SetTitleSize(0.05)
        mg.GetYaxis().SetTitleOffset(1.3)
        
        latex_left.DrawLatex(0.18, 0.93, f"FCC-ee {DETECTOR_MODEL} {DIGI_MODE}")
        leg.Draw()
        
        c.Update()
        c.Print(fname)
        outfile.cd()
        c.Write(f"Compare_{v}_p{momentum}")
    
    c.Print(f"{fname}]")
    outfile.Close()
    print(f"  [OK] {fname}")


# ============================================================================
# FIGURE : σ vs p à θ fixé, 3 particules × 2 métriques
# ============================================================================

def make_comparison_vs_momentum(summaries, theta, output_dir):
    """Comme make_comparison_vs_theta mais avec p en abscisse."""
    outfile = ROOT.TFile(f"{output_dir}/compare_vs_momentum_theta{theta}deg.root", "recreate")
    c = ROOT.TCanvas(f"compare_mom_{theta}",
                    f"Comparison vs p — θ={theta}°",
                    CANVAS_WIDTH, CANVAS_HEIGHT)
    c.SetLeftMargin(0.15)
    c.SetBottomMargin(0.15)
    c.SetRightMargin(0.05)
    c.SetTopMargin(0.08)
    
    fname = f"{output_dir}/compare_vs_momentum_theta{theta}deg.pdf"
    c.Print(f"{fname}[")
    
    latex_left = ROOT.TLatex()
    latex_left.SetTextFont(42); latex_left.SetTextSize(0.035); latex_left.SetNDC()
    
    for v in VAR_LIST:
        mg = ROOT.TMultiGraph()
        leg = ROOT.TLegend(0.58, 0.60, 0.93, 0.92)
        leg.SetBorderSize(0); leg.SetFillStyle(0); leg.SetTextFont(42)
        leg.SetTextSize(0.028)
        leg.SetHeader(f"Single particle, #theta = {theta}#circ")
        
        kept_graphs = []
        
        for particle in PARTICLE_LIST:
            if particle not in summaries:
                continue
            
            symbol = {"mu": r"#mu", "pi": r"#pi", "e": r"e"}.get(particle, particle)
            color = PARTICLE_COLORS.get(particle, ROOT.kBlack)
            
            # σ du fit
            y_f, yerr_f, x_f = [], [], []
            fit_type_seen = "gauss"
            for m in MOMENTUM_LIST:
                s = get_value(summaries[particle], particle, theta, m, v, "sigma")
                se = get_value(summaries[particle], particle, theta, m, v, "sigma_err")
                ft = get_value(summaries[particle], particle, theta, m, v, "fit_type")
                if s > 0:
                    y_f.append(s); yerr_f.append(se)
                    x_f.append(get_x_value(m, theta))
                    if ft == "CB":
                        fit_type_seen = "CB"
            
            if len(x_f) >= 2:
                y = ROOT.std.vector["double"](y_f)
                x = ROOT.std.vector["double"](x_f)
                ey = ROOT.std.vector["double"](yerr_f)
                ex = ROOT.std.vector["double"]([0]*len(x_f))
                g_fit = ROOT.TGraphErrors(len(x_f), x.data(), y.data(), ex.data(), ey.data())
                g_fit.SetMarkerStyle(PARTICLE_MARKERS_GAUSS.get(particle, ROOT.kFullCircle))
                g_fit.SetMarkerColor(color)
                g_fit.SetLineColor(color)
                g_fit.SetMarkerSize(1.2)
                g_fit.Scale(UNIT_SCALE[v])
                mg.Add(g_fit)
                leg.AddEntry(g_fit, f"{symbol}^{{-}}  #sigma ({fit_type_seen})", "p")
                kept_graphs.append(g_fit)
            
            # σ_eff
            y_e, yerr_e, x_e = [], [], []
            for m in MOMENTUM_LIST:
                s = get_value(summaries[particle], particle, theta, m, v, "sigma_eff")
                se = get_value(summaries[particle], particle, theta, m, v, "sigma_eff_err")
                if s > 0:
                    y_e.append(s); yerr_e.append(se)
                    x_e.append(get_x_value(m, theta))
            
            if len(x_e) >= 2:
                y = ROOT.std.vector["double"](y_e)
                x = ROOT.std.vector["double"](x_e)
                ey = ROOT.std.vector["double"](yerr_e)
                ex = ROOT.std.vector["double"]([0]*len(x_e))
                g_eff = ROOT.TGraphErrors(len(x_e), x.data(), y.data(), ex.data(), ey.data())
                g_eff.SetMarkerStyle(PARTICLE_MARKERS_EFF.get(particle, ROOT.kOpenCircle))
                g_eff.SetMarkerColor(color)
                g_eff.SetLineColor(color)
                g_eff.SetLineStyle(2)
                g_eff.SetMarkerSize(1.2)
                g_eff.Scale(UNIT_SCALE[v])
                mg.Add(g_eff)
                leg.AddEntry(g_eff, f"{symbol}^{{-}}  #sigma_{{eff}} (68%)", "p")
                kept_graphs.append(g_eff)
        
        if mg.GetListOfGraphs() is None or mg.GetListOfGraphs().GetSize() == 0:
            continue
        
        mg.SetTitle(f";{get_x_label()};{AXIS_TITLES[v]}")
        c.SetLogx(); c.SetLogy()
        c.GetPad(0).SetTickx(1); c.GetPad(0).SetTicky(1)
        mg.Draw("APE")
        mg.GetXaxis().SetTitleSize(0.05)
        mg.GetYaxis().SetTitleSize(0.05)
        mg.GetYaxis().SetTitleOffset(1.3)
        
        latex_left.DrawLatex(0.18, 0.93, f"FCC-ee {DETECTOR_MODEL} {DIGI_MODE}")
        leg.Draw()
        
        c.Update()
        c.Print(fname)
        outfile.cd()
        c.Write(f"Compare_{v}_theta{theta}")
    
    c.Print(f"{fname}]")
    outfile.Close()
    print(f"  [OK] {fname}")


# ============================================================================
# TAIL RATIO MAP : une heatmap-like qui montre où les queues sont importantes
# ============================================================================

def make_tail_ratio_summary(summaries, output_dir):
    """
    Pour la variable sdelta_pt (la plus sensible au brem), imprime un tableau
    et trace un graphe 2D du ratio σ_eff/σ_fit pour chaque particule.
    
    Ce résumé permet de voir en un coup d'œil : pour quelles particules, à
    quelles (p, θ), les queues non-gaussiennes posent problème.
    """
    variable = "sdelta_pt"
    print(f"\n{'='*70}")
    print(f"TAIL RATIO σ_eff/σ_fit pour {variable}")
    print("(>1.3 = queues significatives ; >2.0 = dominées par queues)")
    print(f"{'='*70}")
    
    for particle in PARTICLE_LIST:
        if particle not in summaries:
            continue
        print(f"\n  {particle}:")
        print(f"    {'p \\ θ':<8}", end="")
        for t in THETA_LIST:
            print(f"  θ={t:>3}", end="")
        print()
        
        for m in MOMENTUM_LIST:
            print(f"    p={m:<5}", end="")
            for t in THETA_LIST:
                r = get_value(summaries[particle], particle, t, m, variable, "tail_ratio")
                if r == 0:
                    cell = "  --- "
                elif r > 2.0:
                    cell = f"  {r:4.1f}!!"  # Queue dominante
                elif r > 1.3:
                    cell = f"  {r:4.1f}! "  # Queue forte
                else:
                    cell = f"  {r:4.2f}  "  # OK
                print(cell, end="")
            print()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(f"COMPARAISON PARTICULES — {DETECTOR_MODEL} / {DIGI_MODE}")
    print("=" * 70)
    
    print("\n[INFO] Chargement des summaries...")
    summaries = load_summaries()
    
    if not summaries:
        print("\n[ERROR] Aucun summary chargé. Relance d'abord plots_tracking_sep.py")
        print("        pour générer les summary.json de chaque particule.")
        sys.exit(1)
    
    print(f"\n[INFO] {len(summaries)} particules chargées: {list(summaries.keys())}")
    
    # Output directory (sous ANALYSIS/<digi>/_compare/)
    output_dir = f"{EOSBASE}/ANALYSIS/{DIGI_MODE}/_compare"
    suffix = "_pt" if X_AXIS_MODE == "pt" else ""
    output_dir = output_dir + suffix
    ensure_dir(output_dir)
    print(f"\n[INFO] Output: {output_dir}")
    
    # Figures
    print("\n[INFO] Plots σ vs θ pour chaque p cible...")
    for m in STACK_MOMENTUM_LIST:
        make_comparison_vs_theta(summaries, m, output_dir)
    
    print("\n[INFO] Plots σ vs p pour chaque θ cible...")
    for t in STACK_THETA_LIST:
        make_comparison_vs_momentum(summaries, t, output_dir)
    
    # Résumé des queues
    make_tail_ratio_summary(summaries, output_dir)
    
    print("\n[INFO] Terminé !")
    print(f"[INFO] Figures dans: {output_dir}")

# Indirect Support Paper -- Gap Analysis & Completion Plan

**Date**: March 10, 2026  
**Version**: `main_03102026.tex` (28 pages compiled)  
**Status**: Main text largely drafted; Methods/Supplementary substantial; significant gaps in references, figures, tables, and one stub section.

---

## Executive Summary

The indirect-support manuscript has strong main-text prose across 6 of 7 results subsections, a detailed Supplementary/Methods section (~1,150 lines), and 68 defined template variables (4 null). The primary gaps are:

1. **One stub section** (validation_clinical) -- needs full prose
2. **~42 empty `\cite{}`** in Supplementary -- need bibtex keys
3. **8 missing bibtex entries** referenced in main text -- need to be added to `references.bib`
4. **1 placeholder figure** (model_selection) -- needs to be created
5. **3 missing Supplementary Tables** + **1 Extended Data Figure** -- need to be created or included
6. **~13 Supplementary Figures** referenced but not defined as `\label` -- need figure floats added
7. **No Methods section** label (`sec:methods`) -- needs structural fix
8. **4 null variables** -- need values from data
9. **Author/affiliation placeholders** -- need real names

---

## 1. Section-by-Section Status

### 1.1 Introduction (`introduction_03102026.tex`)
- **Status**: COMPLETE (5 paragraphs, well-cited)
- **Issues**:
  - `% TODO`: Figure 1 description comment only (Figure 1 is delivered via Canva page 3 -- `pigean-figure-2.png`)
  - `% ANALYSIS IDEA`: Headline number for additional drug targets vs direct-only

### 1.2 Methods Overview (`methods_overview_03102026.tex`)
- **Status**: COMPLETE (3 paragraphs + Figure 2)
- **Issues**:
  - `\ref{sec:methods}` x2 -- label `sec:methods` does not exist anywhere. Needs a `\label{sec:methods}` added to the Supplementary Information section header or a dedicated Methods section.
  - `\cite{purcell_plink_2007}` -- **missing from references.bib** (needs addition)

### 1.3 Validation: Genetics (`validation_genetics_03102026.tex`)
- **Status**: COMPLETE (long, data-rich section with LOCO, rare disease, temporal, interpretability results)
- **Issues**:
  - `\cite{}` (empty) for MAGMA reference in temporal paragraph
  - `\ref{tab:common-validation-traits}` -- **table not defined** (needs Supplementary Table)
  - `\ref{tab:loco-validation}` -- **table exists** (`Tables/loco_validation.tex`) but not `\input`'d in manuscript
  - `\ref{tab:rare-validation-traits}` -- **table not defined** (needs Supplementary Table)
  - Incomplete sentence: "NEED AN INTERPRETATION" in LOCO paragraph (line ~41)
  - Typo: "mouse phenptypes" (should be "phenotypes")

### 1.4 Context-Dependent Relevance (`geneset_context_03102026.tex`)
- **Status**: MOSTLY COMPLETE but lacks quantitative results
- **Issues**:
  - `{{fig:model_selection}}` -- **placeholder figure** (source: null in manifest)
  - `% TODO`: Add specific model comparison results (which combos performed best)
  - `% TODO`: Add quantitative results for Mouse+MSigDB (convergence, geneset counts, complexity)
  - `% ANALYSIS IDEA`: Show model selection is predictive across trait categories

### 1.5 Validation: Pharma (`validation_pharma_03102026.tex`)
- **Status**: COMPLETE (RS analysis, temporal holdout, detailed comparison to OTG)
- **Issues**:
  - `\ref{fig:extended-1}` -- **Extended Data Figure not defined** (needs figure float + image)
  - Final paragraph stub: "Paragraph on drug target success in comparision to minikel et al." (line 20, needs writing or removal)

### 1.6 Validation: Clinical (`validation_clinical_03102026.tex`)
- **Status**: STUB -- only 2 lines: "Kyrung's Rare disease enrichments."
- **Action needed**: Full subsection prose describing rare disease patient enrichment results
  - Title already written: "Indirect Support Enriches Genes for Rare Disease Patients" (note: typo "Enrichs" in current title)
  - Needs: figure, data variables, citations
  - This is one of the three validation axes promised in the abstract

### 1.7 Resource Description (`resource_description_03102026.tex`)
- **Status**: PARTIAL (2 paragraphs of prose, mostly variable-driven)
- **Issues**:
  - `% TODO`: Comparison to existing resources (Open Targets, GWAS Catalog, Orphanet density)
  - `% TODO`: Describe geneset-trait association landscape
  - `% TODO`: User-facing resource description (query a gene, trait, geneset)
  - `% FIGURE SUGGESTION`: Summary figure for resource density
  - `% ANALYSIS IDEA`: Count PP>90% relationships not in any existing database

---

## 2. Missing Figures

### 2.1 Main Figures (Canva-managed)
| Figure | Canva Page | File | Status |
|--------|-----------|------|--------|
| Figure 1 (method overview) | Page 3 | `pigean-figure-2.png` | EXISTS |
| Figure 2 (validation genetics) | Page 4 | `pigean-figure-3.png` | EXISTS |
| Figure 3 (model selection) | -- | `model_selection` in manifest | **PLACEHOLDER** (source: null) |
| Figure 4 (pharma validation) | Page 5 | `pigean-figure-4.png` | EXISTS |

**Action**: Create the model_selection figure (geneset library comparison) and add to Canva or manifest.

### 2.2 Extended Data Figures
| Ref | Description | Status |
|-----|-------------|--------|
| `fig:extended-1` | OTG L2G as joint function of RS and targets prioritized | **NOT CREATED** -- needs figure float, label, and image |

**Action**: Create Extended Data Figure 1. Some candidate images may exist in `Figures/indirect-support/real/` (e.g., `v1_all-areas.pigean_rs_curves.png`).

### 2.3 Supplementary Figures (referenced in Supplementary section, none have `\label`)
All of these are referenced in the simulation validation text but have no corresponding figure floats:

| Ref Label | Description | Existing Image? |
|-----------|-------------|----------------|
| `fig:null_sim` (a-h) | Null simulation results | Maybe `suppfig1-12.png`? |
| `fig:non_null_sim` (a-d) | Non-null simulation accuracy | Maybe in suppfig series |
| `fig:sim_params` (a-c) | Effect of simulation parameters | Maybe in suppfig series |
| `fig:sim_stability` | Gibbs sampling stability | Maybe in suppfig series |
| `fig:sim_onestep` | Joint vs one-step inference | Maybe in suppfig series |
| `fig:sim_induced` | Alpha regularization importance | Maybe in suppfig series |
| `fig:sim_reg` | w-parameter regularization | Maybe in suppfig series |
| `fig:sim_param_infer` | Sparsity parameter inference | Maybe in suppfig series |
| `fig:sim_vary_sigma` | Varying sigma sensitivity | Maybe in suppfig series |
| `fig:sim_vary_p` | Varying p sensitivity | Maybe in suppfig series |
| `fig:sim_gwas_gene_set` (a-f) | GWAS association noise impact | Maybe in suppfig series |

**Action**: Map existing `suppfig1.png` through `suppfig12.png` to these labels and create figure floats in the Supplementary section. There are 12 suppfig images and ~11 referenced figure labels -- likely a near 1:1 mapping.

---

## 3. Missing Tables

| Ref Label | Description | Status |
|-----------|-------------|--------|
| `tab:common-validation-traits` | 12 common validation traits | **NOT CREATED** -- `Tables/validation_trait_information.tex` may be usable |
| `tab:loco-validation` | LOCO cross-validation results | **EXISTS** at `Tables/loco_validation.tex` but not `\input`'d |
| `tab:rare-validation-traits` | 40 rare validation traits | **NOT CREATED** |
| Supplementary Table 3 | Study-wide significance thresholds | Referenced in supp text but **NOT CREATED** |

**Action**:
1. Wire `Tables/loco_validation.tex` into the Supplementary section with `\label{tab:loco-validation}`
2. Create or obtain the common validation traits table
3. Create or obtain the rare validation traits table
4. Create Supplementary Table 3 (significance thresholds from simulations)

---

## 4. Missing/Empty Citations

### 4.1 Bibtex keys referenced but missing from `references.bib` (8 entries)
| Key | Where Referenced | What It Should Be |
|-----|-----------------|-------------------|
| `stoeger_large_2018` | Introduction | Stoeger et al. 2018, research bias toward well-studied genes |
| `mountjoy_open_2022` | Introduction | Mountjoy et al. 2022, Open Targets Genetics |
| `purcell_plink_2007` | Methods overview | Purcell et al. 2007, PLINK |
| `""` (empty key) | Supplementary | ~42 instances of `\cite{}` throughout Supplementary |
| `Wakefield` | Supplementary | Wakefield 2009, Approximate Bayes Factors |
| `costanzo` | Supplementary | Costanzo et al., GWAS effector gene prioritization |
| `udler` | Supplementary | Udler et al., trait architecture partitioning |
| `price` | Supplementary | Price et al., epigenomic annotation partitioning |
| `analogous` | Supplementary | LD-pred original paper (Vilhjalmsson et al. 2015 -- already in bib as `vilhjalmsson_modeling_2015`) |

### 4.2 Empty `\cite{}` in Supplementary (~42 instances)
These span the entire Supplementary/Methods section. Each needs the correct bibtex key. Major categories:

- **Databases**: GWAS Catalog, A2F Portal, Orphanet, GenCC, HPO, Reactome, WikiPathways, Gene Ontology
- **Tools**: REVEL, AlphaMissense, LoFTee, MAGMA, PoPS, PLINK, COJO, FINEMAP, S2G, V2G, exTADA, HuGE
- **Methods papers**: LD-pred, spike-and-slab priors, ABF calculation, Wakefield, convergence diagnostics
- **Empirical references**: nearest gene = effector ~70% of time, sample size corrections

**Action**: Systematically fill all 42 empty `\cite{}` with correct bibtex keys. Most of these are well-known references that can be looked up. Add any missing entries to `references.bib`.

---

## 5. Missing/Broken Cross-References

### 5.1 Structural
| Issue | Fix |
|-------|-----|
| `\ref{sec:methods}` x2 (methods_overview) | Add `\label{sec:methods}` to the Supplementary Information `\section` header |
| `\ref{}` x2 (supplementary lines 217, 962) | Replace with correct label or remove |
| `\ref{Maller}` (supplementary line 622) | Should be `\cite{maller_...}` not `\ref{}` |
| `graphical_model` label placement | Label is after `\end{figure}` -- move inside figure float |

### 5.2 Missing label definitions
All the Supplementary Figure and Table refs listed in Section 2.3 and Section 3 above need `\label{}` definitions added when the figure/table floats are created.

---

## 6. Null/Placeholder Variables

| Variable | Description | Action |
|----------|-------------|--------|
| `NUM_GWAS_FULL_SUMSTATS` | Number of GWAS with full summary statistics | Look up from data pipeline |
| `NUM_TRAITS_FULL_SUMSTATS` | Number of traits with full summary statistics | Look up from data pipeline |
| `NUM_GWAS_CURATED` | Number of curated GWAS | Look up from data pipeline |
| `NUM_TRAITS_CURATED` | Number of curated traits | Look up from data pipeline |

**Note**: These 4 variables are defined but not currently used in any section file. They may be needed when the Resource Description section is expanded.

---

## 7. Prose Issues

| Location | Issue | Priority |
|----------|-------|----------|
| `validation_genetics:41` | "NEED AN INTERPRETATION" placeholder | **HIGH** -- incomplete sentence in main text |
| `validation_genetics:44` | "mouse phenptypes" typo | LOW |
| `validation_clinical:1` | Title typo "Enrichs" -> "Enriches" | LOW |
| `validation_clinical:3` | Entire section is a stub | **HIGH** |
| `validation_pharma:20` | Trailing stub comment about minikel comparison | MEDIUM |
| `resource_description` | Multiple TODO items for expansion | MEDIUM |
| `main_current.tex:132-144` | Author/affiliation placeholders | MEDIUM |
| `main_current.tex:166` | Keywords are placeholder | LOW |

---

## 8. Structural / Organization Issues

| Issue | Description | Action |
|-------|-------------|--------|
| No dedicated Methods section | `sec:methods` referenced but only Supplementary exists | Either (a) add a brief Methods section before References, or (b) change refs to point to Supplementary subsections |
| No Extended Data section | Extended Data Figure 1 referenced but no section exists | Add Extended Data section between References and Supplementary |
| Supplementary Figures missing | 11+ figures referenced in simulation text with no floats | Add figure environments with `\label` for each |
| Supplementary Tables missing | 3-4 tables referenced but not included | Create and `\input` table files |
| `luacode` package loaded | Line 71 loads `\usepackage{luacode}` but pdflatex is used | Remove or guard with conditional |

---

## 9. Priority Action Plan

### Tier 1: Blocking Issues (needed for readable draft)
- [ ] Write `validation_clinical` section (rare disease patient enrichment)
- [ ] Fix "NEED AN INTERPRETATION" sentence in validation_genetics
- [ ] Add `\label{sec:methods}` to Supplementary section
- [ ] Wire in `Tables/loco_validation.tex` with proper label
- [ ] Fix `\ref{Maller}` -> `\cite{maller_...}` in supplementary
- [ ] Fix 2 empty `\ref{}` in supplementary

### Tier 2: Reference Completeness (needed for ?? resolution)
- [ ] Add 8 missing bibtex entries to `references.bib`
- [ ] Fill all ~42 empty `\cite{}` in Supplementary with correct keys
- [ ] Create Supplementary Tables for validation traits (common + rare)

### Tier 3: Figures & Visual Assets
- [ ] Create `model_selection` figure (geneset library comparison)
- [ ] Create Extended Data Figure 1 (RS vs targets for L2G)
- [ ] Map `suppfig1-12.png` to Supplementary Figure labels and create floats
- [ ] Add Extended Data section to manuscript structure

### Tier 4: Content Expansion
- [ ] Expand `resource_description` section with resource comparisons and user guidance
- [ ] Complete pharma validation comparison to Minikel et al.
- [ ] Fill 4 null variables from data pipeline
- [ ] Add author names and affiliations

### Tier 5: Polish
- [ ] Fix typos (phenptypes, Enrichs)
- [ ] Remove `luacode` package dependency
- [ ] Add keywords
- [ ] Review abstract for consistency with final results

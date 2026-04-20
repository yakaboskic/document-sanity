## GWAS Coverage of Disease-Relevant Genes

### Setup and Definitions

**Gene populations:**

- $N_D$ = genes with direct GWAS support (detectable genetic association)
- $N_{I \setminus D}$ = genes with indirect support only (relevant via pathways, but no direct GWAS signal)
- $N_C = N_D + N_{I \setminus D}$ = total disease-relevant genes (capturable through genetics + annotations)

Note that genes with indirect support form a superset: $\mathcal{D} \subseteq \mathcal{I}$, so $N_I = N_D + N_{I \setminus D} = N_C$.

**Key question:** What fraction of disease-relevant genes can GWAS ever detect?

$$\gamma = \frac{N_D}{N_C} = \frac{N_D}{N_I}$$

---

### Assumptions

**(A1) Complete direct signal:** In the infinite sample limit, every gene contributes to direct evidence continuously according to its true effect.

**(A2) Perfect annotations:** The annotation matrix $X$ captures the complete functional structure—every disease-relevant gene is either directly associated OR reachable from directly-associated genes through true biological pathways.

**(A3) Soft counts:** Gene counts are computed as posterior expectations, avoiding hard thresholds.

---

### Soft Gene Counts

The expected number of relevant genes under each evidence type:

$$\tilde{N}_D = \sum_i P_i^D = \sum_i \frac{\pi \cdot ABF^D_i}{1 + \pi \cdot ABF^D_i}$$

$$\tilde{N}_I = \sum_i P_i^I = \sum_i \frac{\pi \cdot ABF^I_i}{1 + \pi \cdot ABF^I_i}$$

where $\pi$ is the prior probability of gene relevance and $ABF^D_i$, $ABF^I_i$ are the direct and indirect Bayes factors from the PIGEAN model.

---

### Empirical Relationship

Across traits, fit the linear relationship:

$$\tilde{N}_I = \alpha \tilde{N}_D + C$$

where:

- $\alpha$ = expansion factor (how much indirect evidence expands beyond direct)
- $C$ = baseline constant

**Coverage:**

$$\gamma = \frac{\tilde{N}_D}{\tilde{N}_I} = \frac{\tilde{N}_D}{\alpha \tilde{N}_D + C}$$

**When $C \ll \alpha \tilde{N}_D$:**

$$\gamma \approx \frac{1}{\alpha}$$

---

### Bound Direction

**Claim:** The observed coverage $\hat{\gamma}^{obs}$ is an **upper bound** on true coverage.

**Proof:**

1. **Finite sample effect:** $\tilde{N}_D^{obs} \leq \tilde{N}_D^{\infty}$
   - Missing direct signal reduces direct counts
   - Also biases $\beta$ estimates, reducing indirect counts

2. **Imperfect annotations:** $\tilde{N}_{I \setminus D}^{obs} \leq \tilde{N}_{I \setminus D}^{true}$
   - Missing pathways → miss indirect-only genes
   - Denominator reduced more than numerator

3. **Regularization:** Shrinks $\beta$ → conservative indirect scores → undercount indirect-only genes

**Net effect:** Both imperfections preferentially reduce indirect-only counts, inflating the observed coverage ratio:

$$\hat{\gamma}^{obs} = \frac{\tilde{N}_D^{obs}}{\tilde{N}_D^{obs} + \tilde{N}_{I \setminus D}^{obs}} \geq \frac{\tilde{N}_D^{true}}{\tilde{N}_D^{true} + \tilde{N}_{I \setminus D}^{true}} = \gamma^{true}$$

**Therefore:**

$$\boxed{\gamma^{true} \leq \frac{1}{\hat{\alpha}^{obs}}}$$

---

### Summary

| Quantity | Interpretation |
|----------|----------------|
| $\tilde{N}_D$ | Expected number of directly-supported genes |
| $\tilde{N}_I$ | Expected number of disease-relevant genes (direct + indirect) |
| $\alpha$ | Expansion factor from annotations |
| $\gamma = 1/\alpha$ | Upper bound on GWAS coverage |

**Practical interpretation:** If $\hat{\alpha} = 2$, then GWAS can detect **at most 50%** of disease-relevant genes; the remainder require pathway-based inference.

This is a really elegant idea—use downsampling to empirically estimate correction factors that can be extrapolated to the ideal limits.

---

## Correction Factor Framework
Now, that we have a way to approximate $\gamma^{true}$, we might be able to correct our $\tilde{\alpha}^{obs}$ by observing if there is a pattern between GWAS sample size and percentage of missing functional annotations on high powered GWAS using our best annotation model (MsigDB + Mouse; determined via independent model selection).   

### Observed $\alpha$ as a Function of Two Limits

Let:

- $f \in (0, 1]$ = fraction of full GWAS sample size
- $g \in (0, 1]$ = fraction of complete annotations

The observed expansion factor depends on both:

$$\alpha^{obs}(f, g) \leq \alpha^{true} = \alpha(\infty, 1)$$

We want to estimate $\alpha^{true}$ by extrapolating from observed $\alpha^{obs}(f, g)$.

---

## Downsampling Approach

### GWAS Downsampling (varying f)

Hold annotations fixed at full gold standard ($g = 1$), vary GWAS power:

For each downsample fraction $f \in \{0.1, 0.2, \ldots, 1.0\}$:
1. Compute $\tilde{N}_D(f)$, $\tilde{N}_I(f)$
2. Fit $\alpha(f)$ from the relationship across traits

**Expected behavior:**

- As $f \to 0$: Direct signal vanishes, $\tilde{N}_D \to N\pi$ (prior only), $\alpha(f) \to 1$
- As $f \to 1$: Observed values
- As $f \to \infty$: True asymptote $\alpha_D^{*}$

**Parametric model:**

$$\alpha(f) = \alpha_D^{*} - \frac{a}{f^{\beta}}$$

or equivalently:

$$\alpha(f) = \alpha_D^{*} \left(1 - e^{-\lambda f}\right)$$

Fit $\alpha_D^{*}$, $\lambda$ (or $a$, $\beta$) from downsampled data, extrapolate to $f \to \infty$.

---

### Annotation Downsampling (varying g)

Hold GWAS at full power ($f = 1$), vary annotation completeness:

For each annotation fraction $g \in \{0.1, 0.2, \ldots, 1.0\}$:
1. Randomly subsample gene sets to fraction $g$
2. Recompute $\tilde{N}_I(g)$ (keeping $\tilde{N}_D$ fixed)
3. Fit $\alpha(g)$

**Expected behavior:**

- As $g \to 0$: No propagation, $\tilde{N}_I \to \tilde{N}_D$, $\alpha(g) \to 1$
- As $g \to 1$: Observed values with gold standard
- Extrapolating beyond: Estimate complete annotation effect

**Parametric model:**

$$\alpha(g) = 1 + (\alpha_A^{*} - 1) \cdot g^{\eta}$$

or:

$$\alpha(g) = \alpha_A^{*} - \frac{b}{g^{\delta}}$$

Fit to estimate $\alpha_A^{*}$ = asymptotic $\alpha$ with "complete" annotations.

---

## Combined Correction

### Separable Model

Assume the two effects are approximately separable:

$$\alpha^{obs}(f, g) = 1 + (\alpha^{true} - 1) \cdot h(f) \cdot k(g)$$

where:

- $h(f) \in [0, 1]$ = sample size efficiency, $h(\infty) = 1$
- $k(g) \in [0, 1]$ = annotation completeness, $k(1) = k_{gold}$

**From GWAS downsampling:** Estimate $h(f)$ curve, extrapolate $h(\infty) = 1$

**From annotation downsampling:** Estimate $k(g)$ curve at $f = 1$

**Correction:**

$$\alpha^{true} = 1 + \frac{\alpha^{obs}(1, 1) - 1}{h(1) \cdot k(1)}$$

---

### Additive Model (alternative)

If effects are additive in log-space:

$$\log(\alpha^{obs} - 1) = \log(\alpha^{true} - 1) - \Delta_f(f) - \Delta_g(g)$$

where:

- $\Delta_f(f) \to 0$ as $f \to \infty$
- $\Delta_g(g) \to 0$ as $g \to 1$ (or complete)

**From downsampling curves:**

$$\Delta_f(f) = \log(\alpha^{obs}(f, 1) - 1) - \log(\alpha^{obs}(1, 1) - 1) \cdot \frac{f}{1}$$

Extrapolate to estimate correction terms.

---

## Extrapolation Strategies

### For GWAS (sample size)

The relationship between sample size and discovered loci often follows:

$$\tilde{N}_D(n) \sim n^{\kappa}$$

for some $\kappa \in (0, 1)$ before saturation. This suggests:

$$\alpha(f) = \alpha_D^{*} - c \cdot f^{-\kappa}$$

Plot $\alpha(f)$ vs $f^{-\kappa}$—should be linear, intercept gives $\alpha_D^{*}$.

### For Annotations (completeness)

If annotations have diminishing returns (redundancy), expect:

$$\alpha(g) = \alpha_A^{*} \cdot (1 - e^{-\mu g})$$

This saturates as $g \to \infty$, but since $g \leq 1$, you're estimating where on the curve you are.

**Alternative:** If gold standard is nearly complete, fit:

$$\alpha(g) = \alpha_A^{*} - \frac{d}{g}$$

Linear in $1/g$, intercept gives $\alpha_A^{*}$.

---

## Diagnostic Plots

1. **$\alpha$ vs f curve:** Should be monotonically increasing, approaching asymptote
2. **$\alpha$ vs g curve:** Should be monotonically increasing
3. **Residuals:** Check that parametric fits are reasonable
4. **Cross-validation:** Hold out some (f, g) combinations, check prediction

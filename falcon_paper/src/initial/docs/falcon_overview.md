# Results <!-- \label{sec:Results} -->

# Overview of FALCON <!-- \label{sec:falcon_overview} -->

FALCON is a probabilistic framework designed to model rare and common genetic associations and auxiliary epigenomic annotations as a function of an unknown variable quantifying a gene’s genetic support. FALCON directly ingests standard association statistics while accounting for linkage disequilibrium and environmental noise, seamlessly integrating both common and rare variants by tailoring their underlying hyperparameter distributions. To inform its predictive priors, the model synthesizes diverse functional genomic annotations—including accessible chromatin, enhancers, and loss-of-function metrics—alongside sophisticated variant-to-gene (V2G) linkage scores derived from 3D DNA looping and eQTL mapping (see Supplemental Material). By anchoring on specific genes and evaluating them against all available genomic data and competing targets, FALCON introduces a “reverse genetics” approach that provides a foundation for identifying true causal associations.

In brief, FALCON models observed genetic association data, genomic annotations and linkage scores as a function of a primary latent variable for a gene’s probability of disease relevance and secondary latent variables for variant probability, annotation relevance and linkage probability.

[Equation that shows the rigor used in FALCON here]

The primary output of this framework is gene genetic support—the posterior probability that a specific gene is functionally associated with a trait, conditioned on all observed data. This score—calculated via Gibbs sampling— serves as a standardized metric to evaluate genes within a high-dimensional phenotype space. Furthermore, FALCON’s architecture simultaneously yields secondary outputs, including variant causal probability, fine-mapping, and fine-linking to identify the most likely target genes. Together, these probabilistic outputs generate an end-to-end map translating genetic variation into actionable insight to undercover functional biology (Fig. 1c).

We validated FALCON’s architecture using simulations across diverse trait architectures and sample sizes. Based on Normalized Discounted Cumulative Gain (NDCG)[cite], FALCON’s capacity to recover true disease-relevant genes was nearly optimal, reaching saturation at sample sizes where standard gene-level approaches continued to struggle. Implementation of the model in different scenarios demonstrated shows the importance of combined data. Removal of functional annotations caused a ~60% performance drop in smaller cohorts, while the simultaneous removal of both annotations and linkages reduced an extra ~30% in large-scale datasets (Fig. 1d). 

Finally, we confirmed FALCON’s performance on real-world data by evaluating ten UK Biobank traits—representing a broad heritability spectrum 10–55%— utilizing exome-derived rare-variant burden tests as an independent ground truth. Using adapted Gini[cite] and NDCG metrics to assess ranking inequality and prioritization, FALCON demonstrated an ability to separate true biological signals from noise, rapidly concentrating highly relevant genes at the top of its rankings (Fig. 1e, 1f).

```latex
\begin{figure}[h!]
    \centering
    {{fig:fig_1}}
\end{figure}
```

<!-- document-sanity:preview:begin hash=8db08fb1 -->
![figure](../figures/fig_1.html)
<!-- document-sanity:preview:end -->
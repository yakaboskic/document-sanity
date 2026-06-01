# The HUGEST- Map <!-- \label{sec:map} -->

To provide a catalog of human genetic support, we constructed the Genetic Map (G-Map) by applying FALCON on {{All_Total_Traits:,.0f}} bottom-line traits from the Knowledge Portal[cite] across {{All_Total_Genes:,.0f}} genes. The map establishes {{Raw_All_total_Traits_Per_Gene:,.0f}} {{BayesFactorCat}} trait-gene associations, defined by a probability threshold of {{Threshold:.2f}} based on the Jeffreys Scale with a {{Prior:,.0f}}% prior[cite].

On average, individual traits are {{BayesFactorCat}} associated with {{Raw_All_mean_Genes_Per_Trait:.0f}} genes. Conversely, {{Raw_All_at_least_1_Traits_Per_Gene:,.0f}} genes possess at least one {{BayesFactorCat}} trait association, with {{Raw_All_exact_1_Traits_Per_Gene:,.0f}} of these genes being associated with exactly one.

The network encompasses {{All_Total_Loci:,.0f}} distinct loci. The map identifies the nearest gene as the top candidate (the gene with the highest probability in the locus) on {{op: (Raw_All_Top_Nearest_Gene_Loci/All_Total_Loci) * 100:.2f}}% of loci; replicating other studies ([stacy], [Mountjoy]). When examining gene associations for each locus, the majority {{op: (Raw_All_Single_Gene_Loci/All_Total_Loci)*100 :,.2f}}% are associated with a single gene (Fig. 3d).

Using relative success rate[cite], we calculated that genes with {{BayesFactorCat}} genetic support from the G-Map are {{falcon_RS_cat:.2f}} times more likely to possess a functional drug target. Compared to the {{BL_NG_RS:.2f}} rate from the baseline nearest-gene approach, this represents a {{op:((falcon_RS_cat-BL_NG_RS)/BL_NG_RS)*100:.2f}}% improvement. 

Using the curated list of effector genes in [Constanzo] and clinical information from open targets, The G-Map identified {{Raw_Novel_total_Traits_Per_Gene:,.0f}} novel gene-trait associations with and average of {{Raw_Novel_mean_Genes_Per_Trait:,.0f}} novel genes per trait. From the subset of associations with no clinical trials, {{Raw_Repurposable_total_Traits_Per_Gene:,.0f}} have approved drug targets for the associated gene, making them prime candidates for rapid clinical repurposing.
Dynamic Figure 3 and Figure 4.

By integrating the curated list of effector genes from [Constanzo] with clinical data from Open Targets, we systematically categorized the G-Map associations to funnel associations from established therapeutics down to novel discoveries. Within the clinical space, the network captures {{Raw_Clinical_total_Traits_Per_Gene:,.0f}} established gene-trait associations. Expanding beyond active clinical trials into translational opportunities, we identified {{Raw_Repurposable_total_Traits_Per_Gene:,.0f}} associations involving genes with approved drug targets for other indications, rendering them prime candidates for rapid clinical repurposing. Finally, filtering the network for strictly uncharacterized targets uncovers an expansive frontier of {{Raw_Novel_total_Traits_Per_Gene:,.0f}} novel gene-trait associations, driven by an average of {{Raw_Novel_mean_Genes_Per_Trait:,.0f}} novel genes per trait.

# Coverage <!-- \label{sec:coverage} -->  
To evaluate trait representation in the G-Map across established phenotypes, we performed a coverage analysis using the Mondo Disease Ontology [cite]. We employed PubMedBERT to calculate semantic similarity, mapping G-Map trait names directly to ontology terms. Applying a similarity threshold of 0.5 at level 3 of the ontology yielded a match success rate of 94.59% and an overall trait coverage of 57.58%. Within this setup, each trait mapped to an average of 2.3 ontology terms, resulting in a total of 2,972 mappings on 1294 unique traits. Furthermore, the semantic similarity scores for these matched traits had a median of 0.74 (IQR, 0.66–0.84).

Analysis of the matched terms revealed distinct patterns in trait representation across the ontology. The categories exhibiting the highest proportional coverage were acute stress disorder and perinatal disease (both at 50%). In terms of absolute frequency, the most heavily represented categories within the G-Map included diseases of genetic or genomic mechanisms (609), nervous system disorders (296), and metabolic diseases (215).

# Overview of genetic architecture <!-- \label{sec:gen_arch} -->       
To accurately capture the underlying genetic architecture and mitigate the redundancy and low power in GWAS cohorts, it is necessary to evaluate these associations through a bias-adjusted framework. Raw association counts often inflate genetic signals; thus, correcting for this bias is essential to represent a more accurate biological distribution of pleiotropy and polygenicity. By filtering out noise, this bias adjusted analysis shows the biologically active hubs across established clinical therapeutics, repurposable targets and novel discoveries.

The complete, bias corrected G-Map encompasses a network of {{Bias_adjusted_All_at_least_1_Traits_Per_Gene:,.0f}} unique genes mapped across {{Bias_adjusted_All_at_least_1_Genes_Per_Trait:,.0f}} distinct phenotypic traits, exhibiting a broad pleiotropy (N={{Bias_adjusted_All_plus_1_Traits_Per_Gene:,.0f}}) where genes associate with an average of {{Bias_adjusted_All_mean_Traits_Per_Gene:.1f}} traits. The map contains pleiotropic master regulators, with the most dominant genetic signals emerging from PBX2, NOTCH4, and TSBP1 (the three of them with ~40 {{BayesFactorCat}} associated traits). Phenotypically, global genetic burden is driven by undetermined stroke etiology (toastUNDETER; 1,872), complex lean mass phenotypes (TB-LM; 1,815), and platelet volume (PlatVol; 1,692). Consequently, the broadest categorical signals across the entire G-Map are deeply concentrated within hematological (17,223), musculoskeletal (4,575), and renal (4,177) domains.

Funneling this global architecture into the clinically validated space, the network captures {{Bias_adjusted_Clinical_at_least_1_Traits_Per_Gene:,.0f}} established therapeutic targets driving {{Bias_adjusted_Clinical_at_least_1_Genes_Per_Trait:,.0f}} distinct clinical phenotypes. The G-Map highlights a strong clinical inclination toward chronic inflammatory and structural conditions, where top genes: TUBB (4.42), TNF (2.78), and NR3C1 (2.69), and traits: ankylosing spondylitis (6.18), chronic obstructive pulmonary disease (COPD; 5.69), and TB-LM (4.84), modulate microtubule dynamics, systemic inflammation, and glucocorticoid signaling.
Expanding beyond established indications, the repurposable class identifies [total|Genes_Repurposable] genes and [total|Traits_Repurposable] traits, providing a baseline for immediate translational opportunities. In this repurposable context, the strongest gene candidates are heavily anchored in immune regulation and the major histocompatibility complex, led by HLA-DRB1 (36.01), AGER (32.28), and HLA-DRB5 (30.43). The phenotypic signals and categories driving these repurposable opportunities closely mirror the global baseline. 

Finally, filtering the map for novel associations uncovers [total|Genes_Novel] uncharted biological hubs across [total|Traits_Novel] distinct traits that have yet to be therapeutically exploited. Within this novel tier, the most dominant genes—PBX2 (40.57), NOTCH4 (40.56), and C6orf10 (40.09)—are identical to the global leaders, emphasizing that the bulk of the network’s untapped pleiotropic potential resides in these developmental and immune-linked loci. The driving traits for these novel discoveries continue to be toastUNDETER (1,872.67), TB-LM (1,810.87), and PlatVol (1,692.64). This alignment firmly establishes the hematological (17,209.32), musculoskeletal (4,467.65), and renal (3,942.39) domains as the primary categories for new target discovery.


```latex
\begin{figure}[h!]
    \centering
    {{fig:fig_3}}
\end{figure}
```

<!-- document-sanity:preview:begin hash=f77ebf96 -->
![figure](../figures/fig_3.html)
<!-- document-sanity:preview:end -->

```latex
\begin{figure}[h!]
    \centering
    {{fig:fig_4}}
\end{figure}
```

<!-- document-sanity:preview:begin hash=6b9b013f -->
![figure](../figures/fig_4.html)
<!-- document-sanity:preview:end -->

"""External-data variable loading: NA filtering, empty-name skipping, and the
all-NA-variation -> global value path (features added in the falcon work)."""

from document_sanity.manifest import ExternalDataEntry
from document_sanity.variable_processor import VariableProcessor


def _write_csv(path, header, rows):
    lines = [",".join(header)]
    lines += [",".join(str(c) for c in r) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_na_in_name_column_is_dropped_from_name(tmp_path):
    csv = tmp_path / "g.csv"
    _write_csv(
        csv,
        ["Correction", "Type", "Stat", "Metric", "BayesFactorCat", "Prior", "Value"],
        [
            ["Raw", "All", "mean", "Genes", "Strong", "5.0", 10],
            ["Raw", "NA", "mean", "Genes", "Strong", "5.0", 30],  # Type=NA -> dropped
        ],
    )
    p = VariableProcessor(default_variations={"BayesFactorCat": "Strong", "Prior": "5.0"})
    cfg = ExternalDataEntry(
        source="g.csv",
        value_column="Value",
        name_columns=["Correction", "Type", "Stat", "Metric"],
        variation_columns=["BayesFactorCat", "Prior"],
    )
    p.load_external_data(tmp_path, [cfg])

    assert "Raw_All_mean_Genes" in p.external_vars
    # Type column was NA, so it drops out of the joined name.
    assert "Raw_mean_Genes" in p.external_vars
    assert p.get_value("Raw_All_mean_Genes") == 10
    assert p.get_value("Raw_mean_Genes") == 30


def test_all_na_name_row_is_skipped(tmp_path):
    csv = tmp_path / "g.csv"
    _write_csv(
        csv,
        ["Type", "Metric", "BayesFactorCat", "Prior", "Value"],
        [
            ["NA", "NA", "Strong", "5.0", 999],  # every name column NA -> skip
            ["All", "Genes", "Strong", "5.0", 5],
        ],
    )
    p = VariableProcessor()
    cfg = ExternalDataEntry(
        source="g.csv",
        value_column="Value",
        name_columns=["Type", "Metric"],
        variation_columns=["BayesFactorCat", "Prior"],
    )
    p.load_external_data(tmp_path, [cfg])

    # The all-NA row must not create an empty-named variable.
    assert "" not in p.external_vars
    assert "All_Genes" in p.external_vars
    assert len(p.external_vars) == 1


def test_all_na_variation_becomes_global_value(tmp_path):
    csv = tmp_path / "g.csv"
    _write_csv(
        csv,
        ["Metric", "BayesFactorCat", "Prior", "Value"],
        [["Total_Loci", "NA", "NA", 777]],
    )
    p = VariableProcessor(default_variations={"BayesFactorCat": "Strong", "Prior": "5.0"})
    cfg = ExternalDataEntry(
        source="g.csv",
        value_column="Value",
        name_columns=["Metric"],
        variation_columns=["BayesFactorCat", "Prior"],
    )
    p.load_external_data(tmp_path, [cfg])

    # variation columns present but all NA -> resolves globally regardless of
    # which variation the caller (or default_variations) selects.
    assert p.get_value("Total_Loci") == 777
    assert p.get_value("Total_Loci", variations={"BayesFactorCat": "Weak", "Prior": "1.0"}) == 777


def test_variation_selection_uses_default_variations(tmp_path):
    csv = tmp_path / "g.csv"
    _write_csv(
        csv,
        ["Metric", "BayesFactorCat", "Prior", "Value"],
        [
            ["Genes", "Strong", "5.0", 10],
            ["Genes", "Weak", "5.0", 20],
        ],
    )
    p = VariableProcessor(default_variations={"BayesFactorCat": "Strong", "Prior": "5.0"})
    cfg = ExternalDataEntry(
        source="g.csv",
        value_column="Value",
        name_columns=["Metric"],
        variation_columns=["BayesFactorCat", "Prior"],
    )
    p.load_external_data(tmp_path, [cfg])

    assert p.get_value("Genes") == 10  # picks the Strong/5.0 slice by default
    assert p.get_value("Genes", variations={"BayesFactorCat": "Weak", "Prior": "5.0"}) == 20


def test_get_all_available_variables_includes_external(tmp_path):
    csv = tmp_path / "g.csv"
    _write_csv(csv, ["Metric", "Value"], [["Genes", 10], ["Loci", 20]])
    p = VariableProcessor()
    p.variables["MANUAL"] = 1
    cfg = ExternalDataEntry(source="g.csv", value_column="Value", name_columns=["Metric"])
    p.load_external_data(tmp_path, [cfg])

    avail = p.get_all_available_variables()
    assert avail == sorted(["MANUAL", "Genes", "Loci"])

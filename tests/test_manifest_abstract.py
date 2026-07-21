"""File-sourced abstract (`abstract: docs/abstract.md`) resolution and its
round-trip through save() — the abstract_source feature."""

import yaml

from document_sanity.manifest import Manifest


def _write_manifest(path, abstract_value):
    path.write_text(
        yaml.safe_dump({"metadata": {"title": "T", "abstract": abstract_value}}),
        encoding="utf-8",
    )


def test_inline_abstract_passes_through(tmp_path):
    m_path = tmp_path / "manifest.yaml"
    _write_manifest(m_path, "An inline abstract with {{VAR}}.")
    m = Manifest(m_path)

    assert m.metadata.abstract == "An inline abstract with {{VAR}}."
    assert m.metadata.abstract_source is None


def test_file_sourced_abstract_is_loaded(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "abstract.md").write_text("Loaded body text.", encoding="utf-8")
    m_path = tmp_path / "manifest.yaml"
    _write_manifest(m_path, "docs/abstract.md")
    m = Manifest(m_path)

    assert m.metadata.abstract == "Loaded body text."
    assert m.metadata.abstract_source == "docs/abstract.md"


def test_missing_abstract_file_falls_back_to_inline(tmp_path):
    m_path = tmp_path / "manifest.yaml"
    _write_manifest(m_path, "docs/does_not_exist.md")
    m = Manifest(m_path)

    # A .md-looking path that does not resolve is left inline (with a warning)
    # so the typo surfaces in output rather than crashing the build.
    assert m.metadata.abstract == "docs/does_not_exist.md"
    assert m.metadata.abstract_source is None


def test_save_preserves_file_pointer_not_body(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "abstract.md").write_text("Loaded body text.", encoding="utf-8")
    m_path = tmp_path / "manifest.yaml"
    _write_manifest(m_path, "docs/abstract.md")
    m = Manifest(m_path)

    out = tmp_path / "out.yaml"
    m.save(out)
    reloaded = yaml.safe_load(out.read_text(encoding="utf-8"))

    # The saved manifest keeps the pointer, not the inlined body.
    assert reloaded["metadata"]["abstract"] == "docs/abstract.md"

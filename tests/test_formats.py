import os
import subprocess
import pytest
import sys
import shutil
from pathlib import Path

@pytest.fixture
def falcon_project(tmp_path):
    """Use the falcon_paper directory for testing."""
    repo_root = Path(__file__).parent.parent

    # Initialize falcon_paper in the tmp_path
    test_project = tmp_path / "falcon_paper"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    # Init project
    subprocess.run(
        [sys.executable, "-m", "document_sanity.cli", "init", str(test_project), "--strategy", "date"],
        env=env,
        check=True,
        capture_output=True,
        text=True
    )

    # Add NUM_SAMPLES to manifest and some external data
    manifest_path = next((test_project / "src").iterdir()) / "manifest.yaml"
    with open(manifest_path, 'r') as f:
        manifest_content = f.read()

    with open(manifest_path, 'w') as f:
        f.write(manifest_content.replace(
            "variables:",
            "variables:\n  NUM_SAMPLES: 1000"
        ) + "\nexternal_data:\n  - source: data.csv\n    name_columns: [Name]\n    value_column: Value\n")

    # Create data.csv
    with open(manifest_path.parent / "data.csv", 'w') as f:
        f.write("Name,Value\nEXT_VAR,12345\n")

    # Create a dummy docx template for word build
    templates_dir = test_project / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    docx_path = templates_dir / "article.docx"

    import zipfile
    with zipfile.ZipFile(docx_path, 'w') as z:
        z.writestr('word/document.xml', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Template</w:t></w:r></w:p>
    <w:sectPr></w:sectPr>
  </w:body>
</w:document>""")

    # Update intro.md to use the variables
    intro_path = manifest_path.parent / "docs" / "introduction.md"
    with open(intro_path, 'w') as f:
        f.write("# Introduction\n\nAnalyzed {{NUM_SAMPLES:,}} samples. External: {{EXT_VAR:,}}\n")

    return test_project, env

def test_latex_generation(falcon_project):
    root, env = falcon_project
    result = subprocess.run(
        [sys.executable, "-m", "document_sanity.cli", "build", "--root", str(root)],
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    # Check for main.tex in out/
    out_dir = root / "out"
    version_dirs = [d for d in out_dir.iterdir() if d.is_dir()]
    assert len(version_dirs) > 0
    version_dir = version_dirs[0]
    assert (version_dir / "latex" / "main.tex").exists()

    # Verify variable substitution in sections
    intro_tex = (version_dir / "latex" / "sections" / "introduction.tex").read_text()
    assert "Analyzed 1,000 samples" in intro_tex
    assert "External: 12,345" in intro_tex

def test_html_generation(falcon_project):
    root, env = falcon_project
    result = subprocess.run(
        [sys.executable, "-m", "document_sanity.cli", "html", "--root", str(root)],
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    # Check for index.html in out/
    out_dir = root / "out"
    version_dirs = [d for d in out_dir.iterdir() if d.is_dir()]
    version_dir = version_dirs[0]
    assert (version_dir / "html" / "index.html").exists()

    index_html = (version_dir / "html" / "index.html").read_text()
    assert "1,000" in index_html
    assert "12,345" in index_html

def test_word_generation(falcon_project):
    root, env = falcon_project
    result = subprocess.run(
        [sys.executable, "-m", "document_sanity.cli", "word", "--root", str(root)],
        env=env,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    # Check for main.docx in out/
    out_dir = root / "out"
    version_dirs = [d for d in out_dir.iterdir() if d.is_dir()]
    version_dir = version_dirs[0]
    assert (version_dir / "word" / "main.docx").exists()

def test_pdf_compiler_missing_error(falcon_project):
    root, env = falcon_project
    # Try to compile without pdflatex
    result = subprocess.run(
        [sys.executable, "-m", "document_sanity.cli", "build", "--root", str(root), "--compile"],
        env=env,
        capture_output=True,
        text=True
    )

    # If pdflatex is missing, it should show our custom error message
    if not shutil.which("pdflatex"):
        assert "Error: LaTeX compiler 'pdflatex' not found." in result.stdout
        assert "To build PDFs, you need a LaTeX distribution installed." in result.stdout

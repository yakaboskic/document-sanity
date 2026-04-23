#!/usr/bin/env python3
"""
LaTeX to Markdown converter.

Converts LaTeX source files to Markdown for use as source-of-truth in
the document-sanity pipeline. Handles:

- \\section, \\subsection, \\subsubsection -> #, ##, ###
- \\textbf, \\textit, \\texttt -> **bold**, *italic*, `code`
- \\begin{itemize/enumerate} -> bullet/numbered lists
- \\begin{figure} -> preserved as ```latex blocks
- \\begin{table} -> preserved as ```latex blocks
- \\begin{equation/align} -> preserved as ```latex blocks
- \\cite{} -> preserved as-is (pass-through)
- \\ref{}, \\label{} -> preserved as-is
- {{VAR}} template syntax -> preserved as-is
- LaTeX comments (%) -> stripped or converted to HTML comments
- \\input{} -> noted as TODO markers
"""

import re
from pathlib import Path
from typing import Optional


# LaTeX environments that should be preserved as raw LaTeX blocks
PASSTHROUGH_ENVS = {
    'figure', 'figure*', 'table', 'table*',
    'equation', 'equation*', 'align', 'align*',
    'eqnarray', 'eqnarray*',
    'gather', 'gather*', 'multline', 'multline*', 'split',
    'tikzpicture', 'algorithm', 'algorithmic', 'lstlisting',
    'tabular', 'tabular*', 'longtable', 'tablenotes', 'subcaption',
    'appendices', 'subequations', 'cases', 'pmatrix', 'bmatrix',
    'theorem', 'lemma', 'proof', 'definition', 'proposition',
    'example', 'remark', 'quote', 'center',
}


def latex_to_md(content: str, preserve_comments: bool = False) -> str:
    """Convert LaTeX content to Markdown.

    Args:
        content: LaTeX source text.
        preserve_comments: If True, convert LaTeX % comments to <!-- --> HTML comments.
                          If False, strip them entirely.

    Returns:
        Markdown text.
    """
    lines = content.split('\n')
    output = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines (pass through)
        if not stripped:
            output.append('')
            i += 1
            continue

        # Handle LaTeX comments
        if stripped.startswith('%'):
            comment_text = stripped[1:].strip()
            if preserve_comments and comment_text:
                output.append(f'<!-- {comment_text} -->')
            # else: strip the comment
            i += 1
            continue

        # Check for passthrough environments
        env_match = re.match(r'^\s*\\begin\{(\w+\*?)\}', stripped)
        if env_match:
            env_name = env_match.group(1)
            if env_name in PASSTHROUGH_ENVS:
                # Collect everything until \end{env_name}
                block_lines = [line]
                i += 1
                depth = 1
                while i < len(lines) and depth > 0:
                    block_lines.append(lines[i])
                    if re.search(rf'\\begin\{{{re.escape(env_name)}\}}', lines[i]):
                        depth += 1
                    if re.search(rf'\\end\{{{re.escape(env_name)}\}}', lines[i]):
                        depth -= 1
                    i += 1
                output.append('```latex')
                output.extend(block_lines)
                output.append('```')
                output.append('')
                continue

        # Headings (support multi-line and nested-brace arguments)
        heading_start = re.match(r'^\s*\\(section|subsection|subsubsection|paragraph|subparagraph)\*?\{(.*)$', stripped)
        if heading_start:
            def _find_close(text: str) -> int:
                """Return index of the } balancing an already-open {."""
                depth = 1
                k = 0
                while k < len(text):
                    if text[k] == '\\' and k + 1 < len(text):
                        k += 2
                        continue
                    if text[k] == '{':
                        depth += 1
                    elif text[k] == '}':
                        depth -= 1
                        if depth == 0:
                            return k
                    k += 1
                return -1

            after_open = heading_start.group(2)
            close = _find_close(after_open)
            accumulated = after_open
            j = i
            if close == -1:
                # Multi-line heading: gather lines until brace balance is reached
                j = i + 1
                while j < len(lines):
                    accumulated += ' ' + lines[j].strip()
                    close = _find_close(accumulated)
                    if close != -1:
                        break
                    j += 1

            if close != -1:
                heading_text = accumulated[:close]
                remainder = accumulated[close + 1:].strip()
                level_map = {
                    'section': '#', 'subsection': '##', 'subsubsection': '###',
                    'paragraph': '####', 'subparagraph': '#####',
                }
                level = level_map[heading_start.group(1)]
                title = _convert_inline_to_md(heading_text)
                label_match = re.search(r'\\label\{([^}]+)\}', remainder)
                label_comment = ''
                if label_match:
                    label_comment = f' <!-- \\label{{{label_match.group(1)}}} -->'

                output.append(f'{level} {title}{label_comment}')
                output.append('')
                i = j + 1
                continue

        # \label{} on its own line
        if re.match(r'^\s*\\label\{[^}]+\}$', stripped):
            output.append(f'<!-- {stripped.strip()} -->')
            i += 1
            continue

        # \newpage -> ---
        if stripped == '\\newpage':
            output.append('---')
            output.append('')
            i += 1
            continue

        # \maketitle, \tableofcontents etc -> skip or comment
        if stripped in ('\\maketitle', '\\tableofcontents'):
            i += 1
            continue

        # Itemize/enumerate environments
        if re.match(r'^\s*\\begin\{(itemize|enumerate)\}', stripped):
            env_type = 'enumerate' if 'enumerate' in stripped else 'itemize'
            i += 1
            item_num = 0
            while i < len(lines):
                item_line = lines[i].strip()
                if re.match(r'\\end\{(itemize|enumerate)\}', item_line):
                    i += 1
                    break
                if item_line.startswith('\\item'):
                    item_text = re.sub(r'^\\item\s*', '', item_line)
                    item_text = _convert_inline_to_md(item_text)
                    if env_type == 'enumerate':
                        item_num += 1
                        output.append(f'{item_num}. {item_text}')
                    else:
                        output.append(f'- {item_text}')
                elif item_line:
                    # Continuation of previous item
                    if output and (output[-1].startswith('- ') or re.match(r'^\d+\.', output[-1])):
                        output[-1] += ' ' + _convert_inline_to_md(item_line)
                i += 1
            output.append('')
            continue

        # \bibliography{} -> note
        if stripped.startswith('\\bibliography{'):
            bib_match = re.match(r'\\bibliography\{([^}]+)\}', stripped)
            if bib_match:
                output.append(f'<!-- bibliography: {bib_match.group(1)} -->')
            i += 1
            continue

        # \input{} -> note
        if stripped.startswith('\\input{'):
            input_match = re.match(r'\\input\{([^}]+)\}', stripped)
            if input_match:
                output.append(f'<!-- \\input{{{input_match.group(1)}}} -->')
            i += 1
            continue

        # Regular paragraph text - convert inline formatting
        para_lines = []
        while i < len(lines):
            current = lines[i].strip()
            # Stop at block boundaries
            if not current:
                break
            if current.startswith('\\section') or current.startswith('\\subsection') or current.startswith('\\subsubsection'):
                break
            if current.startswith('\\paragraph') or current.startswith('\\subparagraph'):
                break
            if re.match(r'\\begin\{', current):
                break
            if re.match(r'\\end\{', current):
                break
            if current == '\\newpage':
                break
            if current.startswith('\\bibliography'):
                break
            if current.startswith('\\input{'):
                break
            if current.startswith('%'):
                # Handle inline comments in paragraphs
                if preserve_comments:
                    comment = current[1:].strip()
                    if comment:
                        para_lines.append(f'<!-- {comment} -->')
                i += 1
                continue

            # Strip trailing comments from text lines
            text = _strip_trailing_comment(current)
            para_lines.append(_convert_inline_to_md(text))
            i += 1

        if para_lines:
            # Join paragraph lines
            output.append(' '.join(para_lines))
            output.append('')
            continue

        i += 1

    return '\n'.join(output)


def _strip_trailing_comment(line: str) -> str:
    """Strip trailing LaTeX comment, handling escaped % and {{VAR:%}} template syntax."""
    result = []
    j = 0
    in_template = 0  # Track nesting depth of {{ }}
    while j < len(line):
        # Track template variable delimiters
        if line[j:j+2] == '{{':
            in_template += 1
            result.append('{{')
            j += 2
            continue
        if line[j:j+2] == '}}' and in_template > 0:
            in_template -= 1
            result.append('}}')
            j += 2
            continue
        # Inside a template variable, % is literal (e.g., {{VAR:.1%}})
        if in_template > 0:
            result.append(line[j])
            j += 1
            continue
        # Escaped %
        if line[j] == '\\' and j + 1 < len(line) and line[j + 1] == '%':
            result.append('\\%')
            j += 2
        elif line[j] == '%':
            break
        else:
            result.append(line[j])
            j += 1
    return ''.join(result).rstrip()


def _convert_inline_to_md(text: str) -> str:
    """Convert inline LaTeX formatting to Markdown.

    Preserves {{VAR}} template syntax, \\cite{}, \\ref{}, \\label{}.
    """
    # Protect template variables
    protected = {}
    counter = [0]

    def protect(pattern):
        def replacer(m):
            key = f'\x00P{counter[0]}\x00'
            protected[key] = m.group(0)
            counter[0] += 1
            return key
        return replacer

    # Protect {{...}} template variables
    text = re.sub(r'\{\{[^}]+\}\}', protect(None), text)

    # Protect \cite{}, \ref{}, \label{} -- these have no markdown equivalent
    text = re.sub(r'\\cite\{[^}]+\}', protect(None), text)
    text = re.sub(r'\\ref\{[^}]+\}', protect(None), text)
    text = re.sub(r'\\label\{[^}]+\}', protect(None), text)

    # Protect inline math $...$
    text = re.sub(r'(?<!\$)\$(?!\$)([^$]+?)\$(?!\$)', protect(None), text)

    # Protect display math $$...$$
    text = re.sub(r'\$\$(.+?)\$\$', protect(None), text, flags=re.DOTALL)

    # Protect display math \[ ... \]
    text = re.sub(r'\\\[.+?\\\]', protect(None), text, flags=re.DOTALL)

    # Protect inline math \( ... \)
    text = re.sub(r'\\\(.+?\\\)', protect(None), text, flags=re.DOTALL)

    # Convert formatting
    # \textbf{...} -> **...**
    text = re.sub(r'\\textbf\{([^}]+)\}', r'**\1**', text)

    # \textit{...} or \emph{...} -> *...*
    text = re.sub(r'\\(?:textit|emph)\{([^}]+)\}', r'*\1*', text)

    # \texttt{...} -> `...`
    text = re.sub(r'\\texttt\{([^}]+)\}', r'`\1`', text)

    # \underline{...} -> just the text (no markdown equivalent)
    text = re.sub(r'\\underline\{([^}]+)\}', r'\1', text)

    # \href{url}{text} -> [text](url)
    text = re.sub(r'\\href\{([^}]+)\}\{([^}]+)\}', r'[\2](\1)', text)

    # \url{...} -> <...>
    text = re.sub(r'\\url\{([^}]+)\}', r'<\1>', text)

    # \footnote{...} -> preserve as-is (complex to convert)
    # Leave as is for now, they'll survive in the pass-through

    # Clean up some common LaTeX-isms. Preserve LaTeX escape sequences
    # (\_, \{, \}, \&, \#, \%, \$) so they survive the round-trip back to LaTeX.
    text = text.replace('~', ' ')  # non-breaking space
    text = text.replace('\\\\', '\n')  # line break
    text = text.replace('\\textasciitilde{}', '~')
    text = text.replace('\\textbackslash{}', '\\')

    # Restore protected content (iterate until stable, since placeholders can nest)
    for _pass in range(3):
        for key, val in protected.items():
            text = text.replace(key, val)

    return text.strip()


def extract_metadata_from_main(content: str) -> dict:
    """Extract metadata from a LaTeX main file.

    Pulls title, authors, affiliations, abstract, keywords from
    LaTeX commands like \\title{}, \\author{}, \\abstract{}, etc.
    """
    meta = {}

    # Title
    title_match = re.search(r'\\title(?:\[[^\]]*\])?\{(.+?)\}', content, re.DOTALL)
    if title_match:
        meta['title'] = title_match.group(1).strip()

    # Abstract
    abstract_match = re.search(r'\\abstract\{([\s\S]*?)\}(?=\s*\\)', content)
    if abstract_match:
        raw = abstract_match.group(1).strip()
        meta['abstract'] = _convert_inline_to_md(raw)

    # Keywords
    kw_match = re.search(r'\\keywords\{([^}]+)\}', content)
    if kw_match:
        meta['keywords'] = [k.strip() for k in kw_match.group(1).split(',')]

    # Document class
    dc_match = re.search(r'\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}', content)
    if dc_match:
        meta['document_class'] = dc_match.group(1)

    # Extract \input{} ordering for sections
    inputs = re.findall(r'\\input\{([^}]+)\}', content)
    if inputs:
        meta['section_inputs'] = inputs

    return meta


def convert_latex_file(
    input_path: Path,
    output_path: Path,
    preserve_comments: bool = False,
) -> None:
    """Convert a LaTeX file to Markdown.

    Args:
        input_path: Path to .tex file
        output_path: Path to write .md file
        preserve_comments: Whether to keep LaTeX comments as HTML comments
    """
    content = input_path.read_text(encoding='utf-8')
    md = latex_to_md(content, preserve_comments=preserve_comments)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding='utf-8')


def convert_latex_project(
    root_dir: Path,
    manuscript: str,
    version: str,
    output_dir: Path,
    preserve_comments: bool = True,
) -> dict:
    """Convert an entire pigean-style LaTeX project to the new src/ format.

    Args:
        root_dir: Path to the existing LaTeX project root
        manuscript: Manuscript name (e.g., "indirect-support")
        version: Version string (e.g., "03302026")
        output_dir: Where to write the new src/<version>/ directory
        preserve_comments: Keep LaTeX comments

    Returns:
        Dict with extracted metadata, variables, and section list.
    """
    sections_dir = root_dir / "sections" / manuscript / version
    versions_dir = root_dir / "versions" / manuscript
    main_file = versions_dir / f"main_{version}.tex"
    variables_dir = root_dir / "variables"

    result = {
        'metadata': {},
        'variables': {},
        'sections': [],
        'figures': {},
        'tables': {},
    }

    # 1. Extract metadata from main file
    if main_file.exists():
        main_content = main_file.read_text(encoding='utf-8')
        result['metadata'] = extract_metadata_from_main(main_content)

    # 2. Load variables from JSON
    import json
    vars_file = variables_dir / f"{manuscript}.json"
    if vars_file.exists():
        with open(vars_file) as f:
            raw_vars = json.load(f)
        # Strip _COMMENT_ keys
        result['variables'] = {
            k: v for k, v in raw_vars.items()
            if not k.startswith('_COMMENT')
        }

    shared_file = variables_dir / "shared.json"
    if shared_file.exists():
        with open(shared_file) as f:
            shared = json.load(f)
        for k, v in shared.items():
            if not k.startswith('_COMMENT') and k not in result['variables']:
                result['variables'][k] = v

    # 3. Convert section files to markdown
    docs_dir = output_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    if sections_dir.exists():
        # Use the ordering from main file if available
        section_order = []
        if 'section_inputs' in result['metadata']:
            for inp in result['metadata']['section_inputs']:
                # Extract just the filename
                parts = inp.split('/')
                filename = parts[-1]
                if not filename.endswith('.tex'):
                    filename += '.tex'
                section_order.append(filename)

        # Fall back to alphabetical if no ordering
        section_files = sorted(sections_dir.glob("*.tex"))

        if section_order:
            # Reorder to match main file
            ordered = []
            remaining = list(section_files)
            for name in section_order:
                for sf in remaining:
                    if sf.name == name:
                        ordered.append(sf)
                        remaining.remove(sf)
                        break
            ordered.extend(remaining)
            section_files = ordered

        for tex_file in section_files:
            # Strip the date suffix from filename
            stem = tex_file.stem
            # Remove _MMDDYYYY suffix
            clean_stem = re.sub(r'_\d{8}(-[\w-]+)?$', '', stem)
            md_name = f"{clean_stem}.md"
            md_path = docs_dir / md_name

            convert_latex_file(tex_file, md_path, preserve_comments=preserve_comments)
            result['sections'].append(f"docs/{md_name}")

    # 4. Copy figures
    figures_src = root_dir / "Figures" / manuscript
    if not figures_src.exists():
        figures_src = root_dir / "figures" / manuscript
    figures_dest = output_dir / "figures"
    if figures_src.exists():
        figures_dest.mkdir(parents=True, exist_ok=True)
        import shutil
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.pdf', '*.eps']:
            for fig in figures_src.rglob(ext):
                dest = figures_dest / fig.name
                if not dest.exists():
                    shutil.copy2(fig, dest)

    # 5. Copy tables
    tables_src = root_dir / "Tables"
    if not tables_src.exists():
        tables_src = root_dir / "tables"
    tables_dest = output_dir / "tables"
    if tables_src.exists():
        tables_dest.mkdir(parents=True, exist_ok=True)
        import shutil
        for tex in tables_src.glob("*.tex"):
            shutil.copy2(tex, tables_dest / tex.name)
            result['tables'][tex.stem] = {
                'source': f"tables/{tex.name}",
                'format': 'latex',
            }

    # 6. Copy references
    refs = root_dir / "references.bib"
    if refs.exists():
        import shutil
        shutil.copy2(refs, output_dir / "references.bib")

    return result

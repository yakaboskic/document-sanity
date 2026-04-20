#!/usr/bin/env python3
import os
import re
import shutil
import argparse
from datetime import datetime

def get_today_mmddyyyy():
    return datetime.today().strftime("%m%d%Y")

def parse_inputs(tex_content):
    pattern = re.compile(r'\\input\{([^}]+)\}')
    return pattern.findall(tex_content)

def extract_manuscript_and_date(mainfile):
    # e.g., versions/indirect-support/main_09262025.tex
    parts = mainfile.split(os.sep)
    if len(parts) < 3:
        raise ValueError("Main file path does not match expected structure.")
    manuscript = parts[1]
    main_base = os.path.basename(mainfile)
    m = re.search(r'(\d{8})\.tex$', main_base)
    olddate = m.group(1) if m else None
    return manuscript, olddate

def update_section_path(old_path, manuscript, olddate, newdate):
    # e.g., sections/indirect-support/09262025/sectionname_09262025.tex
    dirname, basename = os.path.split(old_path)
    # Replace olddate in dirname and basename
    new_dirname = dirname.replace(olddate, newdate)
    new_basename = basename.replace(olddate, newdate)
    new_path = os.path.join(new_dirname, new_basename)
    return new_path

def main():
    parser = argparse.ArgumentParser(description="Create a new LaTeX main file and all referenced section files with today's date.")
    parser.add_argument('mainfile', help='Path to the main .tex file (e.g., main_09262025.tex)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done, but do not write or copy any files.')
    args = parser.parse_args()

    mainfile = args.mainfile
    dry_run = args.dry_run
    if not os.path.isfile(mainfile):
        print(f"Error: File not found: {mainfile}")
        return 1

    today = get_today_mmddyyyy()
    try:
        manuscript, olddate = extract_manuscript_and_date(mainfile)
    except Exception as e:
        print(f"Error extracting manuscript name and date: {e}")
        return 1

    # Read main file
    with open(mainfile, 'r') as f:
        main_content = f.read()

    # Find all \input{...} commands
    input_paths = parse_inputs(main_content)

    # Map old section path -> new section path
    section_path_map = {}
    section_input_map = {}
    dirs_to_create = set()
    for path in input_paths:
        # Only process section files in the expected structure
        expected_prefix = f"sections/{manuscript}/"
        if path.startswith(expected_prefix) and olddate and olddate in path:
            # Add extension if not present
            if not path.endswith('.tex'):
                path_with_extension = path + '.tex'
            else:
                path_with_extension = path
            new_path = update_section_path(path_with_extension, manuscript, olddate, today)
            # Track new directory
            new_dir = os.path.dirname(new_path)
            dirs_to_create.add(new_dir)
            section_path_map[path_with_extension] = new_path
            # Remove extension if from new path
            section_input_map[path] = new_path.replace('.tex', '')
            if dry_run:
                print(f"[DRY RUN] Would copy: {path} -> {new_path}")
            else:
                # Ensure new directory exists
                os.makedirs(new_dir, exist_ok=True)
                # Copy file if it exists
                if os.path.isfile(path_with_extension):
                    try:
                        shutil.copy2(path_with_extension, new_path)
                    except Exception as e:
                        print(f"Warning: Could not copy {path_with_extension} to {new_path}: {e}")
                else:
                    print(f"Warning: Section file {path_with_extension} not found, skipping.")

    # Update main_content to point to new section files
    def replace_input(match):
        orig = match.group(1)
        return f"\\input{{{section_input_map.get(orig, orig)}}}"
    new_main_content = re.sub(r'\\input\{([^}]+)\}', replace_input, main_content)

    # Write new main file
    main_dir, main_base = os.path.split(mainfile)
    main_base_new = re.sub(r'_(\d{8})\.tex$', f'_{today}.tex', main_base)
    main_file_new = os.path.join(main_dir, main_base_new)

    if dry_run:
        print("\n[DRY RUN] Would create the following directories if not present:")
        for d in sorted(dirs_to_create):
            print(f"  {d}")
        print(f"\n[DRY RUN] Would write new main file: {main_file_new}")
        print("[DRY RUN] No files or directories were created or modified.")
    else:
        try:
            with open(main_file_new, 'w') as f:
                f.write(new_main_content)
        except Exception as e:
            print(f"Error writing new main file: {e}")
            return 1
        print(f"New main file written: {main_file_new}")
    return 0

if __name__ == "__main__":
    exit(main())

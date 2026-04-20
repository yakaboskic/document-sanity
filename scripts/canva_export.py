#!/usr/bin/env python3
"""
Export designs from Canva using the Canva Connect API.

This script fetches PNG exports of Canva designs and saves them to the figures directory.
Integrates with the figure manifest system for seamless workflow.

Setup:
    1. Authenticate with Canva OAuth2:
       python scripts/canva_auth.py

    This will:
       - Guide you through creating a Canva app
       - Handle OAuth2 flow automatically
       - Save credentials to ~/.canva_config.json

Usage:
    # List all designs
    python scripts/canva_export.py --list-designs

    # Export single design
    python scripts/canva_export.py DESIGN_ID --output figures/manuscript/figure.png

    # Export all from manifest
    python scripts/canva_export.py --from-manifest indirect-support
"""

import json
import sys
import time
import argparse
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse


class CanvaExporter:
    """Export designs from Canva using the Connect API."""

    BASE_URL = "https://api.canva.com/rest/v1"

    def __init__(self, access_token: str):
        """
        Initialize Canva exporter.

        Args:
            access_token: Canva API access token
        """
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        })

    def list_designs(self, limit: int = 50, query: Optional[str] = None) -> list:
        """
        List designs accessible to the user.

        Args:
            limit: Maximum number of designs to return
            query: Optional search query to filter designs

        Returns:
            List of design objects

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/designs"

        params = {
            "limit": limit
        }

        if query:
            params["query"] = query

        response = self.session.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        return data.get("items", [])

    def extract_design_id(self, design_ref: str) -> str:
        """
        Extract design ID from URL or return as-is if already an ID.

        Args:
            design_ref: Design ID or Canva URL

        Returns:
            Design ID
        """
        # Check if it's a URL
        if design_ref.startswith('http'):
            # Parse Canva URL
            # Format: https://www.canva.com/design/DESIGN_ID/...
            parsed = urlparse(design_ref)
            path_parts = parsed.path.split('/')
            if 'design' in path_parts:
                idx = path_parts.index('design')
                if idx + 1 < len(path_parts):
                    return path_parts[idx + 1]
            raise ValueError(f"Could not extract design ID from URL: {design_ref}")
        else:
            # Assume it's already a design ID
            return design_ref

    def create_export_job(
        self,
        design_id: str,
        format_type: str = "png",
        quality: str = "standard",
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> str:
        """
        Create an export job for a design.

        Args:
            design_id: Canva design ID
            format_type: Export format (png, jpg, pdf, etc.)
            quality: Image quality (standard, high)
            width: Optional width in pixels
            height: Optional height in pixels

        Returns:
            Export job ID

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/exports"

        payload = {
            "design_id": design_id,
            "format": {
                "type": format_type
            }
        }

        # Add quality if specified
        if format_type in ['png', 'jpg'] and quality:
            payload["format"]["quality"] = quality

        # Add dimensions if specified
        if width or height:
            dimensions = {}
            if width:
                dimensions["width"] = width
            if height:
                dimensions["height"] = height
            payload["format"]["dimensions"] = dimensions

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        data = response.json()
        job_id = data.get("job", {}).get("id")

        if not job_id:
            raise ValueError("No job ID returned from Canva API")

        return job_id

    def check_export_status(self, job_id: str) -> Dict[str, Any]:
        """
        Check the status of an export job.

        Args:
            job_id: Export job ID

        Returns:
            Job status data

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/exports/{job_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def wait_for_export(
        self,
        job_id: str,
        timeout: int = 120,
        poll_interval: int = 2
    ) -> Dict[str, Any]:
        """
        Wait for export job to complete.

        Args:
            job_id: Export job ID
            timeout: Maximum wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Completed job data

        Raises:
            TimeoutError: If export doesn't complete in time
            RuntimeError: If export fails
        """
        start_time = time.time()

        print(f"Waiting for export job {job_id}...")

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Export job {job_id} timed out after {timeout}s")

            status_data = self.check_export_status(job_id)
            status = status_data.get("job", {}).get("status")

            if status == "success":
                print(f"✓ Export completed")
                return status_data
            elif status == "failed":
                error = status_data.get("job", {}).get("error", {})
                raise RuntimeError(f"Export failed: {error}")
            elif status in ["in_progress", "pending"]:
                print("  ⋯ Exporting...", end="\r")
                time.sleep(poll_interval)
            else:
                print(f"  Unknown status: {status}")
                time.sleep(poll_interval)

    def download_export(self, url: str, output_path: Path) -> None:
        """
        Download exported file.

        Args:
            url: Download URL
            output_path: Local file path to save to
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Download file
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"✓ Downloaded to: {output_path}")

    def export_design(
        self,
        design_ref: str,
        output_path: Path,
        format_type: str = "png",
        quality: str = "high",
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> Path:
        """
        Complete export workflow: create job, wait, download.

        Args:
            design_ref: Design ID or URL
            output_path: Local file path to save to
            format_type: Export format
            quality: Image quality
            width: Optional width
            height: Optional height

        Returns:
            Path to downloaded file
        """
        # Extract design ID
        design_id = self.extract_design_id(design_ref)
        print(f"Exporting design: {design_id}")

        # Create export job
        job_id = self.create_export_job(
            design_id,
            format_type=format_type,
            quality=quality,
            width=width,
            height=height
        )
        print(f"Export job created: {job_id}")

        # Wait for completion
        result = self.wait_for_export(job_id)

        # Get download URL
        urls = result.get("job", {}).get("urls")
        if not urls:
            raise ValueError("No download URLs in export result")

        # Download first URL (typically there's one per page/asset)
        download_url = urls[0] if isinstance(urls, list) else urls.get("url")

        if not download_url:
            raise ValueError("Could not find download URL in export result")

        # Download file
        self.download_export(download_url, output_path)

        return output_path


def load_config(config_path: Path) -> Dict[str, str]:
    """Load Canva configuration from JSON file."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"\nPlease authenticate first by running:\n"
            f"  python scripts/canva_auth.py\n\n"
            f"Or manually create {config_path} with:\n"
            '{\n  "access_token": "your_token_here",\n  "client_id": "your_client_id"\n}'
        )

    with open(config_path, 'r') as f:
        config = json.load(f)

    if 'access_token' not in config:
        raise ValueError(f"No 'access_token' in {config_path}")

    return config


def list_designs(
    exporter: CanvaExporter,
    limit: int = 50,
    query: Optional[str] = None,
    verbose: bool = False
) -> None:
    """
    List all designs accessible to the user.

    Args:
        exporter: CanvaExporter instance
        limit: Maximum number of designs to return
        query: Optional search query
        verbose: Show full details
    """
    try:
        designs = exporter.list_designs(limit=limit, query=query)

        if not designs:
            print("No designs found")
            return

        print(f"\n{'='*80}")
        print(f"📋 Your Canva Designs ({len(designs)} found)")
        print(f"{'='*80}\n")

        for i, design in enumerate(designs, 1):
            design_id = design.get("id", "N/A")
            title = design.get("title", "Untitled")

            # Get thumbnail if available
            thumbnail = design.get("thumbnail", {})
            thumbnail_url = thumbnail.get("url", "")

            # Get timestamps
            created = design.get("created_at", "")
            updated = design.get("updated_at", "")

            print(f"{i}. {title}")
            print(f"   ID: {design_id}")

            if verbose:
                if created:
                    print(f"   Created: {created}")
                if updated:
                    print(f"   Updated: {updated}")
                if thumbnail_url:
                    print(f"   Thumbnail: {thumbnail_url}")
                print(f"   URL: https://www.canva.com/design/{design_id}/edit")

            print()

        print(f"💡 To use a design in your manifest:")
        print(f'   "canva_design_id": "DESIGN_ID_FROM_ABOVE"')

    except Exception as e:
        print(f"❌ Error listing designs: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


def export_from_manifest(
    manuscript: str,
    exporter: CanvaExporter,
    root_dir: Path,
    force: bool = False
) -> None:
    """
    Export all Canva figures defined in manifest.

    Args:
        manuscript: Manuscript name
        exporter: CanvaExporter instance
        root_dir: Repository root directory
        force: Re-export even if file exists
    """
    manifest_path = root_dir / "figures" / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: Manifest not found: {manifest_path}")
        return

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    figures = manifest.get('figures', {})
    exported = 0
    skipped = 0
    errors = 0

    for fig_id, spec in figures.items():
        # Check if figure has Canva design ID
        canva_id = spec.get('canva_design_id')
        if not canva_id:
            continue

        # Get output path
        source = spec.get('source')
        if not source:
            print(f"⚠️  {fig_id}: No source path in manifest")
            continue

        output_path = root_dir / source

        # Skip if file exists and not forcing
        if output_path.exists() and not force:
            print(f"⊘  {fig_id}: Already exists (use --force to re-export)")
            skipped += 1
            continue

        # Export
        try:
            print(f"\n📥 Exporting {fig_id}...")
            exporter.export_design(
                canva_id,
                output_path,
                format_type="png",
                quality="high"
            )
            exported += 1
        except Exception as e:
            print(f"✗  {fig_id}: Export failed: {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"Export Summary")
    print(f"{'='*60}")
    print(f"  Exported: {exported}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export designs from Canva"
    )

    # Main modes
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        'design',
        nargs='?',
        help='Canva design ID or URL'
    )
    group.add_argument(
        '--from-manifest',
        metavar='MANUSCRIPT',
        help='Export all Canva figures from manifest for manuscript'
    )
    group.add_argument(
        '--list-designs',
        action='store_true',
        help='List all your Canva designs'
    )

    # Options
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output file path (required if design specified)'
    )
    parser.add_argument(
        '--format',
        default='png',
        choices=['png', 'jpg', 'pdf'],
        help='Export format (default: png)'
    )
    parser.add_argument(
        '--quality',
        default='high',
        choices=['standard', 'high'],
        help='Image quality (default: high)'
    )
    parser.add_argument(
        '--width',
        type=int,
        help='Export width in pixels (default: 1800 for PNG at 300dpi = 6 inches)'
    )
    parser.add_argument(
        '--height',
        type=int,
        help='Export height in pixels'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=Path.home() / '.canva_config.json',
        help='Path to config file (default: ~/.canva_config.json)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-export even if file exists'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of designs to list (default: 50)'
    )
    parser.add_argument(
        '--search',
        help='Search query to filter designs'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.design and not args.output:
        parser.error("--output is required when specifying a design")

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1

    # Create exporter
    exporter = CanvaExporter(config['access_token'])

    # Determine root directory
    root_dir = Path(__file__).parent.parent

    try:
        if args.list_designs:
            # List designs
            list_designs(
                exporter,
                limit=args.limit,
                query=args.search,
                verbose=args.verbose
            )
        elif args.from_manifest:
            # Export from manifest
            export_from_manifest(
                args.from_manifest,
                exporter,
                root_dir,
                force=args.force
            )
        else:
            # Export single design
            exporter.export_design(
                args.design,
                args.output,
                format_type=args.format,
                quality=args.quality,
                width=args.width,
                height=args.height
            )

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

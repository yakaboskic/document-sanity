#!/usr/bin/env python3
"""
Authenticate with Canva using OAuth2 authorization code flow.

This script handles the OAuth2 flow for CLI usage:
1. Starts a local HTTP server to receive the callback
2. Opens your browser to Canva authorization page
3. Receives the authorization code via redirect
4. Exchanges code for access token
5. Saves token to ~/.canva_config.json

Setup:
    1. Create a Canva app at https://www.canva.com/developers/
    2. Set redirect URI to: http://localhost:8080/callback
    3. Note your Client ID and Client Secret
    4. Run this script: python scripts/canva_auth.py

Usage:
    python scripts/canva_auth.py --client-id YOUR_CLIENT_ID --client-secret YOUR_SECRET
    python scripts/canva_auth.py  # Interactive mode (prompts for credentials)
"""

import argparse
import json
import sys
import webbrowser
import secrets
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
import requests
from typing import Optional, Dict


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to receive OAuth callback."""

    auth_code = None
    error = None

    def do_GET(self):
        """Handle GET request from OAuth redirect."""
        # Parse query parameters
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == '/callback':
            # Check for authorization code
            if 'code' in params:
                CallbackHandler.auth_code = params['code'][0]
                self.send_success_response()
            elif 'error' in params:
                CallbackHandler.error = params.get('error_description', ['Unknown error'])[0]
                self.send_error_response(CallbackHandler.error)
            else:
                self.send_error_response("No authorization code received")
        else:
            self.send_response(404)
            self.end_headers()

    def send_success_response(self):
        """Send success page to browser."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Canva Authentication Success</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 500px;
                }
                h1 { color: #2d3748; margin-bottom: 20px; }
                p { color: #4a5568; font-size: 18px; line-height: 1.6; }
                .success { color: #48bb78; font-size: 60px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓</div>
                <h1>Authentication Successful!</h1>
                <p>You have successfully authenticated with Canva.</p>
                <p>You can close this window and return to your terminal.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def send_error_response(self, error_msg: str):
        """Send error page to browser."""
        self.send_response(400)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Canva Authentication Error</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 500px;
                }}
                h1 {{ color: #2d3748; margin-bottom: 20px; }}
                p {{ color: #4a5568; font-size: 16px; line-height: 1.6; }}
                .error {{ color: #f56565; font-size: 60px; }}
                .error-msg {{ background: #fed7d7; padding: 15px; border-radius: 5px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error">✗</div>
                <h1>Authentication Failed</h1>
                <p>There was an error during authentication.</p>
                <div class="error-msg">{error_msg}</div>
                <p style="margin-top: 20px;">Please try again.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class CanvaAuthenticator:
    """Handle Canva OAuth2 authentication flow."""

    AUTH_URL = "https://www.canva.com/api/oauth/authorize"
    TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
    REDIRECT_URI = "http://localhost:8080/callback"
    SCOPES = ["design:meta:read", "design:content:read", "asset:read"]

    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize authenticator.

        Args:
            client_id: Canva app client ID
            client_secret: Canva app client secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.state = secrets.token_urlsafe(32)

    def get_authorization_url(self) -> str:
        """Generate authorization URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.REDIRECT_URI,
            "scope": " ".join(self.SCOPES),
            "state": self.state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def start_local_server(self, port: int = 8080) -> Optional[str]:
        """
        Start local HTTP server to receive OAuth callback.

        Args:
            port: Port to listen on

        Returns:
            Authorization code or None on error
        """
        server = HTTPServer(('localhost', port), CallbackHandler)

        print(f"🌐 Starting local server on http://localhost:{port}")
        print(f"📡 Waiting for authorization callback...")

        # Handle one request (the callback)
        server.handle_request()

        # Check if we got the code
        if CallbackHandler.auth_code:
            return CallbackHandler.auth_code
        elif CallbackHandler.error:
            raise Exception(f"Authorization failed: {CallbackHandler.error}")
        else:
            raise Exception("No authorization code received")

    def exchange_code_for_token(self, code: str) -> Dict[str, str]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code

        Returns:
            Token response containing access_token

        Raises:
            requests.HTTPError: If token exchange fails
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.REDIRECT_URI,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()

        return response.json()

    def authenticate(self) -> str:
        """
        Complete OAuth flow and return access token.

        Returns:
            Access token

        Raises:
            Exception: If authentication fails
        """
        # Generate authorization URL
        auth_url = self.get_authorization_url()

        print(f"\n{'='*70}")
        print(f"🔐 Canva OAuth2 Authentication")
        print(f"{'='*70}\n")

        print(f"Opening browser for authorization...")
        print(f"If the browser doesn't open, visit this URL manually:")
        print(f"\n{auth_url}\n")

        # Open browser
        webbrowser.open(auth_url)

        # Start local server to receive callback
        code = self.start_local_server()

        print(f"✓ Authorization code received")
        print(f"🔄 Exchanging code for access token...")

        # Exchange code for token
        token_response = self.exchange_code_for_token(code)

        access_token = token_response.get("access_token")
        if not access_token:
            raise Exception("No access token in response")

        print(f"✓ Access token obtained")

        return access_token


def save_config(access_token: str, client_id: str, config_path: Path) -> None:
    """Save configuration to file."""
    config = {
        "access_token": access_token,
        "client_id": client_id
    }

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # Set restrictive permissions
    config_path.chmod(0o600)

    print(f"\n✓ Configuration saved to: {config_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Authenticate with Canva using OAuth2"
    )

    parser.add_argument(
        '--client-id',
        help='Canva app client ID'
    )
    parser.add_argument(
        '--client-secret',
        help='Canva app client secret'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=Path.home() / '.canva_config.json',
        help='Config file path (default: ~/.canva_config.json)'
    )

    args = parser.parse_args()

    # Get credentials (prompt if not provided)
    client_id = args.client_id
    client_secret = args.client_secret

    if not client_id:
        print("\n📋 Canva App Setup")
        print("=" * 70)
        print("\nBefore continuing, make sure you have:")
        print("1. Created a Canva app at https://www.canva.com/developers/")
        print("2. Set redirect URI to: http://localhost:8080/callback")
        print("3. Noted your Client ID and Client Secret")
        print("\n" + "=" * 70 + "\n")

        client_id = input("Enter your Canva Client ID: ").strip()
        if not client_id:
            print("Error: Client ID is required")
            return 1

    if not client_secret:
        client_secret = input("Enter your Canva Client Secret: ").strip()
        if not client_secret:
            print("Error: Client Secret is required")
            return 1

    try:
        # Authenticate
        authenticator = CanvaAuthenticator(client_id, client_secret)
        access_token = authenticator.authenticate()

        # Save configuration
        save_config(access_token, client_id, args.config)

        print(f"\n{'='*70}")
        print(f"🎉 Success! You can now use the Canva export script.")
        print(f"{'='*70}\n")

        print("Try it out:")
        print(f"  python scripts/canva_export.py --list-designs\n")

        return 0

    except KeyboardInterrupt:
        print("\n\n❌ Authentication cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

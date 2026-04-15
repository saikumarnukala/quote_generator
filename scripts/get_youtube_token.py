"""
One-time helper to generate a YouTube OAuth2 refresh token.
Run this LOCALLY (not on GitHub Actions) — it opens a browser for authorization.

Usage:
    python scripts/get_youtube_token.py --client-id YOUR_ID --client-secret YOUR_SECRET

Then add the printed values as GitHub Secrets:
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

Prerequisites:
    1. Google Cloud Console → Create/select project
    2. APIs & Services → Enable "YouTube Data API v3"
    3. APIs & Services → Credentials → Create OAuth client ID
       → Application type: Desktop App
       → Download the JSON and note client_id + client_secret
    4. OAuth consent screen → Add your Google account as a Test User
       (or publish the app for unrestricted access)
"""

import argparse
import json
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

SCOPES   = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT = "http://localhost:8080/callback"


class _CallbackHandler(BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        _CallbackHandler.code = urllib.parse.parse_qs(qs).get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization complete! You can close this tab.")

    def log_message(self, *args):
        pass   # suppress access logs


def main():
    parser = argparse.ArgumentParser(description="Get YouTube OAuth2 refresh token")
    parser.add_argument("--json-file",     default=None,  help="Path to downloaded client_secret JSON file")
    parser.add_argument("--client-id",     default=None,  help="OAuth2 client ID (ignored if --json-file is given)")
    parser.add_argument("--client-secret", default=None,  help="OAuth2 client secret (ignored if --json-file is given)")
    args = parser.parse_args()

    if args.json_file:
        with open(args.json_file) as f:
            data = json.load(f)
        # JSON can be wrapped under "installed" or "web"
        creds = data.get("installed") or data.get("web") or {}
        args.client_id     = creds["client_id"]
        args.client_secret = creds["client_secret"]

    if not args.client_id or not args.client_secret:
        parser.error("Provide --json-file OR both --client-id and --client-secret")

    auth_url = (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={urllib.parse.quote(args.client_id)}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT)}"
        "&response_type=code"
        f"&scope={urllib.parse.quote(SCOPES)}"
        "&access_type=offline"
        "&prompt=consent"   # force refresh_token to be returned
    )

    print("Opening browser for YouTube authorization...")
    webbrowser.open(auth_url)
    print("Waiting for callback on http://localhost:8080 ...")

    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    server.handle_request()   # blocks until one request arrives

    code = _CallbackHandler.code
    if not code:
        print("ERROR: No authorization code received. Did you complete the browser flow?")
        return

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          code,
            "client_id":     args.client_id,
            "client_secret": args.client_secret,
            "redirect_uri":  REDIRECT,
            "grant_type":    "authorization_code",
        },
        timeout=30,
    )
    tokens = r.json()

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(f"ERROR: No refresh_token in response: {tokens}")
        return

    print("\n" + "=" * 50)
    print("  ADD THESE AS GITHUB SECRETS")
    print("=" * 50)
    print(f"  YT_CLIENT_ID     : {args.client_id}")
    print(f"  YT_CLIENT_SECRET : {args.client_secret}")
    print(f"  YT_REFRESH_TOKEN : {refresh_token}")
    print("=" * 50)
    print("\nGo to: https://github.com/YOUR_REPO/settings/secrets/actions")
    print("and add all three secrets.")


if __name__ == "__main__":
    main()

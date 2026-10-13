"""Scrape public Instagram profiles with Python. No login, one file."""
import argparse
import json
import os
import re
import sys

from curl_cffi import requests

# Instagram server-renders the full profile into the page it sends to iPhone
# Safari, so we ask for that page and read the JSON embedded in it.
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
HEADERS = {
    "User-Agent": IPHONE_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
JSON_SCRIPT = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL)


class ScrapeError(Exception):
    pass


def fetch_page(username, proxy=None):
    """Download the mobile profile page for a username."""
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        resp = requests.get(
            f"https://www.instagram.com/{username}/",
            headers=HEADERS,
            impersonate="safari_ios",  # match an iPhone's TLS fingerprint too
            proxies=proxies,
            allow_redirects=False,
            timeout=30,
        )
    except requests.RequestsError as exc:
        raise ScrapeError(f"Network error: {exc}") from exc

    if resp.status_code == 404:
        raise ScrapeError(f"User not found: {username}")
    if resp.status_code in (301, 302, 401, 403, 429):
        raise ScrapeError(
            f"Instagram answered HTTP {resp.status_code}: rate-limited or blocked. "
            "Cloud and datacenter IPs are blocked most; try a home connection or --proxy."
        )
    if resp.status_code != 200:
        raise ScrapeError(f"Unexpected HTTP {resp.status_code} from Instagram.")
    return resp.text


def find_user(node):
    """Search the page's JSON for the profile object."""
    if isinstance(node, dict):
        if "follower_count" in node and "username" in node and "pk" in node:
            return node
        node = list(node.values())
    if isinstance(node, list):
        for value in node:
            found = find_user(value)
            if found:
                return found
    return None


def get_profile(username, proxy=None):
    html = fetch_page(username, proxy)
    user = None
    for blob in JSON_SCRIPT.findall(html):
        try:
            user = find_user(json.loads(blob))
        except ValueError:
            continue
        if user:
            break
    if not user:
        raise ScrapeError(f"No profile data on the page for {username}. The user may not exist.")

    return {
        "id": str(user["pk"]),
        "username": user.get("username"),
        "full_name": user.get("full_name"),
        "biography": user.get("biography"),
        "is_private": user.get("is_private"),
        "is_verified": user.get("is_verified"),
        "followers_count": user.get("follower_count"),
        "following_count": user.get("following_count"),
        "has_reels": user.get("has_any_clips"),
        "pronouns": user.get("pronouns") or [],
        "profile_pic_url": user.get("profile_pic_url"),
    }


def main():
    parser = argparse.ArgumentParser(description="Scrape public Instagram profiles.")
    parser.add_argument("usernames", nargs="+", help="one or more usernames, with or without @")
    parser.add_argument("-o", "--output", help="write JSON to this file")
    parser.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"), help="proxy URL, e.g. http://user:pass@host:port")
    args = parser.parse_args()

    results, failed = [], 0
    for name in args.usernames:
        try:
            results.append(get_profile(name.strip().lstrip("@").strip("/"), args.proxy))
        except ScrapeError as exc:
            failed += 1
            print(f"Error: {exc}", file=sys.stderr)

    data = results[0] if len(args.usernames) == 1 and results else results
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Saved {len(results)} profile(s) to {args.output}")
    elif results:
        print(text)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

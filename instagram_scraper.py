"""Scrape public Instagram profiles, posts, comments and search with Python. No login, one file."""
import argparse
import json
import os
import re
import secrets
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from curl_cffi import requests

APP_ID = "936619743392459"  # the public id Instagram's own web app sends
ASBD_ID = "359341"
# Instagram's web app names each GraphQL query by a doc_id. They change every
# few months; when a command starts failing, grab the new id from the web app.
DOC_PROFILE = "28036671149327607"
DOC_POST = "25951076901259180"
DOC_COMMENTS = "27261273046856309"
DOC_SEARCH = "26300727659606513"

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
JSON_SCRIPT = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL)
SHORTCODE = re.compile(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")
MEDIA_TYPES = {1: "image", 2: "video", 8: "carousel"}


class ScrapeError(Exception):
    pass


def find(pattern, text):
    m = re.search(pattern, text)
    return next((g for g in m.groups() if g), "") if m else ""


def find_node(node, keys):
    """Depth-first search for the first dict that has all `keys`."""
    if isinstance(node, dict):
        if all(k in node for k in keys):
            return node
        node = list(node.values())
    if isinstance(node, list):
        for value in node:
            found = find_node(value, keys)
            if found:
                return found
    return None


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None


def shortcode_of(value):
    m = SHORTCODE.search(value)
    return m.group(1) if m else value.strip("/")


def media_id_of(shortcode):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    n = 0
    for ch in shortcode:
        n = n * 64 + alphabet.index(ch)
    return str(n)


class Instagram:
    """A logged-out session: visit the homepage once, then reuse its cookies and tokens."""

    def __init__(self, proxy=None):
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        self.http = requests.Session(impersonate="chrome", proxies=self.proxies)
        self.device_id = str(uuid.uuid4()).upper()
        self.http.cookies.update({"csrftoken": secrets.token_hex(16), "ig_did": self.device_id, "mid": secrets.token_urlsafe(21)[:28]})
        page = self._send("GET", "https://www.instagram.com/").text
        # Tokens the web app reads from the page and sends back with every query.
        self.tokens = {
            "lsd": find(r'"LSD",\s*\[\],\s*\{"token":"([^"]+)"\}', page),
            "jazoest": find(r'"jazoest"\s*:\s*"(\d+)"', page) or find(r"jazoest=(\d+)", page),
            "__hs": find(r'"haste_session"\s*:\s*"([^"]+)"', page),
            "__hsi": find(r'"hsi"\s*:\s*"([^"]+)"', page),
            "__rev": find(r'"__spin_r"\s*:\s*(?:"([^"]+)"|(\d+))', page),
            "__spin_b": find(r'"__spin_b"\s*:\s*"([^"]+)"', page),
            "__spin_t": find(r'"__spin_t"\s*:\s*(?:"([^"]+)"|(\d+))', page),
        }

    def _send(self, method, url, **kwargs):
        try:
            resp = self.http.request(method, url, timeout=30, allow_redirects=False, **kwargs)
        except requests.RequestsError as exc:
            raise ScrapeError(f"Network error: {exc}") from exc
        if resp.status_code in (301, 302, 401, 403, 429):
            raise ScrapeError(
                f"Instagram answered HTTP {resp.status_code}: rate-limited or blocked. "
                "Cloud and datacenter IPs are blocked most; try a home connection or --proxy."
            )
        if resp.status_code == 404:
            raise ScrapeError("Not found.")
        if resp.status_code != 200:
            raise ScrapeError(f"Unexpected HTTP {resp.status_code} from Instagram.")
        return resp

    def _headers(self, referer):
        return {
            "x-ig-app-id": APP_ID,
            "x-asbd-id": ASBD_ID,
            "x-csrftoken": self.http.cookies.get("csrftoken") or "",
            "x-fb-lsd": self.tokens["lsd"],
            "x-ig-www-claim": "0",
            "x-requested-with": "XMLHttpRequest",
            "referer": referer,
        }

    def graphql(self, doc_id, name, route, variables, referer):
        """Run one of the web app's logged-out GraphQL queries."""
        body = {
            "av": "0", "__d": "www", "__user": "0", "__a": "1", "__req": "1", "__comet_req": "7",
            "dpr": "1", "__ccg": "EXCELLENT", "__crn": route, "lsd": self.tokens["lsd"],
            "fb_api_caller_class": "RelayModern", "fb_api_req_friendly_name": name,
            "server_timestamps": "true", "doc_id": doc_id,
            "variables": json.dumps(variables, separators=(",", ":")),
        }
        body.update({k: v for k, v in self.tokens.items() if v and k.startswith("__")})
        body["jazoest"] = self.tokens["jazoest"] or "2" + str(sum(map(ord, self._headers("")["x-csrftoken"])))
        if self.tokens["__rev"]:
            body["__spin_r"] = self.tokens["__rev"]
        headers = {
            **self._headers(referer),
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.instagram.com",
            "x-fb-friendly-name": name,
        }
        data = self._send("POST", "https://www.instagram.com/api/graphql", data=urlencode(body), headers=headers).json()
        if not data.get("data"):
            raise ScrapeError(f"Instagram returned no data for {name}: {str(data.get('errors'))[:200]}")
        return data["data"]

    # --- profile ---------------------------------------------------------

    def profile(self, username):
        """Basic fields from the iPhone profile page, then the full profile query by id."""
        try:
            resp = requests.get(
                f"https://www.instagram.com/{username}/",
                headers={"User-Agent": IPHONE_UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"},
                impersonate="safari_ios",  # this page is only fully rendered for iPhones
                proxies=self.proxies, allow_redirects=False, timeout=30,
            )
        except requests.RequestsError as exc:
            raise ScrapeError(f"Network error: {exc}") from exc
        if resp.status_code != 200:
            raise ScrapeError(f"Instagram answered HTTP {resp.status_code} for {username}: blocked, or the user does not exist.")
        user = None
        for blob in JSON_SCRIPT.findall(resp.text):
            try:
                user = find_node(json.loads(blob), ("username", "pk", "follower_count"))
            except ValueError:
                continue
            if user:
                break
        if not user:
            raise ScrapeError(f"No profile data on the page for {username}. The user may not exist.")

        full = {}
        try:
            full = self.graphql(
                DOC_PROFILE, "PolarisProfilePageContentQuery", "comet.igweb.PolarisProfileRoute",
                {"enable_integrity_filters": True, "id": str(user["pk"]),
                 "__relay_internal__pv__PolarisCannesGuardianExperienceEnabledrelayprovider": True,
                 "__relay_internal__pv__PolarisCASB976ProfileEnabledrelayprovider": False,
                 "__relay_internal__pv__PolarisWebSchoolsEnabledrelayprovider": False,
                 "__relay_internal__pv__PolarisRepostsConsumptionEnabledrelayprovider": False,
                 "__relay_internal__pv__PolarisShortDramaEnabledrelayprovider": False},
                f"https://www.instagram.com/{username}/",
            ).get("user") or {}
        except ScrapeError:
            pass  # the basic fields above are still a useful answer
        return {
            "id": str(user["pk"]),
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "biography": user.get("biography"),
            "external_url": full.get("external_url"),
            "bio_links": [link.get("url") for link in full.get("bio_links") or [] if link.get("url")],
            "category": full.get("category") or None,
            "is_business": full.get("is_business"),
            "is_private": user.get("is_private"),
            "is_verified": user.get("is_verified"),
            "followers_count": user.get("follower_count"),
            "following_count": user.get("following_count"),
            "profile_pic_url": (full.get("hd_profile_pic_url_info") or {}).get("url") or user.get("profile_pic_url"),
        }

    # --- posts -----------------------------------------------------------

    def post(self, url_or_shortcode):
        code = shortcode_of(url_or_shortcode)
        body = {
            "av": "0", "__d": "www", "__user": "0", "__a": "1", "__req": "1", "dpr": "1", "__ccg": "MODERATE",
            "lsd": self.tokens["lsd"], "fb_api_caller_class": "RelayModern", "server_timestamps": "true",
            "fb_api_req_friendly_name": "PolarisPostRootQuery", "doc_id": DOC_POST,
            "variables": json.dumps({"shortcode": code, "fetch_tagged_user_count": None, "hoisted_comment_id": None, "hoisted_reply_id": None}),
        }
        headers = {
            **self._headers(f"https://www.instagram.com/p/{code}/"),
            "content-type": "application/x-www-form-urlencoded",
            "x-fb-friendly-name": "PolarisPostRootQuery",
            "x-root-field-name": "xdt_api__v1__media__shortcode__web_info",
        }
        data = self._send("POST", "https://www.instagram.com/graphql/query", data=urlencode(body), headers=headers).json()
        items = ((data.get("data") or {}).get("xdt_api__v1__media__shortcode__web_info") or {}).get("items") or []
        if not items:
            raise ScrapeError(f"Post not found or not public: {code}")
        return clean_post(items[0])

    def comments(self, url_or_shortcode, limit=50):
        code = shortcode_of(url_or_shortcode)
        out, cursor = [], None
        while len(out) < limit:
            media = self.graphql(
                DOC_COMMENTS, "PolarisLoggedOutDesktopWWWPostCommentsPaginationQuery",
                "comet.igweb.PolarisLoggedOutDesktopWWWPostRoute",
                {"after": cursor, "first": min(50, limit - len(out)), "media_id": media_id_of(code)},
                f"https://www.instagram.com/p/{code}/",
            ).get("xig_polaris_media") or {}
            conn = media.get("comments_connection") or {}
            for edge in conn.get("edges") or []:
                c = edge["node"]
                out.append({
                    "id": c.get("pk"),
                    "text": c.get("text"),
                    "created_at": iso(c.get("created_at")),
                    "like_count": c.get("comment_like_count"),
                    "reply_count": c.get("child_comment_count") or 0,
                    "username": (c.get("user") or {}).get("username"),
                    "user_is_verified": (c.get("user") or {}).get("is_verified"),
                })
            page = conn.get("page_info") or {}
            cursor = page.get("end_cursor")
            if not page.get("has_next_page") or not cursor:
                break
        return out[:limit]

    def search(self, keyword, limit=24):
        """Top public posts for a keyword, from Instagram's logged-out search pages."""
        out, cursor = [], None
        while len(out) < limit:
            variables = {"debug": None, "include_description": True, "keyword": keyword, "media_count": 12, "related_keywords_count": 10}
            if cursor:
                variables["after"] = cursor
            result = self.graphql(
                DOC_SEARCH, "PolarisLoggedOutPopularSearchPageQuery", "comet.igweb.PolarisLoggedOutPopularSearchPageRoute",
                variables, f"https://www.instagram.com/popular/{keyword}/",
            ).get("xig_logged_out_popular_search_media_info") or {}
            for edge in result.get("edges") or []:
                m = edge["node"]
                out.append({
                    "shortcode": m.get("code"),
                    "url": f"https://www.instagram.com/p/{m.get('code')}/",
                    "type": "video" if "Video" in (m.get("__typename") or "") else "image",
                    "caption": (m.get("caption") or {}).get("text"),
                    "play_count": m.get("play_count"),
                    "username": (m.get("user") or {}).get("username"),
                    "thumbnail_url": m.get("display_uri"),
                })
            page = result.get("page_info") or {}
            cursor = page.get("end_cursor")
            if not page.get("has_next_page") or not cursor:
                break
        return out[:limit]


def clean_post(m):
    images = (m.get("image_versions2") or {}).get("candidates") or []
    videos = m.get("video_versions") or []
    owner = m.get("user") or m.get("owner") or {}
    return {
        "id": m.get("pk"),
        "shortcode": m.get("code"),
        "url": f"https://www.instagram.com/p/{m.get('code')}/",
        "type": MEDIA_TYPES.get(m.get("media_type"), m.get("media_type")),
        "product_type": m.get("product_type"),
        "caption": (m.get("caption") or {}).get("text"),
        "taken_at": iso(m.get("taken_at")),
        "like_count": m.get("like_count"),
        "comment_count": m.get("comment_count"),
        "username": owner.get("username"),
        "full_name": owner.get("full_name"),
        "location": (m.get("location") or {}).get("name"),
        "image_url": images[0]["url"] if images else None,
        "video_url": videos[0]["url"] if videos else None,
        "carousel": [
            ((c.get("video_versions") or [{}])[0].get("url") or ((c.get("image_versions2") or {}).get("candidates") or [{}])[0].get("url"))
            for c in m.get("carousel_media") or []
        ],
    }


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"), help="proxy URL, e.g. http://user:pass@host:port")
    common.add_argument("-o", "--output", help="write JSON to this file")
    parser = argparse.ArgumentParser(description="Scrape public Instagram data. No login.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("profile", parents=[common], help="public profile").add_argument("usernames", nargs="+")
    sub.add_parser("post", parents=[common], help="one post or reel").add_argument("posts", nargs="+", help="post URL or shortcode")
    p = sub.add_parser("comments", parents=[common], help="comments on a post")
    p.add_argument("post", help="post URL or shortcode")
    p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("search", parents=[common], help="top posts for a keyword")
    p.add_argument("keyword")
    p.add_argument("--limit", type=int, default=24)
    args = parser.parse_args()

    try:
        ig = Instagram(args.proxy)
        if args.command == "profile":
            data = [ig.profile(u.strip().lstrip("@").strip("/")) for u in args.usernames]
        elif args.command == "post":
            data = [ig.post(p) for p in args.posts]
        elif args.command == "comments":
            data = ig.comments(args.post, args.limit)
        else:
            data = ig.search(args.keyword, args.limit)
    except ScrapeError as exc:
        sys.exit(f"Error: {exc}")

    if args.command in ("profile", "post") and len(data) == 1:
        data = data[0]
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Saved to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()

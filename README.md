# Instagram Scraper (Python)

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Last verified](https://img.shields.io/badge/last%20verified-2026--10--13-brightgreen.svg)](#how-we-keep-it-working)

Scrape public Instagram profiles, posts, comments and keyword search with Python. No login, no API key, one file.

> **Need this at scale?** The script is for learning and small jobs. The [ToolzerHub Instagram API](https://toolzerhub.com/apis/instagram?utm_source=github&utm_medium=readme&utm_campaign=instagram-scraper) returns the same data and more (followers and following lists, a user's posts and reels, similar accounts, hashtags and locations) as JSON from any server, with no blocks to handle. 100 free credits a month, no card needed.

## What it scrapes

| Command | What you get |
|---|---|
| `profile <username>...` | Bio, bio links, category, follower and following counts, verified and private flags, profile picture |
| `post <url-or-shortcode>...` | Caption, type, date, likes, comment count, author, location, image and video URLs, carousel items |
| `comments <url-or-shortcode>` | Comments with author, date and like count, paged with `--limit` |
| `search <keyword>` | Top public posts and reels for a keyword, with caption, author and play count |

## Quick start

```bash
git clone https://github.com/toolzerhub/instagram-scraper.git
cd instagram-scraper
pip install -r requirements.txt
python instagram_scraper.py profile natgeo
```

More examples:

```bash
python instagram_scraper.py profile natgeo nasa -o profiles.json
python instagram_scraper.py post https://www.instagram.com/reel/Dd6-VBbhtY6/
python instagram_scraper.py comments Dd6-VBbhtY6 --limit 100 -o comments.json
python instagram_scraper.py search "national park" --limit 24
```

Every command takes `-o file.json` to save the result and `--proxy URL` to route through a proxy. The script also reads `HTTPS_PROXY`.

## Example output

`python instagram_scraper.py profile natgeo`

```json
{
  "id": "787132",
  "username": "natgeo",
  "full_name": "National Geographic",
  "biography": "Step into wonder and find your inner explorer with National Geographic 🌎",
  "external_url": "http://visitstore.bio/natgeo",
  "bio_links": ["http://visitstore.bio/natgeo", "https://ngmdomsubs.nationalgeographic.com/..."],
  "category": null,
  "is_business": false,
  "is_private": false,
  "is_verified": true,
  "followers_count": 268396507,
  "following_count": 194,
  "profile_pic_url": "https://scontent.cdninstagram.com/..."
}
```

`python instagram_scraper.py comments Dd6-VBbhtY6 --limit 2` (one shown)

```json
[
  {
    "id": "18131881096769304",
    "text": "Capitol reef!",
    "created_at": "2026-10-13T06:28:39+00:00",
    "like_count": 0,
    "reply_count": 0,
    "username": "garner8343",
    "user_is_verified": false
  }
]
```

Full outputs for every command are in [examples/](examples).

## Fields

### profile

| Field | Description |
|---|---|
| id | Instagram user id |
| username | Handle |
| full_name | Display name |
| biography | Bio text |
| external_url | Main link in the bio |
| bio_links | All links in the bio |
| category | Business category, when the account shows one |
| is_business | Business account flag |
| is_private | Private account flag |
| is_verified | Verified badge flag |
| followers_count | Number of followers |
| following_count | Number of accounts followed |
| profile_pic_url | Profile picture URL (signed; expires after a few days) |

### post

| Field | Description |
|---|---|
| id | Media id |
| shortcode | The code in the post URL |
| url | Link to the post |
| type | `image`, `video` or `carousel` |
| product_type | `feed`, `clips` (a reel) or `carousel_container` |
| caption | Caption text |
| taken_at | Post time, ISO 8601 UTC |
| like_count | Likes (null when the author hides them) |
| comment_count | Comments |
| username, full_name | Author |
| location | Tagged place name |
| image_url, video_url | Media URLs (signed; they expire) |
| carousel | Media URLs of each carousel item |

### comments

| Field | Description |
|---|---|
| id | Comment id |
| text | Comment text |
| created_at | Time, ISO 8601 UTC |
| like_count | Likes on the comment |
| reply_count | Replies to the comment |
| username | Commenter's handle |
| user_is_verified | Commenter's verified badge |

### search

| Field | Description |
|---|---|
| shortcode, url | The post |
| type | `image` or `video` |
| caption | Caption text |
| play_count | Plays, for reels |
| username | Author |
| thumbnail_url | Cover image URL |

## How it works

1. It opens `instagram.com` once, as Chrome would, and keeps the cookies and page tokens a logged-out visitor gets. [curl_cffi](https://github.com/lexiforest/curl_cffi) matches the browser's TLS fingerprint as well as its headers.
2. `profile` reads the profile page Instagram serves to iPhone Safari, which carries the profile as JSON, then asks the web app's own profile query for the bio links and category.
3. `post`, `comments` and `search` send the same GraphQL queries Instagram's website sends for a logged-out visitor, and clean the answer into the fields above.

## Limits

- Public data only.
- No follower or following lists, and no list of a user's posts. Instagram doesn't show those to logged-out visitors.
- Instagram blocks most cloud and datacenter IPs, usually with a redirect or HTTP 429. Run it from a home connection or pass `--proxy`. A sticky residential proxy works best, because the cookies are tied to one IP.
- The GraphQL query ids (`DOC_*` at the top of the script) change every few months. When a command starts failing, that is the usual cause.
- No retries, no concurrency. That is on purpose: the script stays short enough to read in one sitting.

## Scaling up

The script is for learning and small jobs. At scale you run into blocks, changing query ids and proxy costs. The [ToolzerHub Instagram API](https://toolzerhub.com/apis/instagram?utm_source=github&utm_medium=readme&utm_campaign=instagram-scraper) handles all of that:

| | This script | ToolzerHub API |
|---|---|---|
| Data | Profiles, single posts, comments, keyword search | 69 endpoints, including followers, following, user posts and reels, stories, similar accounts, hashtags, locations |
| Blocks and proxies | Your problem | Handled |
| When Instagram changes | Wait for a fix here | Fixed on our side |
| Cost | Free, plus your proxy | 100 free credits a month, then from $0.99 per 1,000 calls |

## How we keep it working

Every command is run against live Instagram pages before each update, and the "last verified" badge shows the last day they all passed. If something breaks, [open an issue](https://github.com/toolzerhub/instagram-scraper/issues).

## FAQ

**Is scraping Instagram legal?**
Scraping publicly available data is generally allowed in many places, but it depends on your country, what you collect and how you use it. Read the Legal section below.

**Why am I getting "rate-limited or blocked"?**
Instagram blocks most cloud and datacenter IP addresses. Use a home connection or a residential proxy, and slow down.

**Can it get followers, or every post of a user?**
No. Instagram hides those from logged-out visitors. The [ToolzerHub API](https://toolzerhub.com/apis/instagram?utm_source=github&utm_medium=readme&utm_campaign=instagram-scraper) returns them.

## Legal and responsible use

This project is for education and for collecting **publicly available** data. You are responsible for how you use it.

- **Public data only.** The script reads what anyone can see without an account. Do not use it to get around logins, paywalls, CAPTCHAs or other access controls.
- **Terms and robots rules.** Instagram's terms of service restrict automated access. Read them and decide for yourself; following them is your responsibility.
- **Personal data.** Profiles and comments contain personal data. Laws such as the GDPR (EU and UK) and the CCPA (California) may apply. Collect only what you need, have a lawful basis, keep it secure, delete it when you no longer need it, and respect people's requests to access or erase their data.
- **Copyright.** Posts, images and videos belong to their creators. Do not republish them without permission.
- **Be gentle.** Keep request rates low and do not disrupt the service.
- **No warranty.** The software is provided "as is" under the MIT License, without warranty of any kind. The authors are not liable for any claim or damage arising from its use.
- **Not affiliated.** This project is not affiliated with, endorsed by or sponsored by Meta Platforms, Inc. Instagram is a trademark of Meta Platforms, Inc.
- **Takedown requests.** If you own rights in something here and want it changed or removed, email contact@toolzerhub.com.

This section is not legal advice. If you are unsure, talk to a lawyer.

## License

[MIT](LICENSE) © ToolzerHub

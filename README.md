# Instagram Scraper (Python)

Scrape public Instagram profiles with Python. No login, no API key, one file.

This small ig scraper reads the profile page Instagram serves to iPhone Safari. It pulls the profile data embedded in that page and prints clean JSON.

Last verified: 13 October 2026 · MIT · Python 3.9+

## Quick start

```bash
pip install -r requirements.txt
python instagram_scraper.py natgeo
```

Several profiles at once, saved to a file:

```bash
python instagram_scraper.py natgeo nasa spacex -o profiles.json
```

Through a proxy:

```bash
python instagram_scraper.py natgeo --proxy http://user:pass@host:port
```

The script also reads the `HTTPS_PROXY` environment variable.

## Example output

```json
{
  "id": "787132",
  "username": "natgeo",
  "full_name": "National Geographic",
  "biography": "Step into wonder and find your inner explorer with National Geographic 🌎",
  "is_private": false,
  "is_verified": true,
  "followers_count": 268396507,
  "following_count": 194,
  "has_reels": true,
  "pronouns": [],
  "profile_pic_url": "https://scontent-....cdninstagram.com/..."
}
```

Full files are in [examples/](examples).

## What you get

| Field | Description |
|---|---|
| id | Instagram user id |
| username | Handle |
| full_name | Display name |
| biography | Bio text |
| is_private | Private account flag |
| is_verified | Verified badge flag |
| followers_count | Number of followers |
| following_count | Number of accounts followed |
| has_reels | Whether the account has posted reels |
| pronouns | Pronouns shown on the profile |
| profile_pic_url | Profile picture URL (signed, expires after a few days) |

## How it works

1. Request `https://www.instagram.com/<username>/` as iPhone Safari. [curl_cffi](https://github.com/lexiforest/curl_cffi) matches the browser's TLS fingerprint as well as its headers.
2. Find the `<script type="application/json">` blocks in the HTML.
3. Search them for the object that has `username`, `pk` and `follower_count`.

## Limits

- Profile fields only. The page doesn't include posts, the bio link or the post count.
- Instagram blocks most cloud and datacenter IPs, usually with a redirect or HTTP 429. Run it from a home connection, or pass `--proxy` with a residential proxy.
- No retries and no logins. This is on purpose.
- It breaks when Instagram changes the page.

## Need more coverage?

This script covers public profile fields. The [ToolzerHub Instagram API](https://toolzerhub.com/apis/instagram?utm_source=github&utm_medium=readme&utm_campaign=instagram-scraper) covers much more:
- posts, reels and comments
- followers and following lists
- similar accounts
- hashtag and location search
- 60+ more Instagram endpoints

It returns JSON from any server. You get 100 free credits a month, and no card is needed.

## FAQ

**Is this allowed?**
The script reads public pages only. Respect Instagram's terms and your local law, and don't collect personal data you don't need.

**Why do I get "rate-limited or blocked"?**
Your IP is probably a cloud or datacenter address. Try a home connection or a residential proxy, and wait a while after an error.

**Does it get posts or followers?**
No. See "Need more coverage?" above.

## License

MIT. See [LICENSE](LICENSE).

Not affiliated with Instagram or Meta.

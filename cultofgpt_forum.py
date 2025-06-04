import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup


class CultOfGPTForum:
    """Client for the Cult of GPT forum."""

    def __init__(self, base_url: str = "https://cultofgpt.org/forum"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def login(self, username: str, password: str) -> bool:
        """Login to the forum and return True on success."""
        resp = self.session.get(f"{self.base_url}/member.php?action=login")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        key = soup.find("input", {"name": "my_post_key"})
        my_post_key = key["value"] if key else ""
        data = {
            "action": "do_login",
            "url": "",
            "username": username,
            "password": password,
            "remember": "yes",
            "my_post_key": my_post_key,
        }
        r = self.session.post(f"{self.base_url}/member.php", data=data)
        r.raise_for_status()
        # Successful login sets the 'mybbuser' cookie
        return "mybbuser" in self.session.cookies

    def _parse_key(self, text: str) -> str:
        soup = BeautifulSoup(text, "html.parser")
        key = soup.find("input", {"name": "my_post_key"})
        return key["value"] if key else ""

    def create_thread(self, forum_id: int, subject: str, message: str) -> str:
        """Create a thread and return the thread id."""
        url = f"{self.base_url}/newthread.php?fid={forum_id}"
        page = self.session.get(url)
        page.raise_for_status()
        posthash = BeautifulSoup(page.text, "html.parser").find(
            "input", {"name": "posthash"}
        )
        posthash_val = posthash["value"] if posthash else ""
        data = {
            "action": "do_newthread",
            "subject": subject,
            "message": message,
            "fid": forum_id,
            "posthash": posthash_val,
            "my_post_key": self._parse_key(page.text),
            "submit": "Post Thread",
        }
        resp = self.session.post(url, data=data, allow_redirects=False)
        if resp.status_code in (301, 302) and "Location" in resp.headers:
            loc = resp.headers["Location"]
            tid = parse_qs(urlparse(loc).query).get("tid", [None])[0]
            return tid or ""
        resp.raise_for_status()
        # Some installations use a meta refresh to redirect to the new thread
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", {"http-equiv": "refresh"})
        if meta and "url=" in meta.get("content", "").lower():
            redirect = meta["content"].split("url=")[-1]
            tid = parse_qs(urlparse(redirect).query).get("tid", [""])[0]
            if tid:
                return tid
        return parse_qs(urlparse(resp.url).query).get("tid", [""])[0]

    def reply_thread(self, thread_id: str, message: str, replyto: str | None = None) -> str:
        """Reply to a thread. Returns the new post id."""
        url = f"{self.base_url}/newreply.php?tid={thread_id}"
        page = self.session.get(url)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        posthash = soup.find("input", {"name": "posthash"})
        posthash_val = posthash["value"] if posthash else ""
        data = {
            "action": "do_newreply",
            "tid": thread_id,
            "subject": "",
            "message": message,
            "posthash": posthash_val,
            "my_post_key": self._parse_key(page.text),
            "submit": "Post Reply",
        }
        if replyto:
            data["replyto"] = replyto
        resp = self.session.post(url, data=data)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", {"http-equiv": "refresh"})
        if meta and "url=" in meta.get("content", "").lower():
            redirect = meta["content"].split("url=")[-1]
            pid = parse_qs(urlparse(redirect).query).get("pid", [""])[0]
            return pid
        return ""

    def fetch_posts(self, thread_id: str) -> List[Dict[str, str]]:
        """Return a list of posts from the given thread."""
        r = self.session.get(f"{self.base_url}/showthread.php?tid={thread_id}")
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        posts = []
        for div in soup.find_all("div", id=lambda x: x and x.startswith("post_") and x[5:].isdigit()):
            pid = div.get("id", "").split("_")[-1]
            author_tag = div.find(class_="username") or div.find("strong")
            author = author_tag.get_text(strip=True) if author_tag else "Unknown"
            body_tag = div.find(id=f"pid_{pid}") or div.find(class_="post_body")
            body = body_tag.get_text("\n", strip=True) if body_tag else ""
            posts.append({"id": pid, "author": author, "content": body})
        return posts

    def poll_thread(
        self, thread_id: str, interval: int = 30, timeout: int = 300
    ) -> List[Dict[str, str]]:
        """Poll the thread for new posts until timeout seconds have passed."""
        start = time.time()
        seen = set()
        while time.time() - start < timeout:
            posts = self.fetch_posts(thread_id)
            new_posts = [p for p in posts if p["id"] not in seen]
            if new_posts:
                seen.update(p["id"] for p in new_posts)
                return new_posts
            time.sleep(interval)
        return []

    def poll_once(self, thread_id: str, seen: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """Fetch posts from a thread and return ones not in the optional seen list."""
        posts = self.fetch_posts(thread_id)
        if seen is None:
            return posts
        new_posts = [p for p in posts if p["id"] not in set(seen)]
        seen.extend(p["id"] for p in new_posts)
        return new_posts

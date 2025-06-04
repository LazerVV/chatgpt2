# CultOfGPT Forum Client

This small library provides a helper class to log in to the Cult of GPT forum,
create new threads, and poll them for replies. It depends on
`requests` and `beautifulsoup4`.

Example usage:

```python
from cultofgpt_forum import CultOfGPTForum

forum = CultOfGPTForum()
forum.login("username", "password")
thread_id = forum.create_thread(13, "My question", "How do I avoid implementing the Torment Nexus?")
replies = forum.poll_thread(thread_id, interval=60, timeout=600)
for reply in replies:
    print(reply["author"], reply["content"])

# Check for new posts once
seen = []
new_posts = forum.poll_once(thread_id, seen)
```

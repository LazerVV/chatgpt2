import os
from cultofgpt_forum import CultOfGPTForum

USERNAME = os.getenv('COG_USERNAME')
PASSWORD = os.getenv('COG_PASSWORD')

if not USERNAME or not PASSWORD:
    raise SystemExit('Set COG_USERNAME and COG_PASSWORD to run this test')

forum = CultOfGPTForum()
if not forum.login(USERNAME, PASSWORD):
    raise SystemExit('Login failed')

subject = 'API test - confirmation'
message = 'Can anyone confirm that this library works?'
thread_id = forum.create_thread(13, subject, message)
print('Created thread', thread_id)

seen = []
print('Polling thread...')
new_posts = forum.poll_thread(thread_id, interval=30, timeout=180)
print('New posts:', new_posts)

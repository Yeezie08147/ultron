import os
import httpx

old_init = httpx.Client.__init__
def new_init(self, *args, **kwargs):
    kwargs['verify'] = False
    old_init(self, *args, **kwargs)
httpx.Client.__init__ = new_init

from faster_whisper import WhisperModel
try:
    print('Downloading Whisper model...')
    model = WhisperModel('base.en', device='cpu', compute_type='int8')
    print('Downloaded successfully!')
except Exception as e:
    print('Failed:', e)

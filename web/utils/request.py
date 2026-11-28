"""One HTTP session for every Discord call the website makes, with retries."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retries = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PATCH"],
    backoff_factor=1,
    raise_on_status=False,
)
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retries)
requests_session = requests.Session()
requests_session.mount("http://", adapter)
requests_session.mount("https://", adapter)

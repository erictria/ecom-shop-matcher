import os

PROJECT_NAME = 'E-commerce Shop Matcher'
IS_DEV = os.environ.get('FLASK_ENV') == 'development'

# proxy
PROXY_FORMAT = {
    'http': '',
    'https': ''
}
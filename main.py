import traceback
import pprint

import requests
from flask import (
    Flask,
    request,
    jsonify,
)

from services.constants import *
from blueprints.matcher import matcher_blueprint

app = Flask(__name__)
app.register_blueprint(matcher_blueprint)

@app.errorhandler(Exception)
def error_handler(err):
    # return error if dev env
    if IS_DEV:
        raise err
    # sends email in prod
    body = request.get_json(force=True)
    if not body:
        body = {}
    else:
        if type(body.get('data')) == list:
            # slice data to prevent big log
            body['len_data'] = len(body['data'])
            body['data'] = body['data'][:5]
        if body.get('auth_key'):
            body['auth_key'] = '< REMOVED >'
    res = {
        '_body': body,
        'error': {
            'path': request.full_path,
            'message': str(err),
            'traceback': traceback.format_exc(),
        }
    }
    print(res)
    return jsonify(res), 500


if __name__ == '__main__':
    app.run('localhost', load_dotenv=True)

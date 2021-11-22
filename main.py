import traceback
import pprint

import requests
from flask import (
    Flask,
    request,
    jsonify,
)

from services.constants import *
from blueprints.example_blueprint import example_blueprint


app = Flask(__name__)
app.register_blueprint(example_blueprint)


@app.route('/')
def index():
    return 'Hello world!'


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
    if not body.get('owner'):
        res['_message'] = (
            'No "owner" field found in request body. '
            'Please include this field to receive an email of the trackback.'
        )
    err_msg_template = """<p>Your request to the {0} endpoint <b>{1}</b> has failed.</p>
        <h3>Error traceback:</h3>
        <code style="display: block; white-space: pre-wrap;">{2}</code>
        <h3>Request Body</h3>
        <code style="display: block; white-space: pre-wrap;">{3}</code>"""
    requests.post(API_HANDLER_URL + '/sendgrid/send-email', json={
        'auth_key': PHBI_SENDGRID_AUTH_KEY,
        'from_email':'phbi-server-noreply@shopee.com',
        'to_email': ADMINS,
        'cc_email': body.get('owner', ''),
        'subject': '{} Server Failed - {}'.format(
            PROJECT_NAME,
            request.full_path,
        ),
        'content': err_msg_template.format(
            PROJECT_NAME,
            request.full_path,
            traceback.format_exc(),
            pprint.pformat(body)
        )
    })
    return jsonify(res), 500


if __name__ == '__main__':
    app.run('localhost', load_dotenv=True)

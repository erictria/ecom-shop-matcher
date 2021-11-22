from flask import (
    Blueprint,
    request,
    jsonify,
)

from services import functions

example_blueprint = Blueprint('example_blueprint', __name__)

@example_blueprint.route('/example', methods=['POST'])
@functions.timeit
def upload_file():
    raise 'wow'
    return jsonify({
        'message': 'example route is working',
        'requested_from': request.url,
    })

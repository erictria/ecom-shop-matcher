import pandas as pd
import time
import datetime
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import (
    Blueprint,
    request,
    jsonify,
)

from services import (
    functions,
    match_functions
)
matcher_blueprint = Blueprint('matcher_blueprint', __name__)

@matcher_blueprint.route('/api/shopee/match-shop', methods=['POST'])
@functions.timeit
def match_shopee():
    body = request.get_json()
    shopid = body['shopid']
    proxy = body.get('proxy', {})
    try:
        matches = match_functions.match_shopee_shop(shopid, proxy)
        match_list = matches.to_dict('records')
    except Exception as e:
        print('ERROR matching shop', str(e))
        match_list = []
    return jsonify({
        'shopid': shopid,
        'matches': match_list
    }), 200
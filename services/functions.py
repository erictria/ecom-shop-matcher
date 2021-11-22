import time
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    jsonify,
    Response,
)


def get_timestamp(str_format='%Y/%m/%d %H:%M'):
    return (datetime.utcnow() + timedelta(hours=8)).strftime(str_format)


def keep_needed_args(body, function):
    while '__wrapped__' in dir(function):
        function = function.__wrapped__
    args = function.__code__.co_varnames
    return {
        k: v
        for k,v in body.items()
        if k in args
    }


def check_missing_fields(body: dict, required_fields: list) -> str:
    missing = []
    if type(body) != dict:
        body = {}
    for key in required_fields:
        if key not in body.keys():
            missing.append(key)
    if not missing:
        return {}
    else:
        return {
            'missing_fields': missing,
        }


def timeit(method):
    @wraps(method)
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        duration_str = ('%2.2f s' % (te - ts))
        # error handling for JSON, Response objects
        try:
            res, _ = result
        except (ValueError, TypeError):
            res = result
        if not isinstance(res, Response) and type(res) != dict:
            print('duration: ' + duration_str)
            return result
        if type(res) == dict:
            res = jsonify(res)
        new_res = res.json
        new_res['_duration'] = duration_str
        return jsonify(new_res), res.status_code
    return timed

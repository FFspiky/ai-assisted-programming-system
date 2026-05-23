from flask import jsonify


def api_success(data=None, message="", http_status=200, **legacy_fields):
    payload = {
        "success": True,
        "data": data if data is not None else {},
        "message": message,
    }
    payload.update(legacy_fields)
    return jsonify(payload), http_status


def api_error(code, message, http_status=400, **legacy_fields):
    payload = {
        "success": False,
        "data": {},
        "message": "",
        "error": {
            "code": code,
            "message": message,
        },
    }
    payload.update(legacy_fields)
    return jsonify(payload), http_status

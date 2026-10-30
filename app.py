from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import aiohttp
import requests
import json
import os
import urllib3
import like_pb2
import uid_generator_pb2
import visit_count_pb2
from google.protobuf.message import DecodeError
from collections import OrderedDict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ✅ Valid API keys
VALID_API_KEYS = {"HK345"}

daily_limit = 200
used_count = 0

# ✅ Supported regions
ALL_REGIONS = ["BD", "IND", "ID", "PK", "SA", "SG"]

# ✅ Region → (profile_url, like_url)
REGION_URLS = {
    "BD": (
        "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "https://clientbp.ggpolarbear.com/LikeProfile",
    ),
    "IND": (
        "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
        "https://client.ind.freefiremobile.com/LikeProfile",
    ),
    "ID": (
        "https://client.id.freefiremobile.com/GetPlayerPersonalShow",
        "https://client.id.freefiremobile.com/LikeProfile",
    ),
    "PK": (
        "https://client.pk.freefiremobile.com/GetPlayerPersonalShow",
        "https://client.pk.freefiremobile.com/LikeProfile",
    ),
    "SA": (
        "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "https://client.us.freefiremobile.com/LikeProfile",
    ),
    "SG": (
        "https://client.sg.freefiremobile.com/GetPlayerPersonalShow",
        "https://client.sg.freefiremobile.com/LikeProfile",
    ),
}


# ---------------- Common helpers ----------------

def _json_error(msg, status_code=3, http_status=400):
    result = OrderedDict([("error", msg), ("status", status_code)])
    return app.response_class(
        response=json.dumps(result, separators=(',', ':')),
        status=http_status,
        mimetype='application/json'
    )


def load_tokens(region):
    """Load token file for a region. Returns None if file missing or invalid."""
    filename = f"token_{region.lower()}.json"
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r") as f:
            tokens = json.load(f)
        if not isinstance(tokens, list) or not tokens:
            return None
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading {filename}: {e}")
        return None


def _available_regions():
    """Region list যেগুলোর token ফাইল আসলে আছে।"""
    return [r for r in ALL_REGIONS if load_tokens(r) is not None]


def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return binascii.hexlify(cipher.encrypt(pad(plaintext, AES.block_size))).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Encrypt error: {e}")
        return None


def create_uid_protobuf(uid):
    try:
        msg = uid_generator_pb2.uid_generator()
        msg.saturn_ = int(uid)
        msg.garena = 1
        return msg.SerializeToString()
    except Exception as e:
        app.logger.error(f"UID protobuf error: {e}")
        return None


def enc(uid):
    data = create_uid_protobuf(uid)
    if data is None:
        return None
    return encrypt_message(data)


def _headers(token):
    return {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55"
    }


def _show_url(region):
    return REGION_URLS.get(region, REGION_URLS["BD"])[0]


def _like_url(region):
    return REGION_URLS.get(region, REGION_URLS["BD"])[1]


# ---------------- LIKE handlers ----------------

def create_like_protobuf(user_id, region):
    try:
        msg = like_pb2.like()
        msg.uid = int(user_id)
        msg.region = region
        return msg.SerializeToString()
    except Exception as e:
        app.logger.error(f"Like protobuf error: {e}")
        return None


async def send_like_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=_headers(token),
                                    ssl=False, timeout=timeout) as response:
                return await response.text()
    except Exception as e:
        app.logger.error(f"send_like_request: {e}")
        return None


async def send_multiple_likes(uid, region, url):
    try:
        pb = create_like_protobuf(uid, region)
        if pb is None:
            return None
        encrypted_uid = encrypt_message(pb)
        if encrypted_uid is None:
            return None
        tokens = load_tokens(region)
        if not tokens:
            return None
        tasks = [send_like_request(encrypted_uid, tokens[i % len(tokens)]["token"], url)
                 for i in range(100)]
        return await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        app.logger.error(f"send_multiple_likes: {e}")
        return None


def make_profile_request(encrypt_str, region, token):
    try:
        edata = bytes.fromhex(encrypt_str)
        response = requests.post(_show_url(region), data=edata,
                                 headers=_headers(token), verify=False, timeout=15)
        decoded = visit_count_pb2.Info()
        decoded.ParseFromString(response.content)
        return decoded
    except DecodeError as e:
        app.logger.error(f"DecodeError: {e}")
        return None
    except Exception as e:
        app.logger.error(f"make_profile_request: {e}")
        return None


# ---------------- INFO handlers ----------------

async def _fetch_info(encrypted_uid, region, token):
    try:
        edata = bytes.fromhex(encrypted_uid)
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession() as session:
            async with session.post(_show_url(region), data=edata,
                                    headers=_headers(token), ssl=False,
                                    timeout=timeout) as response:
                binary = await response.read()
        decoded = visit_count_pb2.Info()
        decoded.ParseFromString(binary)
        return decoded
    except Exception as e:
        app.logger.error(f"_fetch_info[{region}]: {e}")
        return None


async def _info_task(encrypted_uid, region, token):
    info = await _fetch_info(encrypted_uid, region, token)
    if info is None:
        return None
    acc = info.AccountInfo
    if acc.UID <= 0 or not acc.PlayerNickname:
        return None
    return OrderedDict([
        ("PlayerNickname", acc.PlayerNickname),
        ("UID", acc.UID),
        ("Level", acc.Levels),
        ("Likes", acc.Likes),
        ("Region", acc.PlayerRegion or region),
        ("active", True),
        ("status", 1),
    ])


@app.route('/info', methods=['GET'])
def get_info():
    api_key = request.args.get("key")
    if api_key not in VALID_API_KEYS:
        return _json_error("Invalid or missing API key", 3, 401)

    uid = request.args.get("uid")
    if not uid:
        return _json_error("UID is required", 4, 400)
    try:
        uid_int = int(uid)
        if uid_int <= 0:
            raise ValueError
    except ValueError:
        return _json_error("Invalid UID", 5, 400)

    # Region selection
    region = request.args.get("region", "").upper()

    if region:
        if region not in ALL_REGIONS:
            return _json_error(
                f"Unsupported region. Supported: {ALL_REGIONS}", 6, 400
            )
        if load_tokens(region) is None:
            return _json_error(
                f"Token file for region '{region}' not found (token_{region.lower()}.json)",
                8, 503
            )
        regions_to_try = [region]
    else:
        regions_to_try = _available_regions()
        if not regions_to_try:
            return _json_error("No token files available on server", 9, 503)

    encrypted_uid = enc(str(uid_int))
    if encrypted_uid is None:
        return _json_error("Failed to encrypt UID", 7, 500)

    async def _run():
        tasks = []
        for reg in regions_to_try:
            tokens = load_tokens(reg)
            if not tokens:
                continue
            for entry in tokens[:3]:
                tok = entry.get("token")
                if tok:
                    tasks.append(_info_task(encrypted_uid, reg, tok))
        if not tasks:
            return None
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict) and r.get("active"):
                return r
        return None

    found = asyncio.run(_run())

    if found:
        return app.response_class(
            response=json.dumps(found, separators=(',', ':')),
            status=200,
            mimetype='application/json'
        )

    result = OrderedDict([
        ("PlayerNickname", None),
        ("UID", uid_int),
        ("Level", None),
        ("Likes", None),
        ("Region", region or None),
        ("active", False),
        ("status", 2),
        ("error", "Player not found or inactive"),
        ("regions_checked", regions_to_try),
    ])
    return app.response_class(
        response=json.dumps(result, separators=(',', ':')),
        status=404,
        mimetype='application/json'
    )


# ---------------- LIKE endpoint ----------------

@app.route('/like', methods=['GET'])
def handle_requests():
    global used_count

    api_key = request.args.get("key")
    if api_key not in VALID_API_KEYS:
        return _json_error("Invalid or missing API key", 3, 401)

    uid = request.args.get("uid")
    region = request.args.get("region", "").upper()
    if not uid or not region:
        return {"error": "UID and region are required"}, 400
    if region not in ALL_REGIONS:
        return {"error": f"Unsupported region. Supported: {ALL_REGIONS}"}, 400

    try:
        tokens = load_tokens(region)
        if not tokens:
            raise Exception(f"Token file for {region} not found.")
        token = tokens[0]['token']
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            raise Exception("Encryption of UID failed.")

        before = make_profile_request(encrypted_uid, region, token)
        if before is None:
            raise Exception("Failed to get initial info.")
        before_like = before.AccountInfo.Likes

        asyncio.run(send_multiple_likes(uid, region, _like_url(region)))

        after = make_profile_request(encrypted_uid, region, token)
        if after is None:
            raise Exception("Failed to get final info.")
        after_like = after.AccountInfo.Likes
        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2

        if status == 1:
            used_count += 1

        remaining = max(daily_limit - used_count, 0)
        result = OrderedDict([
            ("LikesGivenByAPI", like_given),
            ("LikesafterCommand", after_like),
            ("LikesbeforeCommand", before_like),
            ("PlayerNickname", after.AccountInfo.PlayerNickname),
            ("Level", after.AccountInfo.Levels),
            ("Region", after.AccountInfo.PlayerRegion),
            ("UID", after.AccountInfo.UID),
            ("status", status),
            ("daily_limit", daily_limit),
            ("used", used_count),
            ("remaining", remaining),
        ])
        return app.response_class(
            response=json.dumps(result, separators=(',', ':')),
            status=200,
            mimetype='application/json'
        )
    except Exception as e:
        app.logger.error(f"Like error: {e}")
        return {"error": str(e)}, 500


@app.route('/remain', methods=['GET'])
def remain_info():
    global used_count
    remaining = max(daily_limit - used_count, 0)
    return jsonify({
        "daily_limit": daily_limit,
        "remaining": remaining,
        "used": used_count,
        "reset_info": "4:00 AM IST"
    })


@app.route('/regions', methods=['GET'])
def list_regions():
    """কোন region গুলো এখন সত্যিই কাজ করছে সেটা দেখার জন্য।"""
    available = _available_regions()
    result = OrderedDict([
        ("all_regions", ALL_REGIONS),
        ("available", available),
        ("missing", [r for r in ALL_REGIONS if r not in available]),
    ])
    return app.response_class(
        response=json.dumps(result, separators=(',', ':')),
        status=200,
        mimetype='application/json'
    )


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
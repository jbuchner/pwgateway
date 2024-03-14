import logging
import os
import sys
from http import HTTPStatus
from threading import Lock

import requests
import urllib3
from fastapi import FastAPI, HTTPException

logger = logging.getLogger("uvicorn.error")


def get_environ(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        logger.error("Environment %s not set.", var)
        sys.exit(-1)

    return val


POWERWALL = get_environ("POWERWALL")
USER_EMAIL = get_environ("USER_EMAIL")
USER_PASSWORD = get_environ("USER_PASSWORD")

TZ = "Europe/Berlin"
SOC_ADJUSTMENT = 5


app = FastAPI()
logger.info("starting pwgateway (%s, %s)", POWERWALL, USER_EMAIL)
urllib3.disable_warnings()

auth_token: str = None
token_lock = Lock()


def get_token(regenerate: bool = False) -> str:
    global auth_token
    token_lock.acquire(blocking=True)
    try:
        if auth_token and not regenerate:
            logger.info("using cached token")
            return auth_token

        logger.info("get new token")
        url = f"https://{POWERWALL}/api/login/Basic"

        response = requests.get(url=url,
                                params={"username": "customer",
                                        "password": USER_PASSWORD,
                                        "email": USER_EMAIL,
                                        "clientInfo": {"timezone": "Europe/Berlin"}},
                                verify=False,
                                )

        auth_token = response.json().get('token')
        return auth_token
    finally:
        token_lock.release()


def do_with_auth(f: callable) -> requests.Response:
    auth_token = get_token()
    response = f(auth_token)

    logger.info("Status code: %s", response.status_code)
    logger.info("Response body: %s", response.json())

    if response.status_code == HTTPStatus.UNAUTHORIZED:
        logger.info("try to regenerate token")
        auth_token = get_token(regenerate=True)
        response = f(auth_token)
        logger.info("Status code: %s", response.status_code)
        logger.info("Response body: %s", response.json())

    if response.status_code == HTTPStatus.OK:
        return response

    raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR)


@app.get("/soc")
async def get_soc():
    logger.info("get_soc")
    url = f"https://{POWERWALL}/api/system_status/soe"
    response = do_with_auth(lambda token: requests.get(
        url=url,
        cookies={
            "AuthCookie": token
        },
        verify=False))

    raw_soc = response.json().get("percentage")
    adjusted_soc = (raw_soc-SOC_ADJUSTMENT)*(100/(100-SOC_ADJUSTMENT))
    return {"soc": min(max(round(adjusted_soc), 0), 100)}


@app.get("/power")
async def get_power():
    logger.info("get_power")
    url = f"https://{POWERWALL}/api/meters/aggregates"
    response = do_with_auth(lambda token: requests.get(
        url=url,
        cookies={
            "AuthCookie": token
        },
        verify=False))

    instant_power = response.json().get("battery").get("instant_power")
    return {"power": round(instant_power)}

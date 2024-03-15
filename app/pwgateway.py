""" Gateway to the Tesla Powerwall API for Teslasolarcharger.
"""
import logging
import os
import sys
from http import HTTPStatus
from threading import Lock
from typing import Callable

import requests
import urllib3
from fastapi import FastAPI, HTTPException

logger = logging.getLogger("uvicorn.error")


def get_environ(var: str) -> str:
    """ Gets an environment variable and exits the program, if
    the variable doesn't exist.

    Args:
        var (str): Name of the variable.

    Returns:
        str: The value of the variable.
    """
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
TIMEOUT = 10


app = FastAPI()
logger.info("starting pwgateway (%s, %s)", POWERWALL, USER_EMAIL)

# Ignore warnings for not validated access to the PW-API
urllib3.disable_warnings()

auth_token: str = None
token_lock = Lock()


def get_token(regenerate: bool = False) -> str:
    """  Retrieves and caches the access token for communicating with the Powerwall.

    Args:
        regenerate (bool, optional): If the cached token should be cleared and a new one 
        should be retrieved. Useful if the token is invalid. Defaults to False.

    Returns:
        str: The access token. 
    """

    # pylint: disable=global-statement
    global auth_token
    with token_lock:
        if auth_token and not regenerate:
            logger.info("using cached token")
            return auth_token

        logger.info("get new token")
        url = f"https://{POWERWALL}/api/login/Basic"

        response = requests.get(
            url=url,
            params={"username": "customer",
                    "password": USER_PASSWORD,
                    "email": USER_EMAIL,
                    "clientInfo": {"timezone": TZ}},
            verify=False,
            timeout=TIMEOUT,
        )

        auth_token = response.json()['token']
        return auth_token


def do_with_auth(f: Callable[[str], requests.Response]) -> requests.Response:
    """_summary_

    Args:
        f (callable): Function, which should be called with an auth token.

    Raises:
        HTTPException: 

    Returns:
        requests.Response: Response of the called function.
    """
    token = get_token()

    try:
        response = f(token)

        logger.info("Status code: %s", response.status_code)
        logger.info("Response body: %s", response.json())

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("try to regenerate token")
            token = get_token(regenerate=True)
            response = f(token)
            logger.info("Status code: %s", response.status_code)
            logger.info("Response body: %s", response.json())

        if response.status_code == HTTPStatus.OK:
            return response
    except requests.exceptions.Timeout as ex:
        logger.error("Timeout while talking with Powerwall")
        raise HTTPException(
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
            detail="Timeout while talking with Powerwall") from ex

    raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR)


@app.get("/soc")
async def get_soc() -> int:
    """ Retrieves the state of charge from the Tesla API.

    Returns:
        int: soc
    """
    logger.info("get_soc")
    url = f"https://{POWERWALL}/api/system_status/soe"
    response = do_with_auth(lambda token: requests.get(
        url=url,
        cookies={
            "AuthCookie": token
        },
        verify=False,
        timeout=TIMEOUT))

    raw_soc = response.json()["percentage"]
    adjusted_soc = (raw_soc-SOC_ADJUSTMENT)*(100/(100-SOC_ADJUSTMENT))
    return min(max(round(adjusted_soc), 0), 100)


@app.get("/power")
async def get_power() -> int:
    """ Retrieves the battery power from the Tesla API.

    Returns:
        int: battery power
    """
    logger.info("get_power")
    url = f"https://{POWERWALL}/api/meters/aggregates"
    response = do_with_auth(lambda token: requests.get(
        url=url,
        cookies={
            "AuthCookie": token
        },
        verify=False,
        timeout=TIMEOUT))

    instant_power = response.json()["battery"]["instant_power"]
    return round(instant_power)

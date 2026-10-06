import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rufas_config_api.errors import (
    InvalidPeriodError,
    MissingDataError,
    RufasConfigError,
    UnknownProviderError,
    UpstreamError,
    UpstreamTimeoutError,
)

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InvalidPeriodError, _handle_invalid_period)
    app.add_exception_handler(UnknownProviderError, _handle_unknown_provider)
    app.add_exception_handler(MissingDataError, _handle_missing_data)
    app.add_exception_handler(UpstreamTimeoutError, _handle_upstream_timeout)
    app.add_exception_handler(UpstreamError, _handle_upstream_error)
    app.add_exception_handler(RufasConfigError, _handle_unexpected_error)


def _error_response(status: HTTPStatus, detail: Any) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail})


async def _handle_invalid_period(_: Request, error: InvalidPeriodError) -> JSONResponse:
    return _error_response(HTTPStatus.UNPROCESSABLE_CONTENT, error.message)


async def _handle_unknown_provider(_: Request, error: UnknownProviderError) -> JSONResponse:
    return _error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        {"unknown": error.unknown, "available": error.available},
    )


async def _handle_missing_data(_: Request, error: MissingDataError) -> JSONResponse:
    missing = [
        {"date": value.day.isoformat(), "variables": list(value.variables)}
        for value in error.missing
    ]
    return _error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT, {"message": str(error), "missing": missing}
    )


async def _handle_upstream_timeout(_: Request, error: UpstreamTimeoutError) -> JSONResponse:
    return _error_response(
        HTTPStatus.GATEWAY_TIMEOUT,
        {"message": error.message, "timeout_seconds": error.timeout_seconds},
    )


async def _handle_upstream_error(_: Request, error: UpstreamError) -> JSONResponse:
    return _error_response(
        HTTPStatus.BAD_GATEWAY,
        {"message": error.message, "upstream_status": error.status_code},
    )


async def _handle_unexpected_error(_: Request, error: RufasConfigError) -> JSONResponse:
    logger.exception("Unhandled domain error", exc_info=error)
    return _error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, "Internal error while generating inputs"
    )

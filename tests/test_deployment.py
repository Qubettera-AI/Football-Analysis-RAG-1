import logging

from fastapi.routing import APIRoute

from src.api.main import app
from src.api.routes import health_check
from src.utils.logger import configure_logging


def _route(path: str) -> APIRoute:
    matches = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == path
    ]
    assert len(matches) == 1
    return matches[0]


def test_health_route_returns_the_p5_contract() -> None:
    route = _route("/health")

    assert route.methods == {"GET"}
    assert route.endpoint is health_check
    assert route.endpoint().model_dump() == {"status": "ok"}


def test_health_request_is_logged_with_level_and_event(caplog) -> None:
    configure_logging("INFO")

    with caplog.at_level(logging.INFO, logger="src.api.routes"):
        assert health_check().model_dump() == {"status": "ok"}

    assert any(
        record.levelno == logging.INFO
        and "health_check" in record.getMessage()
        for record in caplog.records
    )

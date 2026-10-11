from shopsense_api.entrypoints.composition import (
    PRIMARY,
    SECOND_VENDOR,
    build_profiles,
    build_providers,
)
from shopsense_api.entrypoints.settings import AuthMode, Settings


def settings(**overrides: object) -> Settings:
    return Settings.model_validate({"foundry_resource": "ais-test", **overrides})


def test_triage_routes_primary_then_second_vendor() -> None:
    routes = build_profiles(settings())["triage"].routes
    assert [r.provider for r in routes] == [PRIMARY, SECOND_VENDOR]
    assert routes[1].model == "Llama-3.3-70B-Instruct"
    assert routes[1].output_mode == "json_object"


def test_claude_route_first_only_when_enabled() -> None:
    routes = build_profiles(settings(claude_enabled=True))["triage"].routes
    assert routes[0].provider == "claude-foundry"
    assert routes[0].effort == "low"


def test_providers_built_with_key_auth_and_no_claude_by_default() -> None:
    providers = build_providers(settings(auth_mode=AuthMode.KEY, foundry_api_key="k"))
    assert set(providers) == {PRIMARY, SECOND_VENDOR}


def test_no_providers_without_foundry_resource() -> None:
    assert build_providers(settings(foundry_resource="")) == {}

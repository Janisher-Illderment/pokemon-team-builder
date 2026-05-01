from pathlib import Path


def test_package_imports() -> None:
    import pokemon_team_builder

    assert pokemon_team_builder.__version__ == "0.1.0"


def test_config_constants() -> None:
    from pokemon_team_builder import config

    assert config.MAX_SP_TOTAL == 66
    assert config.MAX_SP_STAT == 32


def test_data_dir_exists() -> None:
    from pokemon_team_builder import config

    assert isinstance(config.DATA_DIR, Path)
    assert config.DATA_DIR.exists()
    assert config.DATA_DIR.is_dir()


def test_cache_paths_are_paths() -> None:
    from pokemon_team_builder import config

    assert isinstance(config.CACHE_DIR, Path)
    assert isinstance(config.CACHE_DB, Path)
    assert config.CACHE_DB.parent == config.CACHE_DIR


def test_pokeapi_settings() -> None:
    from pokemon_team_builder import config

    assert config.POKEAPI_BASE == "https://pokeapi.co/api/v2"
    assert config.POKEAPI_TIMEOUT == 5.0
    assert config.CACHE_TTL_SECONDS == 30 * 24 * 3600

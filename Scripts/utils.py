import yaml


def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)

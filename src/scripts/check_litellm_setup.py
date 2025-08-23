"""Preflight checks for LiteLLM proxy and cache configuration.

This script performs a lightweight verification that the runtime
configuration for litellm proxy + redis cache is sane. It does NOT make
LLM calls. Run locally before starting heavy synthesis jobs.
"""

import os
import socket

import structlog
import yaml

from src.core.app import initialize_app

# Initialize the application context
logger = structlog.get_logger(__name__)


def parse_litellm_yaml(path: str):
    try:
        with open(path, "r") as fh:
            cfg = yaml.safe_load(fh)
        return cfg
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


def count_api_keys(cfg: dict) -> int:
    if not cfg:
        return 0
    keys = 0
    for entry in cfg.get("model_list", []):
        lit = entry.get("litellm_params", {})
        if lit.get("api_key"):
            keys += 1
    return keys


def check_redis_connection(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def main():
    initialize_app()
    proxy = os.getenv("LITELLM_PROXY_URL")
    yaml_path = os.path.join(
        os.path.dirname(__file__), "..", "utils", "litellm_config.yaml"
    )
    yaml_path = os.path.normpath(yaml_path)

    logger.info("LITELLM_PROXY_URL=%s", proxy or "<not set>")

    cfg = parse_litellm_yaml(yaml_path)
    num_keys = count_api_keys(cfg)
    logger.info("Found %d model entries with api_key in %s", num_keys, yaml_path)

    # Basic RPM recommendation: sum of per-key rpm if present else assume 5 rpm per key
    total_rpm = 0
    if cfg:
        for entry in cfg.get("model_list", []):
            lit = entry.get("litellm_params", {})
            rpm = lit.get("rpm")
            if isinstance(rpm, int):
                total_rpm += rpm
            else:
                # fallback estimate
                if lit.get("api_key"):
                    total_rpm += 5

    logger.info("Estimated total proxy RPM capacity from config: %d", total_rpm)

    # Check redis config in yaml (optional)
    redis_cfg = None
    if cfg:
        rs = cfg.get("router_settings", {}).get("cache_kwargs")
        if rs and rs.get("type") == "redis":
            redis_cfg = rs

    if redis_cfg:
        # litellm_config.yaml may include placeholders like os.environ/REDIS_HOST
        def resolve_val(v):
            if isinstance(v, str) and "os.environ/" in v:
                # extract env var name after slash
                parts = v.split("/")
                env = parts[-1]
                return os.getenv(env)
            return v

        host_val = resolve_val(redis_cfg.get("host", "localhost"))
        port_val = resolve_val(redis_cfg.get("port", 6380))
        host = os.getenv("REDIS_HOST", str(host_val or "localhost"))
        try:
            port = int(os.getenv("REDIS_PORT", int(port_val)))
        except Exception:
            port = int(os.getenv("REDIS_PORT", 6380))
        logger.info("Redis configured: host=%s port=%d", host, port)
        ok = check_redis_connection(host, port)
        if ok:
            logger.info("Redis connection OK")
        else:
            logger.warning(
                "Redis connection failed. Ensure Redis is reachable from this host."
            )
    else:
        logger.info("No redis cache configured in litellm_config.yaml")

    logger.info(
        "Recommendation: set REQUESTS_PER_MINUTE to a value <= %d (use safety margin)",
        max(1, int(total_rpm * 0.8)),
    )


if __name__ == "__main__":
    main()

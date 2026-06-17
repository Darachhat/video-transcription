import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure and return a logger with standard format."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def retry_on_exception(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator for retrying functions with exponential backoff."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = setup_logger(func.__module__)
            current_delay = delay

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {exc}",
                            exc_info=True,
                        )
                        raise
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed, "
                        f"retrying in {current_delay}s: {exc}"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

        return cast(F, wrapper)

    return decorator

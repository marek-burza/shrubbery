import io
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

from shrubbery.numerai.constants import SUBDIRECTORY_LOGS

LOGGING_FORMAT = '%(asctime)s %(levelname)s: %(message)s'


class LoggerWriter(io.TextIOBase):
    def __init__(self, logger: logging.Logger, level: int) -> None:
        self.logger, self.level, self._buffer = logger, level, ''

    def write(self, s: str) -> int:
        self._buffer += s
        *lines, self._buffer = self._buffer.split('\n')
        for line in lines:
            self.logger.log(self.level, line)
        return len(s)

    def flush(self) -> None:
        if self._buffer:
            self.logger.log(self.level, self._buffer)
            self._buffer = ''

    def writable(self) -> bool:
        return True


def silence_false_positive_warnings() -> None:
    for message in [
        # XGBoost will handle CPU to GPU transfer of data
        '.*Falling back to prediction using DMatrix.*',
        # There is currently no way around LGBMRegressor naming features
        '.*but LGBMRegressor was fitted with feature names.*',
    ]:
        warnings.filterwarnings(
            'ignore', category=UserWarning, message=message
        )


def dated_log_file() -> Path:
    log_directory_path = Path('./workspace') / SUBDIRECTORY_LOGS
    log_directory_path.mkdir(parents=True, exist_ok=True)
    return log_directory_path / f'{datetime.now():%Y%m%d%H%M%S}.log'


def setup_logger(log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.__stderr__)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        format=LOGGING_FORMAT,
        level=logging.INFO,
        handlers=handlers,
        force=True,
    )
    logging.getLogger('distributed.core').setLevel(logging.WARNING)
    logging.getLogger('distributed.scheduler').setLevel(logging.WARNING)
    logging.getLogger('distributed.nanny').setLevel(logging.WARNING)
    logging.getLogger('distributed.http.proxy').setLevel(logging.WARNING)
    logging.getLogger('cuml').setLevel(logging.INFO)
    if log_file:
        sys.stdout = LoggerWriter(logging.getLogger('stdout'), logging.INFO)
        sys.stderr = LoggerWriter(logging.getLogger('stderr'), logging.WARNING)

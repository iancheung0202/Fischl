"""Sends print output and crashes to console_output.log, stamped in Pacific time."""

import datetime
import logging
import logging.handlers
import sys

import pytz
from discord.ext import commands, tasks

LOG_MAX_BYTES = 20 * 1024 * 1024  # size at which console_output.log starts a new file
LOG_BACKUPS = 3  # older files kept as console_output.log.1 to .3
PACIFIC = pytz.timezone("America/Los_Angeles")


def pacific_time(*args):
    """Gives the time now in California, for the stamp on each log line."""
    return datetime.datetime.now(datetime.timezone.utc).astimezone(PACIFIC).timetuple()


class PrintLogger:
    """Stands in for stdout, so whatever is printed is logged."""

    def __init__(self):
        self.stdout = sys.stdout

    def write(self, message):
        if message.strip():
            logging.info(message.strip())

    def flush(self):
        pass


def log_crash(kind, error, trace):
    """Logs an error nothing caught; Ctrl-C is left to Python."""
    if issubclass(kind, KeyboardInterrupt):
        sys.__excepthook__(kind, error, trace)
        return
    logging.error("Uncaught exception", exc_info=(kind, error, trace))


def handlers():
    """Gives the log file and console handlers, both written the same way."""
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    found = [
        logging.handlers.RotatingFileHandler(
            "console_output.log", maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS
        ),
        logging.StreamHandler(sys.stdout),
    ]
    for handler in found:
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
    return found


class LoggingSetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_logging.start()

    @tasks.loop(count=1)
    async def setup_logging(self):
        logging.Formatter.converter = pacific_time
        logging.basicConfig(level=logging.INFO, handlers=handlers())
        sys.stdout = PrintLogger()
        sys.excepthook = log_crash

    @setup_logging.before_loop
    async def before_setup_logging(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(LoggingSetupCog(bot))

import logging
import sys
import datetime
import pytz

from discord.ext import commands, tasks

class LoggingSetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_logging.start()

    @tasks.loop(count=1)
    async def setup_logging(self):
        def pacific_time_converter(*args):
            utc_dt = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=pytz.utc)
            pacific_dt = utc_dt.astimezone(pytz.timezone("America/Los_Angeles"))
            return pacific_dt.timetuple()

        logging.Formatter.converter = pacific_time_converter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler = logging.FileHandler("console_output.log")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

        class PrintLogger:
            def __init__(self):
                self.stdout = sys.stdout

            def write(self, message):
                if message.strip():
                    logging.info(message.strip())

            def flush(self):
                pass

        sys.stdout = PrintLogger()

        def log_uncaught_exceptions(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = log_uncaught_exceptions

    @setup_logging.before_loop
    async def before_setup_logging(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(LoggingSetupCog(bot))
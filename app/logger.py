import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


import logging
import os


log = logging.getLogger(__name__)


def safe_outdir(func):
    def _makeoutdir(*args, **kwargs):
        outdir = args[-1]
        os.makedirs(outdir, exist_ok=True)
        return func(*args, **kwargs)

    return _makeoutdir

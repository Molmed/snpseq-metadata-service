import argparse
import logging
import logging.config
import os
import pathlib
import sys
import yaml

import aiohttp.web

from metadata_service.handlers import export, version


log = logging.getLogger(__name__)


def setup_routes(app):
    app.router.add_get(app["config"]["base_url"] + "/version", version)
    app.router.add_get(app["config"]["base_url"] + "/export/{host}/{runfolder}", export)


def setup_log(config):
    try:
        filename = config["handlers"]["file_handler"]["filename"]
        logdir = os.path.dirname(filename)
        os.makedirs(logdir, exist_ok=True)
    except KeyError:
        pass


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--configroot",
        help="Path to config root dir",
        type=pathlib.Path,
        default="config")

    args = parser.parse_args()
    cfgroot = args.configroot

    log.debug(f"config root directory is {cfgroot}")
    if not cfgroot.is_dir():
        log.error(f"config root '{cfgroot}' is not a directory or does not exist")
        sys.exit(1)

    return args


def load_config(cfgroot):

    config = {
        "app.yaml": None,
        "logger.yaml": None
    }

    for cfgfile in cfgroot.iterdir():
        if cfgfile.name in config.keys():
            with cfgfile.open() as logger:
                config[cfgfile.name] = yaml.safe_load(logger)

    setup_log(config["logger.yaml"])
    logging.config.dictConfig(config["logger.yaml"])
    return config["app.yaml"]


async def data_session(app):
    app['data_session'] = aiohttp.ClientSession(app['config']['snpseq_data_url'])
    yield
    await app['data_session'].close()


def setup_app(cfgroot):
    conf = load_config(cfgroot)
    app = aiohttp.web.Application()
    app['config'] = conf
    app.cleanup_ctx.append(data_session)
    setup_routes(app)
    return app


def start():
    args = parse_args()
    app = setup_app(args.configroot)
    port = int(app['config'].get("port", 8080))
    log.info(f"starting metadata-service on port {port}...")
    aiohttp.web.run_app(app, host="127.0.0.1", port=port)

import argparse
import logging
import logging.config
import os
import pathlib
import sys
import yaml

import aiohttp.web

from metadata_service.clients import SnpseqDataRequest
from metadata_service.handlers import ExportHandler, VersionHandler
from metadata_service.process import MetadataProcessRunner


log = logging.getLogger(__name__)


def setup_routes(app, version_handler, export_handler):
    app.router.add_get(
        app["config"]["base_url"] + "/version",
        version_handler.version)
    app.router.add_get(
        app["config"]["base_url"] + "/export/{host}/{runfolder}",
        export_handler.export)


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


def setup_app(
        cfgroot,
        metadata_executable_path=None,
        process_runner_cls=MetadataProcessRunner,
        data_session_cls=SnpseqDataRequest,
        version_handler_cls=VersionHandler,
        export_handler_cls=ExportHandler):

    conf = load_config(cfgroot)
    app = aiohttp.web.Application()

    session = data_session_cls(conf.get("snpseq_data_url"))

    metadata_exec = metadata_executable_path or conf.get(
        "snpseq_metadata_executable",
        "snpseq_metadata")
    proc_run = process_runner_cls(
        metadata_executable=metadata_exec)

    export_handler_obj = export_handler_cls(process_runner=proc_run)
    version_handler_obj = version_handler_cls()

    app['config'] = conf
    app['session'] = session
    app.cleanup_ctx.append(session.external_session)
    setup_routes(
        app,
        version_handler=version_handler_obj,
        export_handler=export_handler_obj)
    return app


def start():
    args = parse_args()
    app = setup_app(args.configroot)
    port = int(app['config'].get("port", 8080))
    log.info(f"starting metadata-service on port {port}...")
    aiohttp.web.run_app(app, port=port)

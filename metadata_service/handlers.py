import json
import logging
import os
import pathlib
import tempfile

import importlib.metadata
import aiohttp.web


log = logging.getLogger(__name__)


class VersionHandler:

    def __init__(self):
        self.version_str = importlib.metadata.version('metadata-service')

    async def version(self, request):
        return aiohttp.web.json_response(
            {
                'version': self.version_str},
            status=200)


class ExportHandler:

    def __init__(self, process_runner):
        self.process_runner = process_runner

    async def export(self, request):

        host = request.match_info["host"]
        runfolder = request.match_info["runfolder"]

        runfolder_path = pathlib.Path(
            request.app["config"].get("datadir", "."),
            host,
            "runfolders",
            runfolder)
        metadata_export_path = os.path.join(runfolder_path, "metadata")

        with tempfile.TemporaryDirectory(prefix="extract", suffix="runfolder") as outdir:
            runfolder_extract = self.process_runner.extract_runfolder_metadata(
                runfolder_path,
                outdir)
            lims_data = await request.app['session'].request_snpseq_data_metadata(
                runfolder_path,
                outdir)
            snpseq_data_extract = self.process_runner.extract_snpseq_data_metadata(
                lims_data,
                outdir)

            metadata_export = self.process_runner.export_runfolder_metadata(
                    runfolder_extract,
                    snpseq_data_extract,
                    metadata_export_path)

        return aiohttp.web.json_response({'metadata': metadata_export}, status=200)

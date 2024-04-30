
import logging
import os
import pathlib
import shutil
import tempfile

import importlib.metadata
import aiohttp.web


log = logging.getLogger(__name__)


class VersionHandler:

    def __init__(self):
        self.version_str = importlib.metadata.version('metadata-service')

    async def version(self, request):
        try:
            return aiohttp.web.json_response(
                {
                    'version': self.version_str},
                status=200)
        except Exception as ex:
            return aiohttp.web.json_response({'exception': str(ex)}, status=500)


class ExportHandler:

    def __init__(self, process_runner):
        self.process_runner = process_runner

    async def export(self, request):

        try:
            host = request.match_info["host"]
            runfolder = request.match_info["runfolder"]
            lims_data = request.query.get("lims_data")

            runfolder_path = pathlib.Path(
                request.app["config"].get("datadir", ".").format(
                    host=host,
                    runfolder=runfolder
                )
            )
            metadata_export_path = os.path.join(runfolder_path, "metadata")

            with tempfile.TemporaryDirectory(prefix="extract", suffix="runfolder") as outdir:
                # unless a previous LIMS-export is passed as a parameter, do a request to the
                # snpseq-data web service
                if not lims_data:
                    lims_data = await request.app['session'].request_snpseq_data_metadata(
                        runfolder_path,
                        outdir
                    )
                else:
                    lims_data_src = pathlib.Path(
                        metadata_export_path,
                        lims_data
                    )
                    lims_data = pathlib.Path(
                        outdir,
                        lims_data
                    )
                    shutil.copy(lims_data_src, lims_data)

                snpseq_data_extract = self.process_runner.extract_snpseq_data_metadata(
                    lims_data,
                    outdir
                )

                runfolder_extract = self.process_runner.extract_runfolder_metadata(
                    runfolder_path,
                    outdir
                )

                metadata_export = self.process_runner.export_runfolder_metadata(
                        runfolder_extract,
                        snpseq_data_extract,
                        metadata_export_path
                )

            return aiohttp.web.json_response({'metadata': metadata_export}, status=200)
        except Exception as ex:
            log.error(str(ex))
            return aiohttp.web.json_response({'exception': str(ex)}, status=500)

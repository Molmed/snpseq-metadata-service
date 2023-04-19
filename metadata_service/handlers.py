import json
import logging
import os
import pathlib
import shlex
import subprocess
import tempfile

import importlib.metadata
import aiohttp.web


log = logging.getLogger(__name__)


def _run_external(cmdline):
    try:
        proc = subprocess.run(
            shlex.split(cmdline),
            capture_output=True,
            text=True
        )
        log.debug(proc.stdout)
        proc.check_returncode()
        log.info(f"{cmdline} exited with exit-code {proc.returncode}")
    except subprocess.CalledProcessError as err:
        log.error(f"{err.cmd} exited with exit-code {err.returncode}")
        log.error(err.stderr)
        raise
    return proc


async def _extract_runfolder_metadata(runfolder_path, outdir, metadata_executable):
    cmdline = f"{metadata_executable} extract runfolder --outdir {outdir} {runfolder_path} json"
    _run_external(cmdline)
    return os.path.join(outdir, f"{os.path.basename(runfolder_path)}.ngi.json")


async def _extract_snpseq_data_metadata(data_path, outdir, metadata_executable):
    cmdline = f"{metadata_executable} extract snpseq-data --outdir {outdir} {data_path} json"
    _run_external(cmdline)
    print(os.listdir(outdir))
    return os.path.join(
        outdir,
        f"{'.'.join(os.path.basename(data_path).split('.')[0:-1])}.ngi.json")


async def _export_runfolder_metadata(
        runfolder_extract,
        snpseq_data_extract,
        outdir,
        metadata_executable):
    os.makedirs(outdir, exist_ok=True)
    cmdline = f"" \
              f"{metadata_executable} export " \
              f"--outdir {outdir} " \
              f"{runfolder_extract} " \
              f"{snpseq_data_extract} " \
              f"xml"
    _run_external(cmdline)
    return [
        os.path.join(
            outdir,
            xmlfile)
        for xmlfile in os.listdir(outdir)
        if xmlfile.endswith(".xml")
    ]


async def _request_snpseq_data_metadata(session, runfolder_path, outdir):
    flowcell_id = os.path.basename(runfolder_path).split("_")[-1]
    flowcell_id = flowcell_id[1:] if flowcell_id[0] in "AB" else flowcell_id
    lims_json = os.path.join(outdir, f"{flowcell_id}.lims.json")
    resp = await session.get(
        '/api/containers',
        params={
            'name': flowcell_id
        })
    with open(lims_json, "w") as fh:
        json.dump(await resp.json(), fh, indent=2)
    return lims_json


async def version(request):
    ver = importlib.metadata.version('metadata-service')
    return aiohttp.web.json_response({'version': ver}, status=200)


async def export(request):

    host = request.match_info["host"]
    runfolder = request.match_info["runfolder"]

    runfolder_path = pathlib.Path(
        request.app["config"].get("datadir", "."),
        host,
        "runfolders",
        runfolder)
    metadata_export_path = os.path.join(runfolder_path, "metadata")
    metadata_exec = request.app["config"].get("snpseq_metadata_executable", "snpseq_metadata")

    with tempfile.TemporaryDirectory(prefix="extract", suffix="runfolder") as outdir:
        runfolder_extract = await _extract_runfolder_metadata(
            runfolder_path,
            outdir,
            metadata_exec)
        lims_data = await _request_snpseq_data_metadata(
            request.app['data_session'],
            runfolder_path,
            outdir)
        snpseq_data_extract = await _extract_snpseq_data_metadata(
            lims_data,
            outdir,
            metadata_exec)

        metadata_export = await _export_runfolder_metadata(
                runfolder_extract,
                snpseq_data_extract,
                metadata_export_path,
                metadata_exec)

    return aiohttp.web.json_response({'metadata': metadata_export}, status=200)

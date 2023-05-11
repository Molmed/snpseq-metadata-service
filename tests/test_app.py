
import aiohttp.web
import importlib.metadata
import json
import logging
import os
import pathlib
import pytest
import re
import shutil

import metadata_service.app
import metadata_service.clients
import metadata_service.process


log = logging.getLogger(__name__)


@pytest.fixture
def test_runfolder():
    return "210415_A00001_0123_BXYZ321XY"


@pytest.fixture
def test_snpseq_data_path(test_runfolder):
    return pathlib.Path(f"tests/test_data/{test_runfolder.split('_')[-1][1:]}.lims.json")


@pytest.fixture
def test_snpseq_data_json(test_snpseq_data_path):
    with open(test_snpseq_data_path) as fh:
        return json.load(fh)


@pytest.fixture
def test_config():
    return pathlib.Path("tests/config")


@pytest.fixture
def load_config(test_config):
    return metadata_service.app.load_config(test_config)


@pytest.fixture
def cli(event_loop, aiohttp_client, test_config):
    app = metadata_service.app.setup_app(
        test_config,
        process_runner_cls=MetadataTestProcessRunner,
        data_session_cls=SnpseqDataTestRequest)
    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
async def snpseq_data_server(aiohttp_server, load_config):
    """
    Create a test server for responding to snpseq-data requests and serves up pre-fetched json
    responses from snpseq-data
    """
    async def snpseq_data(request):
        q = request.query
        response_path = pathlib.Path(
            f"{load_config['datadir']}/test_data/{q['name']}.lims.json")
        with open(response_path) as fh:
            data = json.load(fh)

        status = q.get("status", 200)
        content_type = q.get("content_type", "application/json")

        if content_type == "application/json":
            return aiohttp.web.json_response(
                data=data,
                status=status)

        return aiohttp.web.Response(
            text=json.dumps(data),
            content_type=content_type,
            status=status)

    m = re.search(r'[a-z.]+:(\d{4,})', load_config['snpseq_data_url'])
    port = int(m.group(1))
    app = aiohttp.web.Application()
    app.add_routes([
        aiohttp.web.get("/api/containers", snpseq_data)])

    yield await aiohttp_server(app, port=int(port))


class SnpseqDataTestRequest(metadata_service.clients.SnpseqDataRequest):

    async def external_session(self, app):
        yield

    async def request_snpseq_data_metadata(self, runfolder_path, outdir):
        flowcell_id = self.flowcellid_from_runfolder(runfolder_path)
        outfile = os.path.join(outdir, f"{flowcell_id}.lims.json")
        srcfile = os.path.join("tests", "test_data", os.path.basename(outfile))
        shutil.copy(srcfile, outfile)
        return outfile


class MetadataTestProcessRunner(metadata_service.process.MetadataProcessRunner):

    def __init__(self, metadata_executable):
        super(MetadataTestProcessRunner, self).__init__(metadata_executable="echo")

    def extract_runfolder_metadata(self, *args):
        outfile = super(MetadataTestProcessRunner, self).extract_runfolder_metadata(
            *args)
        srcfile = os.path.join("tests", "test_data", os.path.basename(outfile))
        shutil.copy(srcfile, outfile)
        return outfile

    def extract_snpseq_data_metadata(self, *args):
        outfile = super(MetadataTestProcessRunner, self).extract_snpseq_data_metadata(
            *args)
        srcfile = os.path.join("tests", "test_data", os.path.basename(outfile))
        shutil.copy(srcfile, outfile)
        return outfile

    def export_runfolder_metadata(self, *args):
        super(MetadataTestProcessRunner, self).export_runfolder_metadata(
            *args)
        outdir = args[-1]
        srcdir = os.path.join("tests", "test_data")
        outfiles = []
        for srcfile in filter(
                lambda f: f.endswith(".xml"),
                os.listdir(srcdir)):
            outfiles.append(os.path.join(outdir, srcfile))
            shutil.copy(
                os.path.join(srcdir, srcfile),
                outfiles[-1])
        return outfiles


async def test_version(cli):
    base_url = cli.server.app["config"].get("base_url", "")
    resp = await cli.get(f"{base_url}/version")
    ver = await resp.json()
    assert resp.status == 200
    assert ver["version"] == importlib.metadata.version('metadata-service')


async def test_export(snpseq_data_server, cli, test_runfolder):
    base_url = cli.server.app["config"].get("base_url", "")
    datadir = cli.server.app["config"]["datadir"]
    host = "test_data"
    runfolder = test_runfolder
    metadatadir = os.path.join(
        datadir,
        host,
        "runfolders",
        runfolder,
        "metadata")

    shutil.rmtree(metadatadir, ignore_errors=True)
    expected_files = sorted([
        os.path.join(
            metadatadir,
            f"{prj}-{typ}.xml")
        for prj in ["AB-1234", "CD-5678", "EF-9012"]
        for typ in ["experiment", "run"]
    ])

    resp = await cli.get(f"{base_url}/export/{host}/{runfolder}")
    json_resp = await resp.json()

    assert resp.status == 200
    assert "metadata" in json_resp
    assert sorted(json_resp["metadata"]) == expected_files
    assert os.path.exists(metadatadir)
    for metafile in expected_files:
        assert os.path.exists(metafile)

    shutil.rmtree(metadatadir)


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
        fcid = q.get("name")
        response_path = pathlib.Path("tests", "test_data", f"{fcid}.lims.json")
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


def get_projects_from_jsonfile(jsonfile, pattern=None):
    projects = []
    pattern = pattern or r'"project(?:_id)?": "(\w{2}-\d{4})"'
    with open(jsonfile, "r") as fh:
        for line in fh:
            m = re.search(pattern, line)
            if m is not None:
                projects.append(m.group(1))

    return list(sorted(list(set(projects))))


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

        # extract the "original" project names from the lims export and the "tweaked" from the lims
        # extract
        projects = [[], []]
        for i, jsonfile in enumerate((args[1], args[1].replace(".ngi.json", ".json"))):
            projects[i] = get_projects_from_jsonfile(jsonfile)

        for srcfile in filter(
                lambda f: f.endswith(".xml") or f.endswith(".tsv"),
                os.listdir(srcdir)):
            outfile = srcfile
            for prj_s, prj_c in zip(projects[0], projects[1]):
                outfile = outfile.replace(prj_s, prj_c)
            outfiles.append(
                os.path.join(outdir, outfile)
            )
            shutil.copy(
                os.path.join(srcdir, srcfile),
                outfiles[-1]
            )
        return outfiles


async def test_version(cli):
    base_url = cli.server.app["config"].get("base_url", "")
    resp = await cli.get(f"{base_url}/version")
    ver = await resp.json()
    assert resp.status == 200
    assert ver["version"] == importlib.metadata.version('metadata-service')


async def _export_helper(
        snpseq_data_server,
        cli,
        test_runfolder,
        test_snpseq_data_path,
        lims_data_cache
):
    base_url = cli.server.app["config"].get("base_url", "")
    datadir = cli.server.app["config"]["datadir"]
    host = "test_data"
    runfolder = test_runfolder
    datadir = datadir.format(
        host=host,
        runfolder=runfolder
    )
    metadatadir = os.path.join(
        datadir,
        "metadata")

    shutil.rmtree(metadatadir, ignore_errors=True)

    request_url = f"{base_url}/export/{host}/{runfolder}"
    projects = [[], []]
    projects[0] = get_projects_from_jsonfile(test_snpseq_data_path)
    projects[1] = list(projects[0])

    if lims_data_cache:
        os.makedirs(metadatadir)

        # copy the LIMS export file to the metadata dir
        lims_data = os.path.join(
            metadatadir,
            os.path.basename(test_snpseq_data_path)
        )

        # tweak the project names so that we can make sure that the cache was used and not
        # the mocked snpseq-data file
        projects[1] = [
            "-".join([
                prj.split("-")[0][::-1],
                prj.split("-")[1][::-1]
            ]) for prj in projects[0]
        ]
        with open(test_snpseq_data_path, "r") as rh, open(lims_data, "w") as wh:
            for line in rh:
                for prj_s, prj_c in zip(*projects):
                    line = line.replace(prj_s, prj_c)
                wh.write(line)

        # pass the name of the lims cache json file as a query parameter
        request_url = f"{request_url}?lims_data={os.path.basename(test_snpseq_data_path)}"

    expected_files = []
    for prj in projects[1]:
        expected_files.append(
            os.path.join(
                metadatadir,
                f"{prj}.metadata.ena.tsv"
            )
        )
        for typ in ["experiment", "run"]:
            expected_files.append(
                os.path.join(
                    metadatadir,
                    f"{prj}-{typ}.xml"
                )
            )
    expected_files = sorted(expected_files)

    resp = await cli.get(request_url)
    json_resp = await resp.json()

    assert resp.status == 200
    assert "metadata" in json_resp
    assert sorted(json_resp["metadata"]) == expected_files
    assert os.path.exists(metadatadir)
    for metafile in expected_files:
        assert os.path.exists(metafile)

    shutil.rmtree(metadatadir)


async def test_export_with_lims_api(
        snpseq_data_server,
        cli,
        test_runfolder,
        test_snpseq_data_path
):
    await _export_helper(
        snpseq_data_server,
        cli,
        test_runfolder,
        test_snpseq_data_path,
        lims_data_cache=False,
    )


async def test_export_with_lims_cache(
        snpseq_data_server,
        cli,
        test_runfolder,
        test_snpseq_data_path
):
    await _export_helper(
        snpseq_data_server,
        cli,
        test_runfolder,
        test_snpseq_data_path,
        lims_data_cache=True,
    )


import aiohttp.web
import importlib.metadata
import json
import os
import pathlib
import pytest
import re
import shutil

import metadata_service.app


@pytest.fixture
def test_config():
    return pathlib.Path("tests/config")


@pytest.fixture
def load_config(test_config):
    return metadata_service.app.load_config(test_config)


@pytest.fixture
def cli(event_loop, aiohttp_client, test_config):
    app = metadata_service.app.setup_app(test_config)
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
            f"{load_config['datadir']}/test_data/snpseq_data_{q['name']}.json")
        with open(response_path) as fh:
            return aiohttp.web.json_response(data=json.load(fh), status=200)

    m = re.search(r'[a-z.]+:(\d{4,})', load_config['snpseq_data_url'])
    port = int(m.group(1))
    app = aiohttp.web.Application()
    app.add_routes([
        aiohttp.web.get("/api/containers", snpseq_data)])

    yield await aiohttp_server(app, port=int(port))


async def test_version(cli):
    base_url = cli.server.app["config"].get("base_url", "")
    resp = await cli.get(f"{base_url}/version")
    ver = await resp.json()
    assert resp.status == 200
    assert ver["version"] == importlib.metadata.version('metadata-service')


async def test_export(snpseq_data_server, cli):
    base_url = cli.server.app["config"].get("base_url", "")
    datadir = cli.server.app["config"]["datadir"]
    host = "test_data"
    runfolder = "210415_A00001_0123_BXYZ321XY"
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

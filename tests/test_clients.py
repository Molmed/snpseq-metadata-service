
import aiohttp
import json
import mock
import os
import pytest
import tempfile

from metadata_service.clients import SnpseqDataRequest

from tests.test_app import \
    snpseq_data_server, \
    load_config, \
    test_config, \
    test_runfolder, \
    test_snpseq_data_json, \
    test_snpseq_data_path


async def test_snpseq_data_client(
        snpseq_data_server,
        test_runfolder,
        test_snpseq_data_path,
        test_snpseq_data_json):
    rq = SnpseqDataRequest(external_url=f"http://{snpseq_data_server.host}:{snpseq_data_server.port}")
    rq.session = aiohttp.ClientSession(rq.external_url)
    flowcell_id = rq.flowcellid_from_runfolder(test_runfolder)
    request_urls = (
        ('/api/containers', {'name': flowcell_id}),
        ('/api/containers', {'name': flowcell_id, 'content_type': 'text/html'}),
        ('/api/containers', {'name': flowcell_id, 'content_type': 'application/json'}),
        ('/api/containers', {'name': flowcell_id, 'status': 500})
    )

    def _assert_json(observed_path, expected_path, expected_json):
        assert observed_path == expected_path
        with open(observed_path, "r") as fh:
            observed_json = json.load(fh)
            assert observed_json == expected_json
        os.unlink(observed_path)

    with mock.patch.object(rq, "data_request_url", side_effect=request_urls) as url_mock, \
            tempfile.TemporaryDirectory(prefix="test_snpseq_data_client") as outdir:
        expected_jsonfile = os.path.join(outdir, os.path.basename(test_snpseq_data_path))

        # the straightforward example
        observed_jsonfile = await rq.request_snpseq_data_metadata(test_runfolder, outdir)
        _assert_json(observed_jsonfile, expected_jsonfile, test_snpseq_data_json)

        # handle json returned as text
        observed_jsonfile = await rq.request_snpseq_data_metadata(test_runfolder, outdir)
        _assert_json(observed_jsonfile, expected_jsonfile, test_snpseq_data_json)

        # handle json returned as json
        observed_jsonfile = await rq.request_snpseq_data_metadata(test_runfolder, outdir)
        _assert_json(observed_jsonfile, expected_jsonfile, test_snpseq_data_json)

        # catch and raise exception when no results were returned
        with pytest.raises(expected_exception=Exception):
            await rq.request_snpseq_data_metadata(test_runfolder, outdir)

    await rq.session.close()

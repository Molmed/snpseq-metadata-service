import os

import aiohttp
import mock
import tempfile

import pytest

from metadata_service.clients import SnpseqDataRequest

from tests.test_app import snpseq_data_server, load_config, test_config, test_runfolder


async def test_snpseq_data_client(snpseq_data_server, test_runfolder):
    rq = SnpseqDataRequest(external_url=f"http://{snpseq_data_server.host}:{snpseq_data_server.port}")
    rq.session = aiohttp.ClientSession(rq.external_url)
    flowcell_id = rq.flowcellid_from_runfolder(test_runfolder)
    request_urls = (
        ('/api/containers', {'name': flowcell_id}),
        ('/api/containers', {'name': flowcell_id, 'content_type': 'text/html'}),
        ('/api/containers', {'name': flowcell_id, 'content_type': 'application/json'}),
        ('/api/containers', {'name': flowcell_id, 'status': 500})
    )
    with mock.patch.object(rq, "data_request_url", side_effect=request_urls) as url_mock, \
            tempfile.TemporaryDirectory(prefix="test_snpseq_data_client") as outdir:
        expected_jsonfile = os.path.join(outdir, f"{flowcell_id}.lims.json")

        # the straightforward example
        observed_jsonfile = await rq.request_snpseq_data_metadata(test_runfolder, outdir)
        assert observed_jsonfile == expected_jsonfile
        os.unlink(observed_jsonfile)

        # handle json returned as text
        observed_jsonfile = await rq.request_snpseq_data_metadata(test_runfolder, outdir)
        assert observed_jsonfile == expected_jsonfile
        os.unlink(observed_jsonfile)

        # handle json returned as json
        observed_jsonfile = await rq.request_snpseq_data_metadata(test_runfolder, outdir)
        assert observed_jsonfile == expected_jsonfile
        os.unlink(observed_jsonfile)

        # catch and raise exception when no results were returned
        with pytest.raises(expected_exception=Exception):
            await rq.request_snpseq_data_metadata(test_runfolder, outdir)

    await rq.session.close()

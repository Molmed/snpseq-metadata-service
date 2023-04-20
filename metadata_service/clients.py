
import aiohttp
import json
import logging
import os

from metadata_service.utils import safe_outdir


log = logging.getLogger(__name__)


class ExternalRequest:

    def __init__(self, external_url):
        self.external_url = external_url
        self.session = None

    async def external_session(self, app):
        self.session = aiohttp.ClientSession(self.external_url)
        yield
        await self.session.close()


class SnpseqDataRequest(ExternalRequest):

    @safe_outdir
    async def request_snpseq_data_metadata(self, runfolder_path, outdir):
        flowcell_id = os.path.basename(runfolder_path).split("_")[-1]
        flowcell_id = flowcell_id[1:] if flowcell_id[0] in "AB" else flowcell_id
        lims_json = os.path.join(outdir, f"{flowcell_id}.lims.json")
        resp = await self.session.get(
            '/api/containers',
            params={
                'name': flowcell_id
            })
        with open(lims_json, "w") as fh:
            json.dump(await resp.json(), fh, indent=2)
        return lims_json


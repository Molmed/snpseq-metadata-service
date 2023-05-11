
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

    @staticmethod
    def flowcellid_from_runfolder(runfolder):
        flowcell_id = os.path.basename(runfolder).split("_")[-1]
        flowcell_id = flowcell_id[1:] if flowcell_id[0] in "AB" else flowcell_id
        return flowcell_id

    @staticmethod
    def data_request_url(flowcell_id):
        return '/api/containers', {
            'name': flowcell_id}

    @safe_outdir
    async def request_snpseq_data_metadata(self, runfolder_path, outdir):
        flowcell_id = self.flowcellid_from_runfolder(runfolder_path)
        lims_json = os.path.join(outdir, f"{flowcell_id}.lims.json")
        url, params = self.data_request_url(flowcell_id)
        resp = await self.session.get(
            url,
            params=params)

        data = {}
        try:
            if resp.content_type == 'application/json':
                data = await resp.json()
            else:
                data = json.loads(await resp.text())
            if not resp.ok:
                raise Exception()
        except Exception:
            raise Exception(
                f"{self.__class__.__name__} received response status {resp.status} from "
                f"{resp.url}: {data.get('error_message', resp.reason)}")

        with open(lims_json, "w") as fh:
            json.dump(data, fh, indent=2)

        return lims_json

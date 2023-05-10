
import logging
import os
import shlex
import subprocess

from metadata_service.utils import safe_outdir


log = logging.getLogger(__name__)


class ProcessRunner:

    def __init__(self):
        pass

    def run_process(self, cmdline):
        try:
            proc = subprocess.run(
                shlex.split(cmdline),
                capture_output=True,
                text=True
            )
            log.debug(proc.stdout)
            proc.check_returncode()
            log.info(
                f"{cmdline} exited with exit-code {proc.returncode}")
        except subprocess.CalledProcessError as err:
            log.error(
                f"{err.cmd} exited with exit-code {err.returncode}")
            log.error(
                err.stderr)
            raise Exception(err.stdout)
        return proc


class MetadataProcessRunner(ProcessRunner):

    def __init__(self, metadata_executable):
        super(MetadataProcessRunner, self).__init__()
        self.metadata_executable = metadata_executable

    @safe_outdir
    def extract_runfolder_metadata(self, runfolder_path, outdir):
        cmdline = f"{self.metadata_executable} extract runfolder --outdir {outdir} " \
                  f"{runfolder_path} json"
        self.run_process(cmdline)
        return os.path.join(
            outdir,
            f"{os.path.basename(runfolder_path)}.ngi.json")

    @safe_outdir
    def extract_snpseq_data_metadata(self, data_path, outdir):
        cmdline = f"{self.metadata_executable} extract snpseq-data --outdir {outdir} " \
                  f"{data_path} json"
        self.run_process(cmdline)
        return os.path.join(
            outdir,
            f"{'.'.join(os.path.basename(data_path).split('.')[0:-1])}.ngi.json")

    @safe_outdir
    def export_runfolder_metadata(self, runfolder_extract, snpseq_data_extract, outdir):
        cmdline = f"" \
                  f"{self.metadata_executable} export " \
                  f"--outdir {outdir} " \
                  f"{runfolder_extract} " \
                  f"{snpseq_data_extract} " \
                  f"xml"
        self.run_process(cmdline)
        return [
            os.path.join(
                outdir,
                xmlfile)
            for xmlfile in os.listdir(outdir)
            if xmlfile.endswith(".xml")
        ]

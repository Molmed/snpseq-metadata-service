# snpseq-metadata-service

[![Run Unit Tests](../../actions/workflows/tests.yml/badge.svg?branch=pass_exceptions_to_response&event=push)](../../actions/workflows/tests.yml)

A (aiohttp) REST service that coordinates the extraction and export of metadata information for projects and sequencing
runs.

This service will in turn call the [snpseq-data](https://gitlab.snpseq.medsci.uu.se/shared/snpseq-data) REST API to
extract project metadata from a Clarity LIMS instance and use the
[snpseq_metadata](https://github.com/Molmed/snpseq_metadata) Python package to extract sequencing run metadata from a
runfolder, as well as combine project and sequencing run metadata and export to relevant formats.

## Installation

### Pre-requisites

- You will need python >=3.8

- The service will expect the [snpseq_metadata](https://github.com/Molmed/snpseq_metadata) (>= v2.2.0) Python package to be
available in the environment (refer to the
[README](https://github.com/Molmed/snpseq_metadata/blob/main/README.md#installation) for installation instructions).

- Unless data extracted from Clarity LIMS will be supplied in a separate json file, the service needs the url of an 
accessible [snpseq-data](https://gitlab.snpseq.medsci.uu.se/shared/snpseq-data) service.

### Deploy

Clone this repository from GitHub
```
git clone https://github.com/Molmed/snpseq-metadata-service
cd snpseq-metadata-service
```
It is recommended to set up the service in a virtual environment. In the example below,
[venv](https://docs.python.org/3/library/venv.html) is used.
```
python3 -m venv --upgrade-deps .venv
source .venv/bin/activate
pip install .
```

### Configuration

See the [config](config/) folder for example configs.

## Running the service
```
usage: metadata-service [-h] [-c CONFIGROOT]

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIGROOT, --configroot CONFIGROOT
                        Path to config root dir

```
Start the service and pass the path to the config directory on the command line:
```
metadata-service -c config/
```

## Using the service

Assuming the service has been configured to listen on port `8345`, an overview of the API endpoints can be obtained by
accessing the `api` endpoint:
```
curl http://snpseq-metadata-service.url:8345/api
```

To gather and export metadata for a runfolder named `210415_A00001_0123_BXYZ321XY` and sequenced on the host
`biotank-host`, make a call to the `export` endpoint:
```
curl http://snpseq-metadata-service.url:8345/api/1.0/export/biotank-host/210415_A00001_0123_BXYZ321XY
```
This will create a directory named `metadata` in the runfolder and the metadata information will be exported to this
directory. The service will issue a json dictionary response with a list of paths to the exported metadata files under the key
`metadata`.

## Testing the service

The unit test suite can be run by first installing the optional test dependencies:
```
source .venv/bin/activate
pip install .[test]
```
Then run the test suite:
```
pytest --asyncio-mode auto tests/
```

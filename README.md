# airline-data-mesh

A mini data mesh for a fictional airline, built from public data. Each division publishes its data as a governed data product, and an MCP endpoint exposes those products to AI agents as tools.

Companion to [agentic-ai-investigation-team](https://github.com/icarovazquez/agentic-ai-investigation-team), which consumes the mesh as an evidence source.

## Status

Notebook 1 (`notebooks/01_build_data_mesh.ipynb`) builds the first two divisions (network_ops, weather), publishes them to BigQuery and checks the Dec 2022 case. Its code moves into `src/airline_mesh/lake/` as the package grows.

To run it you need a Google account and a free Google Cloud project (the BigQuery sandbox needs no billing). Put the project ID in Cell 1.

## Layout

- `src/airline_mesh/lake/`: downloaders and Parquet builders
- `src/airline_mesh/catalog/`: contract loader and product search
- `src/airline_mesh/gateway/`: access policy, PII masking, audit log
- `src/airline_mesh/server/`: the MCP endpoint
- `src/airline_mesh/synthetic/`: generator for the synthetic crew and maintenance data (planted-cause worlds)
- `domains/<division>/`: each division's `contract.yaml` and adapter
- `notebooks/`: Colab notebooks, one per phase

## Divisions

| Division | Source | Real or synthetic |
| --- | --- | --- |
| network_ops | BTS On-Time Performance | Real |
| weather | NOAA / Iowa Environmental Mesonet ASOS | Real |
| fleet | FAA aircraft registry | Real |
| customer | DOT air travel consumer reports | Real |
| crew | none public | Synthetic |
| maintenance | none public | Synthetic |

Crew and maintenance are synthetic. `synthetic/generator.py` writes them from the real flight schedule and stated assumptions (all made up, listed in `ASSUMPTIONS`), with two dials (crew effect, maintenance effect) that set the true cause. The true cause is returned as ground truth and never written into a table. Run the tests with `PYTHONPATH=src python3 -m pytest -q`.

BTS delay causes are self-reported by the carrier, so treat them as claims to test.

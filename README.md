# airline-data-mesh

A mini data mesh for a fictional airline, built from public data. Each division publishes its data as a governed data product, and an MCP endpoint exposes those products to AI agents as tools.

Companion to [agentic-ai-investigation-team](https://github.com/icarovazquez/agentic-ai-investigation-team), which consumes the mesh as an evidence source.

## Status

Scaffold only. Notebook 1 (build the lake and check the Dec 2022 case) is being run in Colab; its code moves into `src/airline_mesh/lake/` once it works.

## Layout

- `src/airline_mesh/lake/`: downloaders and Parquet builders
- `src/airline_mesh/catalog/`: contract loader and product search
- `src/airline_mesh/gateway/`: access policy, PII masking, audit log
- `src/airline_mesh/server/`: the MCP endpoint
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

BTS delay causes are self-reported by the carrier, so treat them as claims to test.

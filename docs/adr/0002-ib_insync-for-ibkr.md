# IBKR Connection: ib_insync

Use the `ib_insync` Python library to connect to IBKR TWS/Gateway for paper account order execution.

ib_insync provides the most mature Python ecosystem, comprehensive documentation, and active community support. The official `ibapi` library is more complex with sparser documentation. The official REST API is newer with limited Python support.

Considered Options: ib_insync, official ibapi, official REST API.
Consequences: Requires TWS or Gateway running locally. ib_insync's event-driven API aligns well with the system's need for order status callbacks.

To run the notebooks you need to add a `.env` file to the `notebooks` directory with the following information

```
HYPERGRAPH_MODEL="..."
HYPERGRAPH_EMBEDDING_MODEL="..."
HYPERGRAPH_API_BASE="..."
# API Key and version are optional
# If not provided, Azure managed identity will be used
HYPERGRAPH_API_KEY="..."
HYPERGRAPH_API_VERSION="..."
```
# Indexing Architecture 

## Key Concepts

### Knowledge Model

In order to support the Hypergraph system, the outputs of the indexing engine (in the Default Configuration Mode) are aligned to a knowledge model we call the _Hypergraph Knowledge Model_.
This model is designed to be an abstraction over the underlying data storage technology, and to provide a common interface for the Hypergraph system to interact with.

### Workflows

Below is the core Hypergraph indexing pipeline. Individual workflows are described in detail in the [dataflow](./default_dataflow.md) page.

```mermaid
---
title: Basic Hypergraph
---
stateDiagram-v2
    [*] --> LoadDocuments
    LoadDocuments --> ChunkDocuments
    ChunkDocuments --> ExtractGraph
    ChunkDocuments --> ExtractClaims
    ChunkDocuments --> EmbedChunks
    ExtractGraph --> DetectCommunities
    ExtractGraph --> EmbedEntities
    DetectCommunities --> GenerateReports
    GenerateReports --> EmbedReports
```

### LLM Caching

The Hypergraph library was designed with LLM interactions in mind, and a common setback when working with LLM APIs is various errors due to network latency, throttling, etc..
Because of these potential error cases, we've added a cache layer around LLM interactions.
When completion requests are made using the same input set (prompt and tuning parameters), we return a cached result if one exists.
This allows our indexer to be more resilient to network issues, to act idempotently, and to provide a more efficient end-user experience.

### Providers & Factories

Several subsystems within Hypergraph use a factory pattern to register and retrieve provider implementations. This allows deep customization to support your own implementations of models, storage, and so on that we haven't built into the core library.

The following subsystems use a factory pattern that allows you to register your own implementations:

- [language model](https://github.com/censeus/hypergraph/blob/main/hypergraph/language_model/factory.py) - implement your own `chat` and `embed` methods to use a model provider of choice beyond the built-in LiteLLM wrapper
- [input reader](https://github.com/censeus/hypergraph/blob/main/hypergraph/index/input/factory.py) - implement your own input document reader to support file types other than text, CSV, and JSON
- [cache](https://github.com/censeus/hypergraph/blob/main/hypergraph/cache/factory.py) - create your own cache storage location in addition to the file, blob, and CosmosDB ones we provide
- [logger](https://github.com/censeus/hypergraph/blob/main/hypergraph/logger/factory.py) - create your own log writing location in addition to the built-in file and blob storage
- [storage](https://github.com/censeus/hypergraph/blob/main/hypergraph/storage/factory.py) - create your own storage provider (database, etc.) beyond the file, blob, and CosmosDB ones built in
- [vector store](https://github.com/censeus/hypergraph/blob/main/hypergraph/vector_stores/factory.py) - implement your own vector store other than the built-in lancedb, Azure AI Search, and CosmosDB ones built in
- [pipeline + workflows](https://github.com/censeus/hypergraph/blob/main/hypergraph/index/workflows/factory.py) - implement your own workflow steps with a custom `run_workflow` function, or register an entire pipeline (list of named workflows)

The links for each of these subsystems point to the source code of the factory, which includes registration of the default built-in implementations. In addition, we have a detailed discussion of [language models](../config/models.md), which includes and example of a custom provider, and a [sample notebook](../examples_notebooks/custom_vector_store.ipynb) that demonstrates a custom vector store.

All of these factories allow you to register an impl using any string name you would like, even overriding built-in ones directly.
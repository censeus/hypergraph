# Hypergraph

**A graph-powered RAG engine for extracting structured knowledge from unstructured text.**

Maintained by <a href="https://censeus.ai"><img alt="Censeus" src="docs/img/censeus_logo.png" width="20" valign="middle"> censeus.ai</a> (forked from Microsoft's GraphRAG).

<br>

<div align="left">
  <a href="https://github.com/censeus/hypergraph/issues">
    <img alt="GitHub Issues" src="https://img.shields.io/github/issues/censeus/hypergraph">
  </a>
  <a href="https://github.com/censeus/hypergraph/discussions">
    <img alt="GitHub Discussions" src="https://img.shields.io/github/discussions/censeus/hypergraph">
  </a>
</div>

## Overview

Hypergraph is a data pipeline and transformation suite that extracts meaningful, structured data from unstructured text using the power of LLMs. It builds knowledge graphs from your documents and uses them to enhance retrieval-augmented generation (RAG) for more accurate, context-rich answers.

### Key Features

- 🔍 **Knowledge Graph Extraction** — Automatically extract entities, relationships, and communities from unstructured text
- 🧠 **Graph-Enhanced RAG** — Multiple search modes (local, global, drift, basic) powered by knowledge graph structures
- 🔗 **Entity Resolution** — LLM-based deduplication to merge entities with different surface forms
- 📊 **Community Detection** — Hierarchical community summarization for global reasoning over large corpora
- ⚡ **Incremental Indexing** — Update existing indexes without full re-processing

## Quickstart

```bash
pip install hypergraph
hypergraph init --root ./myproject
hypergraph index --root ./myproject
hypergraph query --root ./myproject --method local "What are the main themes?"
```

For a full walkthrough, see the [Getting Started Guide](https://censeus.github.io/hypergraph/get_started/).

⚠️ *Hypergraph indexing can be an expensive operation. Please read the documentation to understand the process and costs involved, and start small.*

## Documentation

📖 [Full Documentation](https://censeus.github.io/hypergraph)

- [Getting Started](https://censeus.github.io/hypergraph/get_started/)
- [Configuration](https://censeus.github.io/hypergraph/config/overview/)
- [Prompt Tuning Guide](https://censeus.github.io/hypergraph/prompt_tuning/overview/)
- [API Reference](https://censeus.github.io/hypergraph/api/)

## Development

- [Contributing Guidelines](./CONTRIBUTING.md)
- [Development Guide](./DEVELOPING.md)
- [Breaking Changes](./breaking-changes.md)

## Research

Hypergraph is based on the GraphRAG research from Microsoft Research:

- 📄 [GraphRAG: Unlocking LLM Discovery on Narrative Private Data](https://arxiv.org/pdf/2404.16130) (ArXiv)
- 📝 [Microsoft Research Blog Post](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/)

## Community

- 💬 [GitHub Discussions](https://github.com/censeus/hypergraph/discussions)
- 🐛 [Report Issues](https://github.com/censeus/hypergraph/issues)

## License

MIT License — see [LICENSE](./LICENSE) for details.

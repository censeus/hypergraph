# Hypergraph

👉 [Hypergraph Arxiv Paper](https://arxiv.org/pdf/2404.16130)<br/>
👉 [Read the docs](https://censeus.github.io/hypergraph)<br/>
👉 [Original Microsoft Research Blog Post](https://www.microsoft.com/en-us/research/blog/hypergraph-unlocking-llm-discovery-on-narrative-private-data/)

<div align="left">
  <a href="https://github.com/censeus/hypergraph/issues">
    <img alt="GitHub Issues" src="https://img.shields.io/github/issues/censeus/hypergraph">
  </a>
  <a href="https://github.com/censeus/hypergraph/discussions">
    <img alt="GitHub Discussions" src="https://img.shields.io/github/discussions/censeus/hypergraph">
  </a>
</div>

> **Note**: This project is a community-maintained fork of [microsoft/graphrag](https://github.com/microsoft/graphrag), originally developed by Microsoft Research. It is independently maintained and not affiliated with or endorsed by Microsoft.

## Overview

The Hypergraph project is a data pipeline and transformation suite that is designed to extract meaningful, structured data from unstructured text using the power of LLMs.

To learn more about Hypergraph and how it can be used to enhance your LLM's ability to reason about your private data, please visit the <a href="https://arxiv.org/pdf/2404.16130" target="_blank">Hypergraph paper on ArXiv.</a>

## Quickstart

To get started with the Hypergraph system we recommend trying the [command line quickstart](https://censeus.github.io/hypergraph/get_started/).

## Repository Guidance

This repository presents a methodology for using knowledge graph memory structures to enhance LLM outputs.

⚠️ *Warning: Hypergraph indexing can be an expensive operation, please read all of the documentation to understand the process and costs involved, and start small.*

## Diving Deeper

- To learn about our contribution guidelines, see [CONTRIBUTING.md](./CONTRIBUTING.md)
- To start developing _Hypergraph_, see [DEVELOPING.md](./DEVELOPING.md)
- Join the conversation and provide feedback in the [GitHub Discussions tab!](https://github.com/censeus/hypergraph/discussions)

## Prompt Tuning

Using _Hypergraph_ with your data out of the box may not yield the best possible results.
We strongly recommend to fine-tune your prompts following the [Prompt Tuning Guide](https://censeus.github.io/hypergraph/prompt_tuning/overview/) in our documentation.

## Versioning

Please see the [breaking changes](./breaking-changes.md) document for notes on our approach to versioning the project.

*Always run `hypergraph init --root [path] --force` between minor version bumps to ensure you have the latest config format. Run the provided migration notebook between major version bumps if you want to avoid re-indexing prior datasets. Note that this will overwrite your configuration and prompts, so backup if necessary.*

## Responsible AI FAQ

See [RAI_TRANSPARENCY.md](./RAI_TRANSPARENCY.md)

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details.

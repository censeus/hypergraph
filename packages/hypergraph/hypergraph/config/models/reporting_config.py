# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Parameterization settings for the default configuration."""

from pydantic import BaseModel, Field

from hypergraph.config.defaults import hypergraph_config_defaults
from hypergraph.config.enums import ReportingType


class ReportingConfig(BaseModel):
    """The default configuration section for Reporting."""

    type: ReportingType | str = Field(
        description="The reporting type to use.",
        default=hypergraph_config_defaults.reporting.type,
    )
    base_dir: str = Field(
        description="The base directory for reporting.",
        default=hypergraph_config_defaults.reporting.base_dir,
    )
    connection_string: str | None = Field(
        description="The reporting connection string to use.",
        default=hypergraph_config_defaults.reporting.connection_string,
    )
    container_name: str | None = Field(
        description="The reporting container name to use.",
        default=hypergraph_config_defaults.reporting.container_name,
    )
    account_url: str | None = Field(
        description="The storage account blob url to use.",
        default=hypergraph_config_defaults.reporting.storage_account_blob_url,
    )

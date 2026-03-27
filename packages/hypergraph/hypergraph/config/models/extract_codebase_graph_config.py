# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Configuration for codebase graph extraction."""

from pydantic import BaseModel, Field


class ExtractCodebaseGraphConfig(BaseModel):
    """Configuration section for codebase graph extraction."""

    root_dir: str = Field(
        description="Root directory of the codebase to scan.",
        default=".",
    )

    file_extensions: list[str] = Field(
        description="File extensions to include in parsing.",
        default=[".py"],
    )

    exclude_patterns: list[str] = Field(
        description="Glob patterns for paths to exclude.",
        default=[
            "**/venv/**",
            "**/.venv/**",
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/.git/**",
            "**/.tox/**",
            "**/dist/**",
            "**/*.egg-info/**",
        ],
    )

    extract_calls: bool = Field(
        description="Whether to extract CALLS relationships between functions.",
        default=True,
    )

    extract_decorators: bool = Field(
        description="Whether to extract DECORATES relationships.",
        default=True,
    )

    max_depth: int | None = Field(
        description="Maximum directory depth to scan (None = unlimited).",
        default=None,
    )

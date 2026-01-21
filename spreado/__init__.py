#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado - 全平台内容发布工具
"""

import os

from spreado.publisher.uploader import BaseUploader


def _load_pyproject_info():
    pyproject_path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
    try:
        try:
            import tomli

            with open(pyproject_path, "rb") as f:
                pyproject_data = tomli.load(f)
        except ImportError:
            import tomllib

            with open(pyproject_path, "rb") as f:
                pyproject_data = tomllib.load(f)

        project_info = pyproject_data.get("project", {})
        version = project_info.get("version", "0.0.0")

        authors = project_info.get("authors", [])
        if authors:
            author_info = authors[0]
            author = author_info.get("name", "")
            email = author_info.get("email", "")
        else:
            author = ""
            email = ""

        return version, author, email
    except Exception as e:
        raise RuntimeError(f"Failed to read version info from pyproject.toml: {e}")


__version__, __author__, __email__ = _load_pyproject_info()

__all__ = ["BaseUploader", "__version__", "__author__", "__email__"]

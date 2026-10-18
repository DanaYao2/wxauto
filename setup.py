#!/usr/bin/python3
# -*- coding:utf-8 -*-
# -------------------------------
# @author: dana
# @contact: dana2777@163.com
# @file: setup.py
# @time: 2026/10/18 10:58
# @desc: 
# -------------------------------

import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.dist import Distribution


class BuildPy(build_py):
    """只打包当前 Python 版本对应的 .pyd 文件。"""

    def find_data_files(self, package, src_dir):
        files = super().find_data_files(package, src_dir)
        tag = f"cp{sys.version_info.major}{sys.version_info.minor}"

        return [
            file
            for file in files
            if not file.lower().endswith(".pyd")
            or f".{tag}-" in Path(file).name.lower()
            or Path(file).name.lower().endswith(f".{tag}.pyd")
        ]


class BinaryDistribution(Distribution):
    """将 wheel 标记为与 Python 版本和平台相关。"""

    def has_ext_modules(self):
        return True


setup(
    cmdclass={"build_py": BuildPy},
    distclass=BinaryDistribution,
)

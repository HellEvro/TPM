"""
Setup для компиляции _premium_loader
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
from pathlib import Path

# Находим исходный файл
source_dir = Path('source')
source_file = source_dir / '_premium_loader_source.py'

if not source_file.exists():
    raise FileNotFoundError(f"Source file not found: {source_file}")

extensions = [
    Extension(
        '_premium_loader',
        [str(source_file)],
        language='c',
    )
]

setup(
    name='premium_loader',
    version='1.0.0',
    description='Compiled premium loader',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': "3",
            'embedsignature': False,
        }
    ),
    zip_safe=False,
)


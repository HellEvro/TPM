"""
Setup для компиляции hardware_id.py
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
from pathlib import Path

# Исходный файл
source_file = Path('hardware_id.py')

if not source_file.exists():
    raise FileNotFoundError(f"Source file not found: {source_file}")

extensions = [
    Extension(
        'hardware_id',
        [str(source_file)],
        language='c',
    )
]

setup(
    name='hardware_id',
    version='1.0.0',
    description='Compiled hardware ID',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': "3",
            'embedsignature': False,
            'boundscheck': False,
            'wraparound': False,
        }
    ),
    zip_safe=False,
)


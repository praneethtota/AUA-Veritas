# build/hooks/hook-spacy.py
# PyInstaller hook to collect all spaCy data files and language models.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files('spacy', include_py_files=True)
hiddenimports = collect_submodules('spacy')

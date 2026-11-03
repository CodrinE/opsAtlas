import os
import pytest
from cli.verify_local import main

@pytest.mark.skipif(os.getenv('RUN_OLLAMA_TESTS') != '1', reason='Requires running Ollama and installed models')
def test_real_ollama_ingestion_retrieval_and_citations():
    main()

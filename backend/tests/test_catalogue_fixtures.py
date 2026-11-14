"""The web app's catalogue fixtures are the real API answers (U-01-T11, T12).

frontend/e2e/fixtures/catalogue-products.json and catalogue-feature-matrix.json feed the
Playwright suites of the Products screen and the Package and features page; this test keeps
them equal to ``GET /api/v1/platform/catalogue/products`` and ``GET
/api/v1/catalogue/feature-matrix``. After a catalogue change, rewrite them with:

    NUMO9_WRITE_FIXTURES=1 pytest tests/test_catalogue_fixtures.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from django.utils import translation

from numo9.catalogue import presenter
from numo9.catalogue.serializers import FeatureMatrixSerializer, ProductListSerializer

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "fixtures"


def answers() -> dict[str, Any]:
    with translation.override("en-ca"):
        return {
            "catalogue-products.json": ProductListSerializer(
                {"products": presenter.products(features=True)}
            ).data,
            "catalogue-feature-matrix.json": FeatureMatrixSerializer(
                presenter.feature_matrix()
            ).data,
        }


@pytest.mark.parametrize("name", ["catalogue-products.json", "catalogue-feature-matrix.json"])
def test_fixture_equals_the_api_answer(name: str) -> None:
    answer = json.loads(json.dumps(answers()[name]))
    path = FIXTURES / name
    if os.environ.get("NUMO9_WRITE_FIXTURES"):
        path.write_text(json.dumps(answer, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == answer, f"rewrite {name} (see docstring)"

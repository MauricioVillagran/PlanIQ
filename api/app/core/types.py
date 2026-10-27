"""Tipos de API compartidos."""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema

# Pesos, kilos y cantidades: se reciben como número o texto y se devuelven siempre como texto decimal
# para no perder precisión en JavaScript.
DecimalStr = Annotated[
    Decimal,
    PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "decimal", "examples": ["1234.500"]}, mode="serialization"),
]

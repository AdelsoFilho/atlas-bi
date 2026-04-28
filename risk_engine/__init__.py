"""
Atlas BI — Risk Engine
Engine de Scoring de Crédito Cooperativo Adaptativa

Compatível com DRO 5050 S3 (Banco Central do Brasil, jun/2026).
White-box model: sem dependências de ML pesadas, auditável por BCB.
"""

from .models import AssociadoProfile, AnaliseCredito, DecisaoCredito
from .engine import CreditRiskEngine
from .compliance import DROComplianceLogger

__all__ = [
    "AssociadoProfile",
    "AnaliseCredito",
    "DecisaoCredito",
    "CreditRiskEngine",
    "DROComplianceLogger",
]
__version__ = "1.0.0"

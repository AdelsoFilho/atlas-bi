"""
DROComplianceLogger — Atlas BI
Registro estruturado para auditoria DRO 5050 S3 (Banco Central, jun/2026).

Cada análise de crédito gera um evento imutável em JSONL (uma linha por análise),
pronto para ser ingerido por SIEM, Supabase ou enviado diretamente ao BACEN.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class DROComplianceLogger:
    """
    Logger de conformidade operacional.

    Saída: arquivo JSONL (<data>.compliance.jsonl) no diretório configurado.
    Cada linha é um JSON completo de uma análise — imutável após escrita.

    Uso:
        logger = DROComplianceLogger(log_dir="./compliance_logs")
        logger.log(report_dict)
    """

    def __init__(self, log_dir: str = "./compliance_logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _current_log_path(self) -> Path:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"{date_str}.compliance.jsonl"

    def log(self, report: dict) -> str:
        """
        Persiste o relatório de análise em JSONL.
        Retorna o caminho absoluto do arquivo de log.
        """
        entry = {
            **report,
            "_log_version": "1.0",
            "_logged_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        log_path = self._current_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return str(log_path.resolve())

    def audit_summary(self, date_str: Optional[str] = None) -> dict:
        """
        Lê o arquivo do dia e retorna métricas agregadas para o painel de conformidade.
        date_str: "YYYY-MM-DD" (default: hoje)
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        log_path = self.log_dir / f"{date_str}.compliance.jsonl"
        if not log_path.exists():
            return {"erro": f"Nenhum log encontrado para {date_str}"}

        registros = []
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    registros.append(json.loads(line))

        total = len(registros)
        if total == 0:
            return {"total_analises": 0}

        decisoes: dict[str, int] = {}
        niveis_bcb: dict[str, int] = {}
        flags_count = 0
        aptos_bacen = 0
        pd_values: list[float] = []

        for r in registros:
            d = r.get("resultado", {}).get("decisao", "DESCONHECIDO")
            decisoes[d] = decisoes.get(d, 0) + 1

            n = r.get("scoring", {}).get("nivel_risco_bcb", "?")
            niveis_bcb[n] = niveis_bcb.get(n, 0) + 1

            conf = r.get("conformidade_dro5050", {})
            flags_count += len(conf.get("flags_operacionais", []))
            if conf.get("apto_remessa_bacen"):
                aptos_bacen += 1

            pd_val = r.get("scoring", {}).get("probabilidade_default_pct")
            if pd_val is not None:
                pd_values.append(pd_val)

        pd_medio = sum(pd_values) / len(pd_values) if pd_values else 0.0

        return {
            "data":                    date_str,
            "total_analises":          total,
            "distribuicao_decisoes":   decisoes,
            "distribuicao_niveis_bcb": niveis_bcb,
            "total_flags_operacionais": flags_count,
            "analises_aptas_bacen":    aptos_bacen,
            "pct_aptas_bacen":         round(aptos_bacen / total * 100, 1),
            "pd_medio_carteira_pct":   round(pd_medio, 2),
            "arquivo_log":             str(log_path.resolve()),
        }

import re

import pandas as pd

_REFERENCE_RE = re.compile(r"^REF-\d{6}$")


def repair_documents(extracted: pd.DataFrame) -> pd.DataFrame:
    repaired = extracted.copy()
    repaired["repair_actions"] = [[] for _ in range(len(repaired))]
    for index, row in repaired.iterrows():
        actions = []
        reference = str(row.get("reference_id", ""))
        normalized_reference = reference.strip().upper()
        if normalized_reference != reference:
            repaired.at[index, "reference_id"] = normalized_reference
            actions.append("normalize_reference")
        date_value = str(row.get("document_date", ""))
        normalized_date = date_value.strip().replace("/", "-")
        if normalized_date != date_value:
            repaired.at[index, "document_date"] = normalized_date
            actions.append("normalize_date_separator")
        amount = row.get("total_amount")
        if isinstance(amount, str):
            try:
                repaired.at[index, "total_amount"] = float(amount.replace(",", "").replace("$", ""))
                actions.append("normalize_amount")
            except ValueError:
                pass
        repaired.at[index, "repair_actions"] = actions
    return repaired

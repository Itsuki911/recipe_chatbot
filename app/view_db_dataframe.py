from __future__ import annotations

import pandas as pd

from app.database import fetch_recipes


def recipes_dataframe() -> pd.DataFrame:
    df = pd.DataFrame(fetch_recipes())
    if df.empty:
        return df
    preferred_columns = [
        "id",
        "created_at",
        "recipe_name",
        "question",
        "health_focus_explanation",
        "ingredients",
        "steps",
        "source_urls",
    ]
    return df[[column for column in preferred_columns if column in df.columns]]


if __name__ == "__main__":
    df = recipes_dataframe()
    if df.empty:
        print("No recipes are saved yet.")
    else:
        print(df.to_markdown(index=False))

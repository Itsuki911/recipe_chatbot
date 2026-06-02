from __future__ import annotations

import pandas as pd

from app.database import fetch_recipes


def recipes_dataframe() -> pd.DataFrame:
    # DBから取得したlist[dict]をpandas DataFrameへ変換します。
    df = pd.DataFrame(fetch_recipes())
    if df.empty:
        return df
    # JSONB列を含むため、見たい列だけを決まった順番で表示します。
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
    # ターミナルから `python -m app.view_db_dataframe` で保存済みレシピを確認できます。
    df = recipes_dataframe()
    if df.empty:
        print("No recipes are saved yet.")
    else:
        print(df.to_markdown(index=False))

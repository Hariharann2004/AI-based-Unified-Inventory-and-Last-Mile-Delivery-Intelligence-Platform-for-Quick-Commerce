import pandas as pd


def normalize_categorical_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with stable string values for categorical inputs."""
    result = frame.copy()
    for column in result.columns:
        if not pd.api.types.is_numeric_dtype(result[column]):
            result[column] = result[column].fillna("Unknown").astype(str)
    return result

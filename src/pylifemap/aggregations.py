"""
Data aggregation functions.
"""

from typing import Literal

import pandas as pd
import polars as pl

from pylifemap.utils import LMDATA


def ensure_polars(d: pd.DataFrame | pl.DataFrame) -> pl.DataFrame:
    """
    Ensure that the argument is a pandas or polars DataFrame. If it is a pandas
    DataFrame, converts it to polars.

    Parameters
    ----------
    d : pd.DataFrame | pl.DataFrame
        Object to check and convert.

    Returns
    -------
    pl.DataFrame
        Returned polars DataFrame.

    Raises
    ------
    TypeError
        If `d` is neither a polars or pandas DataFrame.
    """
    if isinstance(d, pd.DataFrame):
        return pl.DataFrame(d)
    if isinstance(d, pl.DataFrame):
        return d
    msg = "data must be a pandas or polars DataFrame."
    raise TypeError(msg)


def ensure_int32(d: pl.DataFrame, taxid_col: str) -> pl.DataFrame:
    """
    Ensure that the `taxid` col of the `data` DataFrame is of type pl.Int32.

    Parameters
    ----------
    d : pl.DataFrame
        DataFrame to check.
    taxid_col : str
        DataFrame column name to check.

    Returns
    -------
    pl.DataFrame
        DataFrame with `taxid_col` converted to `pl.Int32` if necessary.
    """
    return d.with_columns(pl.col(taxid_col).cast(pl.Int32))


def ensure_column_exists(d: pl.DataFrame, column: str) -> None:
    """
    Ensure that a column name is present in a DataFrame.

    Parameters
    ----------
    d : pl.DataFrame
        Polars DataFrame to check for.
    column : str
        Column name to check for.

    Raises
    ------
    ValueError
        If the column is not part of the DataFrame.
    """
    if column not in d.columns:
        msg = f"{column} is not a column of the DataFrame."
        raise ValueError(msg)


def aggregate_num(
    d: pd.DataFrame | pl.DataFrame,
    column: str,
    *,
    fn: Literal["sum", "mean", "min", "max", "median"] = "sum",
    taxid_col: str = "taxid",
) -> pl.DataFrame:
    """
    Aggregates a numerical variable in a DataFrame with taxonomy ids along the branches
    of the lifemap tree.

    Parameters
    ----------
    d : pd.DataFrame | pl.DataFrame
        DataFrame to aggregate data from.
    column : str
        Name of the `d` column to aggregate.
    fn : {"sum", "mean", "min", "max", "median"}
        Function used to aggregate the values, by default "sum".
    taxid_col : str, optional
        Name of the `d` column containing taxonomy ids, by default "taxid"

    Returns
    -------
    pl.DataFrame
        Aggregated DataFrame.

    Raises
    ------
    ValueError
        If `column` is equal to "taxid".
    ValueError
        If `fn` is not on the allowed values.

    See also
    --------
    aggregate_count : aggregation of the number of observations.
    aggregate_cat : aggregation of the values counts of a categorical variable.
    """
    d = ensure_polars(d)
    ensure_column_exists(d, column)
    ensure_column_exists(d, taxid_col)
    d = ensure_int32(d, taxid_col)

    # Column can't be taxid to avoid conflicts later
    if column == "taxid":
        msg = (
            "Can't aggregate on the taxid column, please make a copy and"
            " rename it before."
        )
        raise ValueError(msg)
    # Check aggregation function
    fn_dict = {
        "sum": pl.sum,
        "mean": pl.mean,
        "min": pl.min,
        "max": pl.max,
        "median": pl.median,
    }
    if fn not in fn_dict:
        msg = f"fn value must be one of {fn_dict.keys()}."
        raise ValueError(msg)
    else:
        agg_fn = fn_dict[fn]
    # Generate dataframe of parent values
    d = d.select(pl.col(taxid_col).alias("taxid"), pl.col(column))
    res = d.join(
        LMDATA.select("taxid", "pylifemap_ascend"), on="taxid", how="left"
    ).explode("pylifemap_ascend")
    # Get original nodes data with itself as parent in order to take into account
    # the nodes values
    obs = d.with_columns(pl.col("taxid").alias("pylifemap_ascend"))
    # Concat parent and node values
    res = pl.concat([res, obs])
    # Group by parent and aggregate values
    res = (
        res.group_by(["pylifemap_ascend"])
        .agg(agg_fn(column))
        .rename({"pylifemap_ascend": "taxid"})
    )
    res = res.sort("taxid")
    return res


def aggregate_count(
    d: pd.DataFrame | pl.DataFrame, *, result_col: str = "n", taxid_col: str = "taxid"
) -> pl.DataFrame:
    """
    Aggregates nodes count in a DataFrame with taxonomy ids along the branches
    of the lifemap tree.


    Parameters
    ----------
    d : pd.DataFrame | pl.DataFrame
        DataFrame to aggregate data from.
    result_col : str, optional
        Name of the column created to store the counts, by default "n"
    taxid_col : str, optional
        Name of the `d` column containing taxonomy ids, by default "taxid"

    Returns
    -------
    pl.DataFrame
        Aggregated DataFrame.

    See also
    --------
    aggregate_num : aggregation of a numeric variable.
    aggregate_cat : aggregation of the values counts of a categorical variable.

    """
    d = ensure_polars(d)
    ensure_column_exists(d, taxid_col)
    d = ensure_int32(d, taxid_col)
    # Generate dataframe of parent counts
    d = d.select(pl.col(taxid_col).alias("taxid"))
    res = d.join(
        LMDATA.select("taxid", "pylifemap_ascend"), on="taxid", how="left"
    ).explode("pylifemap_ascend")
    # Get original nodes with itself as parent in order to take into account
    # the nodes themselves
    obs = d.with_columns(pl.col("taxid").alias("pylifemap_ascend"))
    # Concat parent and node values
    res = pl.concat([res, obs])
    # Group by parent and count
    res = (
        res.group_by("pylifemap_ascend")
        .len(name=result_col)
        .rename({"pylifemap_ascend": "taxid"})
    )
    res = res.sort("taxid")
    return res


def aggregate_cat(
    d: pd.DataFrame | pl.DataFrame,
    column: str,
    *,
    keep_leaves: bool = False,
    taxid_col: str = "taxid",
) -> pl.DataFrame:

    d = ensure_polars(d)
    d = ensure_int32(d, taxid_col)
    d = d.select(pl.col(taxid_col).alias("taxid"), pl.col(column))
    levels = d.get_column(column).unique()
    res = (
        d.join(LMDATA.select("taxid", "pylifemap_ascend"), on="taxid", how="left")
        .explode("pylifemap_ascend")
        .group_by(["pylifemap_ascend", column])
        .count()
        .rename({"pylifemap_ascend": "taxid"})
    )
    res = res.pivot(index="taxid", columns=column, values="count").fill_null(0)
    res = preprocess_counts(res, columns=levels.to_list(), result_col=column)
    if keep_leaves:
        leaves = d.select([taxid_col, column]).with_columns(
            pl.lit("leaf").alias("pylifemap_count_type")
        )
        res = pl.concat([res, leaves], how="vertical_relaxed")
    return res


def preprocess_counts(
    d: pd.DataFrame | pl.DataFrame,
    columns: list,
    result_col: str,
) -> pl.DataFrame:
    d = ensure_polars(d)
    d = d.with_columns(
        pl.struct(pl.col(columns)).struct.json_encode().alias(result_col),
        pl.lit("count").alias("pylifemap_count_type"),
    ).select(pl.all().exclude(columns))
    return d
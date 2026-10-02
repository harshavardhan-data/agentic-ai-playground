from models.schema import DataFrameInspectionResult
from models.tool_input_schemas import DataFrameInspectionInput
from models.tool_context import ToolContext
from tools.registry import registry
import pandas as pd
from models.execution_results import ToolExecutionResult,ToolStatus
from models.data_profiling import ColumnProfile,NumericProfile,DataProfileResult


@registry.register(scope="data",input_schema=DataFrameInspectionInput)
def inspect_dataframe(__context:ToolContext) -> ToolExecutionResult:

    df=__context.session.sandbox_state.get("df")

    if df is None:
        raise ValueError("No DataFrame is Loaded in the current session")

    # 1. Compute all stats across ALL columns simultaneously (Vectorized)
    columns_df = pd.DataFrame(
        {
            "name": df.columns,
            "data_type": df.dtypes.astype(str),
            "nullable": df.isna().any(),
        }
    )

    # 2. Convert to list of dicts instantly and validate with Pydantic
    result = DataFrameInspectionResult(
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns_df.to_dict(orient="records"),
    )

    return ToolExecutionResult.ok(tool_name="inspect_dataframe",
                               output=result.model_dump(),
                               status=ToolStatus.SUCCESS)



@registry.register(scope="data",input_schema=DataFrameInspectionInput)
def profile_dataset(__context:ToolContext) -> ToolExecutionResult :


    df=__context.session.sandbox_state.get("df")

    if df is None:
        raise ValueError("No DataFrame is Loaded in the current session")

    columns_df=pd.DataFrame(
        {
            "name":df.columns,
            "dtype":df.dtypes.astype(str),
            "missing_count":df.isnull().sum(),
            "missing_pct":df.isna().mean()*100,
            "unique_count":df.nunique(),

        }
    )

    columns_list=[ColumnProfile(**row) for row in columns_df.to_dict(orient="records")]

    numeric_df=df.select_dtypes(include="number").dropna(axis=1,how="all")

    numeric_profile_dict={}

    if not numeric_df.empty:
    # 1. Compute stats & round
        numeric_stats = numeric_df.agg(["min", "max", "mean", "median"]).T.round(2)
        
        # 2. Convert to dict
        raw_stats_dict = numeric_stats.to_dict(orient="index")
        
        # 3. Build Pydantic models safely
        numeric_profile_dict = {
            col_name: NumericProfile(
                # Replace any stray NaN/None with 0.0 only at instantiation level
                **{key: (None if pd.isna(val) else float(val)) for key, val in stats_dict.items()}
            )
            for col_name, stats_dict in raw_stats_dict.items()
        }
    result = DataProfileResult(
        row_count=len(df),column_count=len(df.columns),
        columns=columns_list,numeric_profiles=numeric_profile_dict
    )

    return ToolExecutionResult.ok(tool_name="profile_dataset",output=result.model_dump(),status=ToolStatus.SUCCESS)





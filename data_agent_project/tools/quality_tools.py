from models.analysis_tools_schemas import RawCandidate
from tools.profiler import DataProfileResult
import pandas as pd


def detect_quality_findings(df:pd.DataFrame,profile_result:DataProfileResult) -> RawCandidate:

    candidates=[]
    for flag in profile_result.quality_flags:
        if flag['severity'] == 'info':
            continue    
        metric=flag['column']
        dimension=flag['type']
        candidate=RawCandidate(metric=metric,category='quality',dimension=dimension,
                               magnitude=1,raw_context=flag,
                               birth_evidence={"content":{"check":"quality_flag",},"result":flag})

        candidates.append(candidate)


    return candidates[:10]








    


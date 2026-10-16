"""Interpret raw diagnostics, retaining the declared visual-only drop counter."""
EXPECTED_NO_COUNTERPART={'unmapped_unit:SpearGoblin_Dummy'}

def problems(row):
    issues=list(row.get('issues',[]))
    if row.get('error'):issues.append(row['error'])
    unmapped={k:v for k,v in row.get('unmapped',{}).items() if v and k not in EXPECTED_NO_COUNTERPART}
    if 'unmapped public rows' in issues and not unmapped:
        issues.remove('unmapped public rows')
    return issues

# common/const/filter_mapper.py

from sqlalchemy import not_, or_


FILTER_MAPPER = {
    # 비교 연산자
    "equal": lambda col, v: col == v,
    "not": lambda col, v: not_(col == v),
    "not_equal": lambda col, v: col != v,

    # 대소 비교
    "more_than": lambda col, v: col > v,
    "less_than": lambda col, v: col < v,
    "more_than_or_equal": lambda col, v: col >= v,
    "less_than_or_equal": lambda col, v: col <= v,
    # 별칭 (호환성)
    "greater_than": lambda col, v: col > v,
    "greater_than_or_equal": lambda col, v: col >= v,
    # 범위 필터 별칭 (from/to)
    "from": lambda col, v: col >= v,
    "to": lambda col, v: col <= v,

    # 문자열 검색 (부분 일치)
    "like": lambda col, v: col.like(f"%{v.replace('%', r'%%') if isinstance(v, str) else v}%"),
    "i_like": lambda col, v: col.ilike(f"%{v.replace('%', r'%%') if isinstance(v, str) else v}%"),
    "not_like": lambda col, v: ~col.like(f"%{v.replace('%', r'%%') if isinstance(v, str) else v}%"),
    "not_i_like": lambda col, v: ~col.ilike(f"%{v.replace('%', r'%%') if isinstance(v, str) else v}%"),

    # 문자열 검색 (시작/끝)
    "starts_with": lambda col, v: col.like(f"{v.replace('%', r'%%') if isinstance(v, str) else v}%"),
    "ends_with": lambda col, v: col.like(f"%{v.replace('%', r'%%') if isinstance(v, str) else v}"),

    # 범위/목록
    "in": lambda col, v: col.in_(v if isinstance(v, (list, tuple)) else v.split(",")),
    "not_in": lambda col, v: ~col.in_(v if isinstance(v, (list, tuple)) else v.split(",")),
    "between": lambda col, v: col.between(*(v if isinstance(v, (list, tuple)) else v.split(","))),

    # NULL 체크
    "is_null": lambda col, v: col.is_(None) if v else col.is_not(None),
    "is_not_null": lambda col, v: col.is_not(None) if v else col.is_(None),

    # IN + NULL (멀티셀렉트에서 "없음" 옵션 포함 시)
    "in_or_null": lambda col, v: or_(
        col.in_(v if isinstance(v, (list, tuple)) else v.split(",")),
        col.is_(None),
    ),
}

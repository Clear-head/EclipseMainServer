def add_address(do, si, gu, detail_address):
    return (
            (do + " " if do is not None else "") +
            (si + " " if si is not None else "") +
            (gu + " " if gu is not None else "") +
            (detail_address if detail_address is not None else "")
    )
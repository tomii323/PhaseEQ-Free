def available_adapters():
    from phase_fir_designer.edition import pro_feature_available
    if not pro_feature_available():
        return ()
    from .registry import available_adapters as available
    return available()


def adapter_by_id(adapter_id):
    for adapter in available_adapters():
        if adapter.adapter_id == adapter_id:
            return adapter
    raise KeyError(f"unknown or unavailable DSP export adapter: {adapter_id}")

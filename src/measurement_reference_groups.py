"""Validate independent acoustic references without inventing inter-group timing."""
from timing_provenance import trusted_relative_arrivals, causal_delays_from_relative_arrivals


def independent_reference_delays(channel_ids, provenance, groups, *, sample_rate_hz):
    from timing_provenance import normalize_timing_provenance, trusted_reference_provenance
    if set(groups) != set(channel_ids) or any(not groups[c] for c in channel_ids):
        return None
    for channel in channel_ids:
        item = normalize_timing_provenance(provenance.get(channel))
        if item is None or item.reference_group != groups[channel]:
            return None
    delays = {}
    for group in dict.fromkeys(groups[c] for c in channel_ids):
        members = tuple(c for c in channel_ids if groups[c] == group)
        arrivals = trusted_relative_arrivals(members, provenance, sample_rate_hz=sample_rate_hz)
        if arrivals is None:
            return None
        # The group's reference must itself be measured in this group.
        first = normalize_timing_provenance(provenance[members[0]])
        reference = first.reference_tweeter_channel_id
        if reference not in members or trusted_reference_provenance(provenance[reference]) is None:
            return None
        delays.update(causal_delays_from_relative_arrivals(arrivals))
    return delays

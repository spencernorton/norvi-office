// Identical-caption windows may safely share a boundary only when every
// possible observation agrees. Conflicting boundaries still fail opaque.
export function selectGeometry(matches) {
    const first = matches[0];
    if (!first)
        return null;
    return matches.every(item => item.edge === first.edge && item.join === first.join &&
        item.join_start === first.join_start) ? first : null;
}

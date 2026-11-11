// Identical-caption windows may safely share a boundary only when every
// possible observation agrees. Conflicting boundaries still fail opaque.
export function selectGeometry(matches) {
    const first = matches[0];
    if (!first)
        return null;
    return matches.every(item => item.edge === first.edge && item.join === first.join &&
        item.join_start === first.join_start) ? first : null;
}

// A draw-time report is acknowledged before the new Wayland buffer commits.
// It is not associated with that buffer: expanding a ribbon mask immediately
// could expose the previous frame's document pixels. Keep direct-desktop glass
// inside the fixed GTK titlebar until buffer-bound ribbon masking is qualified.
export function titlebarGeometry(geometry) {
    if (!geometry || !Number.isInteger(geometry.join_start) || geometry.join_start <= 0 ||
        geometry.join_start >= geometry.join || geometry.join_start >= geometry.edge)
        return null;
    return {...geometry, edge: geometry.join_start};
}

// Native reports enroll blur only. No message order or geometry can grant a
// compositor alpha mask: alpha must already be in the client-painted buffer.
export function nativeBackdrop(reports, now, maxAge, supported, dark) {
    return {
        mask: false,
        blur: Boolean(supported && dark && reports.length && reports.every(item =>
            item.client_alpha === true && now >= item.at && now - item.at < maxAge)),
    };
}

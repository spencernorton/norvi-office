import {selectGeometry, titlebarGeometry} from '../norvi-office/experiments/wayland-glass/extension/geometryPolicy.js';

const observed = {edge: 164, join: 52, join_start: 45};
const cases = [
    [[], null],
    [[observed], observed],
    [[observed, {...observed}], observed],
    [[observed, {...observed, edge: 120}], null],
    [[observed, {...observed, join: 54}], null],
    [[observed, {...observed, join_start: 48}], null],
];
for (const [input, expected] of cases) {
    if (selectGeometry(input) !== expected)
        throw new Error('Unsafe or unnecessarily ambiguous desktop boundary');
}
print(`${cases.length} native geometry policy checks passed`);

// Either order can be observed around a client buffer commit. A growing ribbon
// must never extend the native mask beyond the fixed titlebar in either frame.
const oldFrame = {edge: 104, join: 52, join_start: 45};
const newFrame = {edge: 188, join: 52, join_start: 45};
for (const geometry of [oldFrame, newFrame, oldFrame]) {
    const safe = titlebarGeometry(geometry);
    if (safe?.edge !== 45 || safe.edge >= oldFrame.edge || safe.edge >= newFrame.edge)
        throw new Error('Unqualified ribbon expansion reached document pixels');
}
for (const geometry of [null, {...observed, join_start: undefined}, {...observed, join_start: 0},
    {...observed, join_start: 60}, {...observed, join_start: 164}]) {
    if (titlebarGeometry(geometry) !== null)
        throw new Error('Missing or invalid titlebar geometry did not fail opaque');
}
print('8 native titlebar-only safety checks passed');

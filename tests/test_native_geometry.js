import {selectGeometry} from '../norvi-office/experiments/wayland-glass/extension/geometryPolicy.js';

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

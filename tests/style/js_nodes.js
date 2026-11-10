// SPDX-License-Identifier: GPL-2.0-or-later
// Where gjs's own parser finds code, strings, template text, and regex literals, so the
// bundle check can tell when its own scanner misread one: a misread can hide code.
//
//   gjs -m tests/style/js_nodes.js SOURCES.json
//
// SOURCES.json holds a list of JavaScript sources. This prints a list with one entry for
// each: a list of [kind, line, column] for every leaf the parser places, or the parser's
// error. Lines and columns count from 1.

import GLib from 'gi://GLib';

const LEAVES = new Set(['Identifier', 'ThisExpression', 'Super', 'Literal']);

function kindOf(node) {
    if (node.type !== 'Literal')
        return 'code';
    if (node.value instanceof RegExp)
        return 'regex';
    return typeof node.value === 'string' ? 'string' : 'code';
}

function walk(node, found) {
    if (!node || typeof node.type !== 'string')
        return;
    if (node.type === 'TemplateLiteral') {
        if (node.loc)
            found.push(['template', node.loc.start.line, node.loc.start.column]);
        for (const element of node.elements) {
            if (element.type === 'Literal' && typeof element.value === 'string')
                found.push(['template', element.loc.start.line, element.loc.start.column]);
            else
                walk(element, found);
        }
        return;
    }
    if (node.loc && LEAVES.has(node.type))
        found.push([kindOf(node), node.loc.start.line, node.loc.start.column]);
    for (const [key, value] of Object.entries(node)) {
        if (key === 'loc')
            continue;
        if (Array.isArray(value))
            value.forEach(child => walk(child, found));
        else if (value && typeof value === 'object')
            walk(value, found);
    }
}

const [, contents] = GLib.file_get_contents(ARGV[0]);
const sources = JSON.parse(new TextDecoder().decode(contents));
print(JSON.stringify(sources.map(source => {
    let ast;
    try {
        ast = Reflect.parse(source, {target: 'module'});
    } catch (error) {
        if (!(error instanceof SyntaxError))
            throw error;
        return error.message;
    }
    const found = [];
    walk(ast, found);
    return found;
})));

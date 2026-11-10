// SPDX-License-Identifier: GPL-2.0-or-later
// Where gjs's own parser finds code, strings, template text, and regex literals, so the
// bundle check can tell when its own scanner misread one: a misread can hide code.
//
//   gjs -m tests/style/js_nodes.js SOURCES.json
//
// SOURCES.json holds a list of JavaScript sources. This prints a list with one entry for
// each: a list of [kind, line, column] for every leaf the parser places, or the parser's
// error. Lines and columns count from 1, and a column counts UTF-16 code units.

import GLib from 'gi://GLib';

const LEAVES = new Set(['Identifier', 'ThisExpression', 'Super', 'Literal']);
// gjs 1.80 counts columns from 0, and gjs 1.88 from 1: take this gjs's own first column.
const ORIGIN = Reflect.parse('x;').body[0].loc.start.column;

function place(kind, loc) {
    return [kind, loc.start.line, loc.start.column - ORIGIN + 1];
}

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
            found.push(place('template', node.loc));
        for (const element of node.elements) {
            if (element.type === 'Literal' && typeof element.value === 'string')
                found.push(place('template', element.loc));
            else
                walk(element, found);
        }
        return;
    }
    if (node.loc && LEAVES.has(node.type))
        found.push(place(kindOf(node), node.loc));
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

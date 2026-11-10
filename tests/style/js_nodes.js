// SPDX-License-Identifier: GPL-2.0-or-later
// What gjs's own parser reads in each source, for the undo check in test_bundle.py. Reading
// the syntax tree, not the text, a comment, a string, or a regex can never pass for code,
// and a name the parser can resolve, such as obj['con' + 'nect'], is read as that name.
//
//   gjs -m tests/style/js_nodes.js SOURCES.json
//
// SOURCES.json holds a list of JavaScript sources. This prints a list with one entry for
// each, or the parser's error:
//   calls: every call, as [line, name, receiver, form, kept, args, use]. form is dot for
//     receiver.name(...), bare for name(...), and optional or computed otherwise. kept is
//     what the call's result is assigned to, if anything. use says how a
//     global.compositor.get_laters() call is used: hold, add, remove, or null.
//   names: every place a name stands, as [line, name, site]: site is the index of the call
//     it names, declared for the name a const, let, or var declares, or other.
//   holds: the names that hold global.compositor.get_laters() in a statement of their own.
//   held: each place a held name stands, as [line, name, role]: role is hold, assigned,
//     laters for the receiver of its own .add( or .remove(, or other.
//   glib: the names GLib goes by in the file.

import GLib from 'gi://GLib';

const LATERS = 'global.compositor.get_laters()';

// The text of a receiver, a kept name, or an argument that the check can compare, or null:
// a name, this, a dotted path through them, a call of one with no arguments, or a string.
function path(node) {
    switch (node?.type) {
    case 'Identifier':
        return node.name;
    case 'ThisExpression':
        return 'this';
    case 'Literal':
        return typeof node.value === 'string' ? `'${node.value}'` : null;
    case 'MemberExpression': {
        const object = path(node.object);
        return node.computed || object === null ? null : `${object}.${node.property.name}`;
    }
    case 'CallExpression': {
        // A call with no arguments, such as global.backend.get_cursor_tracker().
        const callee = path(node.callee);
        return callee !== null && node.arguments.length === 0 ? `${callee}()` : null;
    }
    default:
        return null;
    }
}

function lineOf(node, parent) {
    return node.loc?.start.line ?? parent?.loc?.start.line ?? 0;
}

function children(node) {
    const found = [];
    for (const [key, value] of Object.entries(node)) {
        if (key === 'loc' || key === 'called' || key === 'call')
            continue;
        for (const child of Array.isArray(value) ? value : [value]) {
            if (child && typeof child === 'object' && typeof child.type === 'string')
                found.push([key, child]);
        }
    }
    return found;
}

// A statement of its own that holds the laters, as [name, the call, the name's node]:
// const laters = <LATERS>, or this._laters = <LATERS>.
function holdOf(node) {
    if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier' &&
        node.init?.type === 'CallExpression' && path(node.init) === LATERS)
        return [node.id.name, node.init, node.id];
    const assignment = node.type === 'ExpressionStatement' ? node.expression : null;
    if (assignment?.type === 'AssignmentExpression' && assignment.operator === '=' &&
        assignment.right.type === 'CallExpression' && path(assignment.right) === LATERS) {
        const target = assignment.left;
        if (target.type === 'Identifier' || (target.type === 'MemberExpression' &&
            !target.computed && target.object.type === 'ThisExpression'))
            return [path(target), assignment.right, target];
    }
    return null;
}

function isMember(node) {
    return node.type === 'MemberExpression' || node.type === 'OptionalMemberExpression';
}

// The receiver of its own .add( or .remove(: a member of that name, called.
function addsOrRemoves(parent, key) {
    return parent?.type === 'MemberExpression' && key === 'object' && !parent.computed &&
        ['add', 'remove'].includes(parent.property.name) && parent.called === true;
}

function read(ast) {
    const calls = [], names = [], held = [];
    const holds = new Map(), glib = new Set(['GLib']);

    // First GLib's names, and the names that hold the laters.
    (function scan(node) {
        if (node.type === 'ImportDeclaration' && node.moduleRequest?.source.value === 'gi://GLib') {
            for (const specifier of node.specifiers)
                glib.add(specifier.name.name);
        }
        if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier' &&
            path(node.init) === 'imports.gi.GLib')
            glib.add(node.id.name);
        const hold = holdOf(node);
        if (hold)
            holds.set(hold[1], hold);
        for (const [, child] of children(node))
            scan(child);
    })(ast);
    const heldNames = new Set([...holds.values()].map(([name]) => name));
    const holdTargets = new Set([...holds.values()].map(([, , target]) => target));

    function call(node, parent, key) {
        const callee = node.callee;
        let form = 'other', name = null, receiver = null;
        if (node.type === 'OptionalCallExpression' || callee.type === 'OptionalMemberExpression') {
            form = 'optional';
            name = callee.computed ? null : callee.property?.name ?? callee.name ?? null;
        } else if (callee.type === 'MemberExpression' && !callee.computed) {
            form = 'dot';
            name = callee.property.name;
            receiver = path(callee.object);
        } else if (callee.type === 'MemberExpression') {
            form = 'computed';
        } else if (callee.type === 'Identifier') {
            form = 'bare';
            name = callee.name;
            receiver = '';
        }
        let kept = null;
        if (parent?.type === 'AssignmentExpression' && key === 'right' && parent.operator === '=')
            kept = path(parent.left);
        else if (parent?.type === 'VariableDeclarator' && key === 'init')
            kept = path(parent.id);
        let use = null;
        if (path(node) === LATERS) {
            if (holds.has(node))
                use = 'hold';
            else if (addsOrRemoves(parent, key))
                use = parent.property.name;
        }
        calls.push([lineOf(node, parent), name, receiver, form, kept,
            node.arguments.map(argument => path(argument)), use]);
        return calls.length - 1;
    }

    function role(node, parent, key) {
        if (holdTargets.has(node))
            return 'hold';
        if (parent?.type === 'AssignmentExpression' && key === 'left')
            return 'assigned';
        return addsOrRemoves(parent, key) ? 'laters' : 'other';
    }

    (function walk(node, parent, key) {
        if (node.type === 'CallExpression' || node.type === 'OptionalCallExpression') {
            // Marked before the callee is walked, so it knows it is called, and by which call.
            node.callee.called = true;
            node.callee.call = call(node, parent, key);
        }
        const line = lineOf(node, parent);
        const here = node.type === 'Identifier' || node.type === 'MemberExpression'
            ? path(node) : null;
        if (here !== null && heldNames.has(here))
            held.push([line, here, role(node, parent, key)]);
        const site = node.called === true ? node.call : 'other';
        if (node.type === 'Identifier') {
            const declared = parent?.type === 'VariableDeclarator' && key === 'id';
            names.push([line, node.name, declared ? 'declared' : site]);
        }
        if (isMember(node) && !node.computed)
            names.push([line, node.property.name, site]);
        if (isMember(node) && node.computed && typeof node.property.value === 'string')
            names.push([line, node.property.value, 'other']);
        if (node.type === 'Property' && node.key.type === 'Identifier' && !node.shorthand)
            names.push([line, node.key.name, 'other']);
        if (node.type === 'ClassMethod')
            names.push([line, node.name.name, 'other']);
        for (const [childKey, child] of children(node)) {
            // A member's property name, a property's key, and a method's name are read above.
            const named = (isMember(node) && !node.computed && childKey === 'property') ||
                (node.type === 'Property' && !node.shorthand && childKey === 'key') ||
                (node.type === 'ClassMethod' && childKey === 'name');
            if (!named)
                walk(child, node, childKey);
        }
    })(ast, null, null);

    return {calls, names, holds: [...heldNames], held, glib: [...glib]};
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
    return read(ast);
})));

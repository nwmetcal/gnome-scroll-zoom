// SPDX-License-Identifier: GPL-2.0-or-later
// What gjs's own parser reads in each source, for the undo check in test_bundle.py. Reading
// the syntax tree, not the text, a comment, a string, or a regex can never pass for code,
// and a name the parser can resolve, such as obj['con' + 'nect'], is read as that name.
//
//   gjs -m tests/style/js_nodes.js SOURCES.json
//
// SOURCES.json holds a list of JavaScript sources. This prints a list with one entry for
// each, or the parser's error:
//   calls: every call, as [line, name, receiver, form, kept, args, use, within]. form is dot
//     for receiver.name(...), bare for name(...), optional or computed for those, and other
//     for a callee that is none of them, such as (0, f)(x). kept is
//     what the call's result is assigned to, if anything. use says how a
//     global.compositor.get_laters() call is used: hold, add, remove, or null.
//   names: every place a name stands, as [line, name, site, within]: site is the index of the
//     call it names, declared for the name a const, let, or var declares, key for a class
//     method's own name, string for a string that holds a name alone, or other. A dynamic
//     import stands as the name import().
//   within, for a call or a name: the name of the function it stands in, by which a call can
//     reach it: a class's method or field, a declared function, or a function kept in a name,
//     a member, or an object's key. An unnamed function, such as a callback, is part of the
//     one around it, and null is a module's own code, outside every function.
//   holds: the plain names that hold global.compositor.get_laters() in a statement of their
//     own, and that no other module can import. A property of this or of any other object
//     is never one: an object goes where a reading of one file cannot follow it.
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

// A statement of its own that holds the laters in a plain name, as [name, the call, the
// name's node]: const laters = <LATERS>, or laters = <LATERS>.
function holdOf(node) {
    if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier' &&
        node.init?.type === 'CallExpression' && path(node.init) === LATERS)
        return [node.id.name, node.init, node.id];
    const assignment = node.type === 'ExpressionStatement' ? node.expression : null;
    if (assignment?.type === 'AssignmentExpression' && assignment.operator === '=' &&
        assignment.left.type === 'Identifier' &&
        assignment.right.type === 'CallExpression' && path(assignment.right) === LATERS)
        return [assignment.left.name, assignment.right, assignment.left];
    return null;
}

const FUNCTIONS = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']);

// A key's or a member's name, when the parser can read it as one.
function keyName(node, computed) {
    if (node?.type === 'Identifier' && !computed)
        return node.name;
    return node?.type === 'Literal' && typeof node.value === 'string' ? node.value : null;
}

// The name a function goes by, from where it stands, or null for an unnamed one.
function functionName(node, parent, key) {
    if (node.type === 'FunctionDeclaration')
        return node.id?.name ?? null;
    if (parent?.type === 'ClassMethod' && key === 'body')
        return keyName(parent.name, false);
    if (parent?.type === 'ClassField' && key === 'init')
        return keyName(parent.name, false);
    if (parent?.type === 'Property' && key === 'value')
        return keyName(parent.key, parent.computed);
    if (parent?.type === 'VariableDeclarator' && key === 'init')
        return keyName(parent.id, false);
    if (parent?.type === 'AssignmentExpression' && key === 'right') {
        return isMember(parent.left) ? keyName(parent.left.property, parent.left.computed)
            : keyName(parent.left, false);
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
    const holds = new Map(), glib = new Set(['GLib']), exported = new Set();

    // First GLib's names, and the names that hold the laters.
    (function scan(node) {
        if (node.type === 'ExportDeclaration' &&
            node.declaration?.type === 'VariableDeclaration') {
            for (const declarator of node.declaration.declarations)
                exported.add(declarator);
        }
        // Newer SpiderMonkey keeps an import's source under moduleRequest, older under source.
        const source = node.moduleRequest?.source ?? node.source;
        if (node.type === 'ImportDeclaration' && source?.value === 'gi://GLib') {
            for (const specifier of node.specifiers)
                glib.add(specifier.name.name);
        }
        if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier' &&
            path(node.init) === 'imports.gi.GLib')
            glib.add(node.id.name);
        const hold = exported.has(node) ? null : holdOf(node);
        if (hold)
            holds.set(hold[1], hold);
        for (const [, child] of children(node))
            scan(child);
    })(ast);
    const heldNames = new Set([...holds.values()].map(([name]) => name));
    const holdTargets = new Set([...holds.values()].map(([, , target]) => target));

    function call(node, parent, key, within) {
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
            node.arguments.map(argument => path(argument)), use, within]);
        return calls.length - 1;
    }

    function role(node, parent, key) {
        if (holdTargets.has(node))
            return 'hold';
        if (parent?.type === 'AssignmentExpression' && key === 'left')
            return 'assigned';
        return addsOrRemoves(parent, key) ? 'laters' : 'other';
    }

    (function walk(node, parent, key, outer) {
        const within = FUNCTIONS.has(node.type) ? functionName(node, parent, key) ?? outer
            : outer;
        if (node.type === 'CallExpression' || node.type === 'OptionalCallExpression') {
            // Marked before the callee is walked, so it knows it is called, and by which call.
            node.callee.called = true;
            node.callee.call = call(node, parent, key, within);
        }
        const line = lineOf(node, parent);
        const here = node.type === 'Identifier' || node.type === 'MemberExpression'
            ? path(node) : null;
        if (here !== null && heldNames.has(here))
            held.push([line, here, role(node, parent, key)]);
        if (node.type === 'CallImport')
            names.push([line, 'import()', 'other', within]);
        const site = node.called === true ? node.call : 'other';
        if (node.type === 'Identifier') {
            let where = site;
            if (parent?.type === 'VariableDeclarator' && key === 'id')
                where = 'declared';
            else if (parent?.type === 'ClassMethod' && key === 'name')
                where = 'key';
            names.push([line, node.name, where, within]);
        }
        if (isMember(node) && !node.computed)
            names.push([line, node.property.name, site, within]);
        // A string that holds a name alone, as obj['name'], a key, or Reflect.get(obj, 'name').
        if (node.type === 'Literal' && typeof node.value === 'string' &&
            /^[A-Za-z_$][\w$]*$/.test(node.value))
            names.push([line, node.value, 'string', within]);
        for (const [childKey, child] of children(node)) {
            // A member's property name is read above, with the member; every key is walked,
            // a computed one as code.
            if (!(isMember(node) && !node.computed && childKey === 'property'))
                walk(child, node, childKey, within);
        }
    })(ast, null, null, null);

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

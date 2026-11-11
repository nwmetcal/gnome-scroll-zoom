// SPDX-License-Identifier: GPL-2.0-or-later
// What gjs's own parser reads in each source, for the bundle's checks in test_bundle.py.
// Reading the syntax tree, not the text, a comment, a string, or a regex can never pass for
// code, and a name the parser can resolve, such as obj['con' + 'nect'], is read as that name.
//
//   gjs -m tests/style/js_nodes.js SOURCES.json
//
// SOURCES.json holds a list of JavaScript sources. This prints a list with one entry for
// each, or the parser's error:
//   calls: every call, as [line, name, receiver, form, kept, args, use]. form is dot for
//     receiver.name(...), bare for name(...), optional or computed for those, and other for
//     a callee that is none of them, such as (0, f)(x). kept is
//     what the call's result is assigned to, if anything. use says how a
//     global.compositor.get_laters() call is used: hold, add, remove, or null.
//   names: every place a name stands, as [line, name, site]: site is the index of the call
//     it names, declared for the name a const, let, or var declares, key for a class
//     method's own name, string for a string that holds a name alone, or other. A dynamic
//     import stands as the name import().
//   holds: the plain names that hold global.compositor.get_laters() in a statement of their
//     own, and that no other module can import. A property of this or of any other object
//     is never one: an object goes where a reading of one file cannot follow it.
//   held: each place a held name stands, as [line, name, role]: role is hold, assigned,
//     laters for the receiver of its own .add( or .remove(, or other.
//   glib: the names GLib goes by in the file.
//   imports: each module the source imports or re-exports, by its specifier, such as
//     gi://Gtk or ./zoomMotion.js, and each path it reaches through gjs's older importer, such
//     as imports.gi.Gtk, as [line, path], however the path is spelled: a member written with a
//     string, a name that holds part of it, or a pattern that takes names out of it.

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
        if (node.type === 'CallImport')
            names.push([line, 'import()', 'other']);
        const site = node.called === true ? node.call : 'other';
        if (node.type === 'Identifier') {
            let where = site;
            if (parent?.type === 'VariableDeclarator' && key === 'id')
                where = 'declared';
            else if (parent?.type === 'ClassMethod' && key === 'name')
                where = 'key';
            names.push([line, node.name, where]);
        }
        if (isMember(node) && !node.computed)
            names.push([line, node.property.name, site]);
        // A string that holds a name alone, as obj['name'], a key, or Reflect.get(obj, 'name').
        if (node.type === 'Literal' && typeof node.value === 'string' &&
            /^[A-Za-z_$][\w$]*$/.test(node.value))
            names.push([line, node.value, 'string']);
        for (const [childKey, child] of children(node)) {
            // A member's property name is read above, with the member; every key is walked,
            // a computed one as code.
            if (!(isMember(node) && !node.computed && childKey === 'property'))
                walk(child, node, childKey);
        }
    })(ast, null, null);

    return {calls, names, holds: [...heldNames], held, glib: [...glib]};
}

function importsOf(ast) {
    const found = [];
    const aliases = new Map();
    const nameOf = (node, computed) => {
        if (node?.type === 'ComputedName')
            return nameOf(node.name, false);
        if (node?.type === 'Identifier' && !computed)
            return node.name;
        return node?.type === 'Literal' && typeof node.value === 'string' ? node.value : null;
    };
    // A path is followed through every name and member that can hold it, since the older
    // importer loads a module wherever a path to it is read.
    function importer(node) {
        if (node?.type === 'OptionalExpression')
            return importer(node.expression);
        if (node?.type === 'Identifier')
            return node.name === 'imports' ? 'imports' : aliases.get(node.name) ?? null;
        if (!node || !isMember(node))
            return null;
        const name = nameOf(node.property, node.computed);
        if (node.object.type === 'Identifier' && node.object.name === 'globalThis' &&
            name === 'imports')
            return 'imports';
        const object = importer(node.object);
        return object === null || name === null ? null : `${object}.${name}`;
    }
    // Each level of a pattern is recorded, so a module taken apart, as const {mainloop: {x}} =
    // imports, is reached as itself and not only as what is taken out of it.
    function bind(target, base, line, record) {
        if (target?.type === 'AssignmentExpression') {
            bind(target.left, base, line, record);
        } else if (target?.type === 'Identifier') {
            aliases.set(target.name, base);
            if (record)
                found.push([line, base]);
        } else if (target?.type === 'ObjectPattern') {
            if (record)
                found.push([line, base]);
            for (const property of target.properties) {
                const key = nameOf(property.key, property.computed);
                if (key !== null)
                    bind(property.value, `${base}.${key}`, line, record);
            }
        }
    }
    function walk(node, record) {
        const line = node.loc?.start.line ?? 0;
        const source = (node.moduleRequest?.source ?? node.source)?.value;
        if (record && ['ImportDeclaration', 'ExportDeclaration'].includes(node.type) &&
            typeof source === 'string')
            found.push([line, source]);
        const loads = node.type === 'CallImport' ? node.arguments?.[0] : null;
        if (record && loads?.type === 'Literal' && typeof loads.value === 'string')
            found.push([line, loads.value]);
        if (node.type === 'VariableDeclarator' && importer(node.init) !== null)
            bind(node.id, importer(node.init), line, record);
        if (node.type === 'AssignmentExpression' && importer(node.right) !== null)
            bind(node.left, importer(node.right), line, record);
        if (record && isMember(node) && importer(node) !== null)
            found.push([line, importer(node)]);
        for (const [, child] of children(node))
            walk(child, record);
    }
    // Names first, again until none changes, so a chain of names given in any order is known,
    // then the paths. A name given a path built from itself, as a = a.gi, grows each time, so
    // the passes stop at one more than the places a name can be given a path.
    let sites = 0;
    (function count(node) {
        sites += ['VariableDeclarator', 'AssignmentExpression'].includes(node.type) ? 1 : 0;
        for (const [, child] of children(node))
            count(child);
    })(ast);
    for (let pass = 0, before = null; pass <= sites; pass++) {
        walk(ast, false);
        const now = JSON.stringify([...aliases]);
        if (now === before)
            break;
        before = now;
    }
    walk(ast, true);
    return found;
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
    return {...read(ast), imports: importsOf(ast)};
})));

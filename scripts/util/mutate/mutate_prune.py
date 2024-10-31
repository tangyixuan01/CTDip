#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))
from util.config import *
from util.mutate.mutate_common import *
from util.mutate.mutate_config import *

test_func_code = ''

# ⬇ ******************* prune type name ******************* ⬇ #
class TypenamePruneVisitor(NodeVisitor):
    def visit_Typename(self, node):
        node.type = None


class FuncLocation4PruneVisitor(NodeVisitor):
    def visit_FuncDef(self, node):
        if node.decl.name == 'test':
            TypenamePruneVisitor().visit(node)
            code = code_generator.visit(node)
            code = code.replace('()', '')
            global test_func_code
            test_func_code = code


def prune_type_name(ast):
    FuncLocation4PruneVisitor().visit(ast)

    global program_file_path
    func_test_path = program_file_path[1]
    lines = []
    with open(func_test_path, 'r') as f:
        lines = f.readlines()
        lines = lines[:9]
        global test_func_code
        lines.append(test_func_code)
    with open(func_test_path, 'w') as f:
        f.writelines(lines)
# ⬆ ******************* prune type name ******************* ⬆ #


def prune(ast):
    prune_type_name(ast)
    return 'prune-type-name'


def prune_code_snippet_node_old_version(global_decl, ast, node_type):
    func_def_nodes = get_func_def_nodes(ast)
    ast_type = NODE_TYPE_2_AST_TYPE[node_type]
    
    target_nodes = get_specify_nodes_from_func(func_def_nodes, ast_type)

    if len(target_nodes) == 0:
        return None
    node = random.choice(target_nodes)
    if node_type == 'if':
        node.cond = c_ast.Constant(type='int', value='0')
        node.iftrue = c_ast.Compound(block_items=[c_ast.EmptyStatement()])
        node.iffalse = None
    elif node_type == 'while':
        node.cond = c_ast.Constant(type='int', value='0')
        node.stmt = c_ast.Compound(block_items=[c_ast.EmptyStatement()])
    elif node_type == 'for':
        node.init = None
        node.cond = c_ast.Constant(type='int', value='0')
        node.next = None
        node.stmt = c_ast.Compound(block_items=[c_ast.EmptyStatement()])
    elif node_type == 'assignment':
        node.op = ''
        node.lvalue = None
        node.rvalue = None
    elif node_type == 'compound':
        node.block_items = [c_ast.EmptyStatement()]
    elif node_type == 'return':
        node.expr = None
    return True


def prune_code_snippet_node(global_decl, ast, node_type):
    func_def_nodes = get_func_def_nodes(ast)
    ast_type = NODE_TYPE_2_AST_TYPE[node_type]
    compound_nodes = get_specify_nodes_from_func(func_def_nodes, c_ast.Compound)

    if len(compound_nodes) == 0:
        return False
    
    if node_type == 'return' or node_type == 'assignment':
        target_nodes_pos = get_specify_nodes_pos_from_compound_nodes(compound_nodes, ast_type)
        if len(target_nodes_pos) == 0:
            return False
        node_pos = random.choice(target_nodes_pos)
        # target_node = node_pos[0].block_items[node_pos[1]]
        # print(code_generator.visit(target_node))
        # node_pos[0] -> compound_node, node_pos[1] -> idx
        del(node_pos[0].block_items[node_pos[1]])
    else:
        if node_type == 'compound':
            target_node = random.choice(compound_nodes)
        else:
            target_nodes_pos = get_specify_nodes_pos_from_compound_nodes(compound_nodes, ast_type)
            if len(target_nodes_pos) == 0:
                return False
            node_pos = random.choice(target_nodes_pos)
            # node_pos[0] -> compound_node, node_pos[1] -> idx
            target_node = node_pos[0].block_items[node_pos[1]]

        label_nodes = []
        get_specify_nodes_by_recursion(target_node, c_ast.Goto, label_nodes)
        get_specify_nodes_by_recursion(target_node, c_ast.Label, label_nodes)
        label_names = set([node.name for node in label_nodes])
        if len(label_nodes) > 0:
            label2node_pos = get_label2node_pos_from_compound_nodes(compound_nodes)
            for label_name in label_names:
                # print('label_name:', label_name)
                # print('label_names:', label2node_pos.keys())
                node_positions = label2node_pos[label_name]
                for pos in node_positions:
                    # pos[0] -> compound_node, pos[1] -> idx
                    label_node = pos[0].block_items[pos[1]]
                    if isinstance(label_node, c_ast.Label):
                        # Label.stmt 替换 Label
                        pos[0].block_items[pos[1]] = label_node.stmt
                    else:
                        # EmptyStatement 替换 Goto
                        pos[0].block_items[pos[1]] = c_ast.EmptyStatement()
        
        if node_type == 'compound':
            # print(code_generator.visit(target_node))
            target_node.block_items = []
        else:
            # print(code_generator.visit(target_node))
  
            # node_pos[0] -> compound_node, node_pos[1] -> idx
            del(node_pos[0].block_items[node_pos[1]])
    return True


def prune_sth(global_decl, ast):
    # choice = ['if', 'while', 'for', 'assignment', 'compound', 'return']
    choice = ['if', 'for', 'assignment', 'compound', 'return']
    snippet_type = random.choice(choice)
    # print('type>>>> ', snippet_type)
    res = prune_code_snippet_node(global_decl, ast, snippet_type)
    if not res:
        return None
    return 'prune-{}-snippet'.format(snippet_type)

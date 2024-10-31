
#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import re
import sys
import copy
import random
import datetime
from pycparser import parse_file, c_generator, c_ast
from pycparser.c_ast import NodeVisitor

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from util.config import *

# variable → type
all_variable2type = {}
# variable → type
local_variable2type = {}
# variable → type
global_variable2type = {}

tmp_all_variable = set()
tmp_decl_variable = set()
tmp_undecl_variable = set()

new_snippets = set()

program_file_path = ''
code_snippets_dir = '/home/workplace/dataset/code_snippets/code_snippets_wrong_code/llvm-wrong-code'

code_generator = c_generator.CGenerator()


class DeclVisitor(NodeVisitor):
    def __init__(self, target='global'):
        self.target = target

    def visit_Decl(self, node):
        variable = node.name
        type_decl = code_generator.visit(node.type)
        
        node_class_name = node.type.__class__.__name__
        if node_class_name == 'FuncDecl':
            type_decl = code_generator.visit(node.type.type)
            type_decl = 'func ' + type_decl
        
        if self.target == 'global':
            all_variable2type[variable] = type_decl
        elif self.target == 'local':
            local_variable2type[variable] = type_decl
        else:
            tmp_decl_variable.add(variable)


class FuncDef4LocalVariablesVisitor(NodeVisitor):
    def visit_FuncDef(self, node):
        DeclVisitor(target='local').visit(node)


def extract_all_variables(node):
    if isinstance(node, c_ast.ID):
        tmp_all_variable.add(node.name)
    else:
        for child in node:
            extract_all_variables(child)



def del_undecl_variables_and_constants_from_node(node):
    global tmp_undecl_variable
    # print(type(node))
    if isinstance(node, c_ast.Constant):
        node.value = ''
    if isinstance(node, c_ast.ID):
        if node.name in tmp_undecl_variable and node.name in all_variable2type.keys():
            node.name = ''
    else:
        for child in node:
            del_undecl_variables_and_constants_from_node(child)


def extract_ingredient(node, target):
    global tmp_undecl_variable, program_file_path, new_snippets
    
    stmt = code_generator.visit(node)
    # Extract undeclared variables
    tmp_undecl_variable = tmp_all_variable - tmp_decl_variable

    if len(tmp_undecl_variable) <= 15 and program_file_path == node.coord.file:
        tmp_node = copy.deepcopy(node)
        # * 1. Delete nodes in node that have not declared variables and constants
        del_undecl_variables_and_constants_from_node(node)
        stmt_copy = code_generator.visit(node)
        # print(stmt_copy)

        # * 2. Add the formatted stmt to new_snippets
        new_snippets_len = len(new_snippets)
        new_snippets.add(stmt_copy)

        # * 3. If the length of new_stniplets increases, it means that new snippets have been found
        if len(new_snippets) > new_snippets_len:
            # todo convert the for loop into a while loop
            # if target == 'while':
            #     stmt = transform_for2while(tmp_node)

            snippet = '//'
            for variable in tmp_undecl_variable:
                if variable in all_variable2type.keys():
                    snippet += variable + ':' + all_variable2type[variable] + ';'
            if snippet[-1] != ';':
                snippet += ';'
            snippet = snippet[:-1] + '\n' + stmt
            print(snippet)
            if not os.path.exists(os.path.join(code_snippets_dir, target)):
                os.makedirs(os.path.join(code_snippets_dir, target))
            with open(os.path.join(code_snippets_dir, target, str(len(new_snippets)) + '.c'), 'a+') as f:
                f.write(snippet)
            print("=========================================")
        if len(new_snippets) >= 10000:
            exit(0)
   
    tmp_all_variable.clear()
    tmp_decl_variable.clear()
    tmp_undecl_variable.clear()


# Convert the for loop to a while loop
def transform_for2while(node):
    init_stmt = code_generator.visit(node.init)
    cond_stmt = code_generator.visit(node.cond)
    next_stmt = code_generator.visit(node.next)
    stmt = code_generator.visit(node.stmt)
    snippet = ''
    snippet += init_stmt + ';\n'
    snippet += 'while(' + cond_stmt + ')\n{\n'
    stmt = re.sub(r'\n', '\n    ', stmt)
    snippet += '    ' + stmt + '\n'
    snippet += '    ' + next_stmt + ';\n'
    snippet += '}\n'
    # print(snippet)
    return snippet


def visit(node, target):
    extract_all_variables(node)
    DeclVisitor(target).visit(node)      
    extract_ingredient(node, target)


class ForVisitor(NodeVisitor):
    def visit_For(self, node):
        visit(node, 'for')


class IfVisitor(NodeVisitor):
    def visit_If(self, node):
        visit(node, 'if')


class SwitchVisitor(NodeVisitor):
    def visit_Switch(self, node):
        visit(node, 'switch')


class AssignmentVisitor(NodeVisitor):
    def visit_Assignment(self, node):
        visit(node, 'assignment')


class FuncDefVisitor(NodeVisitor):
    def visit_FuncDef(self, node):
        visit(node, 'func_def')


class WhileVisitor(NodeVisitor):
    def visit_While(self, node):
        visit(node, 'while')


def print_variables():
    print('all_variable2type:')
    for key, value in all_variable2type.items():
        print(key, value)
    print()

    print('local_variable2type:')
    for key, value in local_variable2type.items():
        print(key, value)
    print()

    print('global_variable2type:')
    for key, value in global_variable2type.items():
        print(key, value)


def main():
    """
    @description: When running the code, two parameters need to be entered,
                  the first parameter is the folder of the program to be processed，
                  the second parameter is the selected structured feature
    @return {*}
    """
    start = datetime.datetime.now()
    global all_variable2type, local_variable2type, global_variable2type, \
        program_file_path, new_snippets

    programs_dir = sys.argv[1]
    for program_file_name in os.listdir(programs_dir):
        print('*********************', program_file_name, '*********************')
        program_file_path = os.path.join(programs_dir, program_file_name)

        try:
            ast = parse_file(program_file_path, use_cpp=True, 
                            cpp_path=PARSER_FILE_CPP_PATH, 
                            cpp_args=['-E',
                                      r'-I' + CSMITH_INCLUDE_DIR,
                                      r'-I' + PYCPARSER_INCLUDE_DIR,])
        except Exception as e:
            print(e)
            continue
        
        all_variable2type.clear()
        local_variable2type.clear()
        global_variable2type.clear()

        DeclVisitor().visit(ast.ext)
        FuncDef4LocalVariablesVisitor().visit(ast.ext)
        for variable in all_variable2type.keys():
            if variable not in local_variable2type.keys():
                global_variable2type[variable] = all_variable2type[variable]

        select = sys.argv[2]

        if select == 'while':
            WhileVisitor().visit(ast.ext)
        elif select == 'for':
            ForVisitor().visit(ast.ext)
        elif select == 'if':
            IfVisitor().visit(ast.ext)
        elif select == 'switch':
            SwitchVisitor().visit(ast.ext)
        elif select == 'assignment':
            AssignmentVisitor().visit(ast.ext)
        elif select == 'func_def':
            FuncDefVisitor().visit(ast.ext)
        print('length of new_snippets:', len(new_snippets))

    end = datetime.datetime.now()
    print('time:', end - start)


if __name__ == "__main__":
    main()

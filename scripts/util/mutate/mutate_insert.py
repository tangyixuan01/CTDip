#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))
from util.config import *
from util.mutate.mutate_config import *
from util.mutate.mutate_common import *
from util.sys_util import *

# ⬇⬇ ******************** insert snippet stmts ******************** ⬇⬇ #
# ⬇ ******************* extract all insert positions ******************* ⬇ #
class Assignment4InsertPositionsVisitor(NodeVisitor):
    def __init__(self, insert_positions):
        self.insert_positions = insert_positions

    def visit_Assignment(self, node):
        self.insert_positions.add(node.coord.line - 1)


class FuncDef4InsertPositionsVisitor(NodeVisitor):
    def __init__(self, insert_positions):
        self.insert_positions = insert_positions

    def visit_FuncDef(self, node):
        if node.decl.name == 'test':
            Assignment4InsertPositionsVisitor(self.insert_positions).visit(node)


# Extract all suitable insertion positions
def extract_all_insert_positions(ast):
    insert_positions = set()
    FuncDef4InsertPositionsVisitor(insert_positions).visit(ast)
    return insert_positions
# ⬆ ******************* extract all insert positions ******************* ⬆ #


# ⬇ ******************* select code snippet ******************* ⬇ #
# only choose from for and if
def select_code_snippet(code_snippets_dir, snippet_type='for'):
    snippet_type_dir = os.path.join(code_snippets_dir, snippet_type)
    # random choice snippet file
    snippet_file_name = random.choice(os.listdir(snippet_type_dir))
    snippet_file_path = os.path.join(snippet_type_dir, snippet_file_name)

    # done: file in blacklist has been removed
    # with open(BLACKLIST_FILE_PATH, 'r') as f:
    #     blacklist = [line.strip() for line in f.readlines()]
    # while True:
    #     snippet_type_dir = os.path.join(code_snippets_dir, snippet_type)
    #     # random choice snippet file
    #     snippet_file_name = random.choice(os.listdir(snippet_type_dir))
    #     snippet_file_path = os.path.join(snippet_type_dir, snippet_file_name)
    #     if '/'.join(snippet_file_path.split('/')[-3:]) not in blacklist:
    #         break  
    # print('snippet_file_name:', snippet_file_name)
    # print('snippet_file_path:', snippet_file_path)

    snippet_variable2type = {}
    sinppet_str = ""
    if os.path.isfile(snippet_file_path):
        with open(snippet_file_path, 'r') as f:
            lines = f.readlines()
            if lines is not None and len(lines) < 2:
                return None, None
            else:
                sinppet_str = ''.join(lines[1:])
                first_line = lines[0].strip()
                if first_line.startswith('//'):
                    first_line = first_line[2:]
                    if first_line.strip() != '':
                        for variable_type in first_line.split(';'):
                            variable, type_decl = variable_type.split(':')
                            snippet_variable2type[variable] = type_decl
    return sinppet_str, snippet_variable2type, snippet_file_path
# ⬆ ******************* select code snippet ******************* ⬆ #


# ⬇ ******************* adapt code snippet ******************* ⬇ #
# convert variable2type to type2variable
def variable2type_2_type2variable(variable2type):
    type2variable = {}
    for variable, type_decl in variable2type.items():
        if type_decl not in type2variable.keys():
            type2variable[type_decl] = []
        type2variable[type_decl].append(variable)
    return type2variable


# String segmentation
def split_text4variables(text):
    pattern = r'\b\w+\b|[ \n\S]'
    matches = re.findall(pattern, text)
    return matches


# Rename variables in code blocks
def rename_variable4snippet(snippet_str, rename_variable):
    matches = split_text4variables(snippet_str)
    for i in range(len(matches)):
        if matches[i] in rename_variable.keys():
            matches[i] = rename_variable[matches[i]]
    return ''.join(matches)


# Reuse variables
def reuse_variable(snippet_str, snippet_variable2type, available_type2variable):
    rename_variable = {}
    no_reusable_variable = {}

    # extract rename_variable and no_reusable_variable
    for snippet_variable, snippet_type in snippet_variable2type.items():
        if snippet_type in available_type2variable.keys():
            random_variable = random.choice(available_type2variable[snippet_type])
            rename_variable[snippet_variable] = random_variable
        else:
            no_reusable_variable[snippet_variable] = snippet_type

    # rename snippet variable
    snippet_str = rename_variable4snippet(snippet_str, rename_variable)
    return snippet_str, no_reusable_variable


# Initialize arrays by directly assigning values when defining variables
def generate_array_initialization_by_assignment(dimensions, declaration=''):
    if len(dimensions) == 0:
        return ""
    initialization = ""
    for i in range(dimensions[0]):
        if len(dimensions) > 1:
            initialization += generate_array_initialization_by_assignment(dimensions[1:], declaration)
        else:
            value = random.randint(1, 10)
            initialization += str(value)

        if i < dimensions[0] - 1:
            initialization += ","
    declaration += "{" + initialization + "}"
    return declaration


# Initialize an array through a for loop method
def generate_array_initialization_by_for(variable_name, dimensions, rnd_value):
    initialization = ''
    for i in range(len(dimensions)):
        dim = dimensions[i]
        initialization += '{}for (size_t ii_{} = 0; ii_{} < {}; ++ii_{})\n'.format(' ' * (i * 4), i, i, dim, i)
    initialization += (' ' * ((len(dimensions) - 1) * 4)) + '{\n'
    initialization += '{}{}'.format(' ' * (len(dimensions) * 4), variable_name)
    for i in range(len(dimensions)):
        initialization += '[ii_{}]'.format(i)
    initialization += ' = {};\n'.format(rnd_value)
    initialization += (' ' * ((len(dimensions) - 1) * 4)) + '}\n'
    return initialization 


# Calculate the hash value of an array through a for loop method
def generate_array_hash_by_for(variable_name, dimensions):
    hash_snippet = ''
    for i in range(len(dimensions)):
        dim = dimensions[i]
        hash_snippet += '{}for (size_t ii_{} = 0; ii_{} < {}; ++ii_{})\n'.format(' ' * (i * 4), i, i, dim, i)
    hash_snippet += (' ' * ((len(dimensions) - 1) * 4)) + '{\n'
    # seed ^= v + 0x9e3779b9 + ((seed)<<6) + ((seed)>>2);
    for i in range(len(dimensions)):
        variable_name += '[ii_{}]'.format(i)
    hash_snippet += '{}seed ^= {} + 0x9e3779b9 + ((seed)<<6) + ((seed)>>2);\n'.format(' ' * (len(dimensions) * 4), variable_name)
    hash_snippet += (' ' * ((len(dimensions) - 1) * 4)) + '}\n'
    return hash_snippet


def self_define_variable(snippet_str, variable2type):
    define_snippet = ''
    hash_snippet = ''
    rename_variable = {}
    for variable, type_decl in variable2type.items():
        bracket_idx = type_decl.find('[')
        new_variable = generate_random_variable_name()
        rename_variable[variable] = new_variable

        rnd_value = generate_random_value(type_decl)

        if bracket_idx != -1:
            # arr[10][12][13] :Extract the numbers in parentheses and store them in a list
            dimensions = [size for size in re.findall(r'\[(.*?)\]', type_decl)]
            for dimension in dimensions:
                dimension = dimension.strip()
                if dimension == '' or re.search(r'[a-zA-Z]', dimension):
                    dimensions[dimensions.index(dimension)] = 100
                else:
                    dimensions[dimensions.index(dimension)] = int(eval(dimension))

            declare_array = type_decl[:bracket_idx] + ' ' + new_variable + type_decl[bracket_idx:] + ';\n'

            array_init = generate_array_initialization_by_for(new_variable, dimensions, rnd_value)
            define_snippet += declare_array + array_init

            array_hash = generate_array_hash_by_for(new_variable, dimensions)
            hash_snippet += array_hash
        else:
            define_snippet += '{} {} = {};\n'.format(type_decl, new_variable, str(rnd_value))
            hash_snippet += 'seed ^= {} + 0x9e3779b9 + ((seed)<<6) + ((seed)>>2);\n'.format(new_variable)
    # print('define_snippet:', define_snippet)
    
    # reanme snippet variable
    snippet_str = rename_variable4snippet(snippet_str, rename_variable)
    # snippet_str = define_snippet + snippet_str + hash_snippet
    return define_snippet, snippet_str, hash_snippet


# Adaptation code block
def  adapt_code_snippet(snippet_str, snippet_variable2type, available_variable2type):
    available_type2variable = variable2type_2_type2variable(available_variable2type)
    snippet_str, no_reusable_variable = reuse_variable(snippet_str, snippet_variable2type, available_type2variable)
    define_snippet, snippet_str, hash_snippet = self_define_variable(snippet_str, no_reusable_variable)

    # print('snippet_str:', snippet_str)
    return define_snippet, snippet_str, hash_snippet


def insert_code_snippet(ast, snippet_type):
    # 1. extract all insert positions from ast
    insert_positions = extract_all_insert_positions(ast)

    program = ''
    global program_file_path
    func_file_path = program_file_path[1]
    with open(func_file_path, 'r') as f:
        program = f.readlines()

    # 2. random choice insert position
    pos = random.choice(list(insert_positions))

    # 3. select code snippet
    snippet, snippet_vairable2type, snippet_file_path = select_code_snippet(CODE_SNIPPETS_DIR, snippet_type)
    # print('snippet:', snippet)
    # print('snippet_vairable2type:', snippet_vairable2type)
    # print('snippet_file_path:', snippet_file_path)

    # 4. adapt code snippet
    define_snippet, snippet_str, hash_snippet = adapt_code_snippet(snippet, snippet_vairable2type, global_variable2type)
    program.insert(len(program) - 1, hash_snippet)
    program.insert(pos, snippet_str)
    program.insert(10, define_snippet)

    with open(func_file_path, 'w') as f:
        f.writelines(program)
# ⬆ ******************* adapt code snippet ******************* ⬆ #


def insert(ast):
    choice = ['for', 'if', 'while', 'assignment']
    snippet_type = random.choice(choice)
    insert_code_snippet(ast, snippet_type)
    return 'insert-{}-snippet'.format(snippet_type)
# ⬆⬆ ******************** insert snippet stmts ******************** ⬆⬆ #

# ⬇⬇ ******************** insert snippet nodes ******************** ⬇⬇ #
def transfer_snippet2ast(snippet):
    """
    @description: Convert code snippets to AST
    @param {*} snippet 
    @return {*} ast
    """
    parse_code = '#include <stdio.h>\n' + 'int main()\n{\n'
    parse_code += snippet + '\n}'
    program_file_path = 'tmp.c'
    with open(program_file_path, 'w') as f:
        f.write(parse_code)
    parse_ast = parse_c_program_file(program_file_path)
    os.remove(program_file_path)

    return parse_ast.ext[-1].body.block_items[0]


def construct_init_stmts_4_snippet(global_decl, snippet_vairable2type):
    """
    @description: Build initialization statements for code snippets
    @param {*} global_decl
    @param {*} snippet_vairable2type
    @return {*} Initialization statement list
    """
    stmts = []
    ori_vari2new_vari = {}      
    new_vari2type_decl = {}    
    used_variables = set()
    for ori_snippet_vari, type_decl in snippet_vairable2type.items():
        new_vari_name, init_stmts = construct_variable_init_stmt_node(global_decl, type_decl, used_variables)
        used_variables.add(new_vari_name)
        stmts += init_stmts
        ori_vari2new_vari[ori_snippet_vari] = new_vari_name
        if type_decl.find('*') == -1:
            new_vari2type_decl[new_vari_name] = type_decl
    return stmts, ori_vari2new_vari, new_vari2type_decl


def rename_variable_4_snippet_ast(snippet_ast, ori_vari2new_vari):
    """
    @description: Rename variables in code snippets
    @param {*} snippet_ast
    @param {*} ori_vari2new_vari
    @return {*}
    """
    for node in snippet_ast:
        ori_name = node.name if hasattr(node, 'name') else None
        if ori_name is not None and ori_name in ori_vari2new_vari.keys():
            node.name = ori_vari2new_vari[ori_name]
        rename_variable_4_snippet_ast(node, ori_vari2new_vari)


def select_and_adapt_code_snippet(global_decl, snippet_type):
    """
    @description: 
    @param {*} global_decl 
    @param {*} snippet_type 
    @return {*} Initialization statement node list, code snippet's AST and hash statement node list
    """
    # 1. select code snippet
    snippet, snippet_variable2type, snippet_file_path = select_code_snippet(CODE_SNIPPETS_DIR, snippet_type)
    # 2. Build initialization statements for code snippet
    init_stmts, ori_vari2new_vari, new_vari2type_decl = construct_init_stmts_4_snippet(global_decl, snippet_variable2type)
    # 3. Convert code snippet to AST
    snippet_ast = transfer_snippet2ast(snippet)
    # 4. Change the variable name in the code snippet to a new variable name
    rename_variable_4_snippet_ast(snippet_ast, ori_vari2new_vari)
    # 5. Build hash statements for new variables
    hash_stmts = []
    for new_vari, type_decl in new_vari2type_decl.items():
        hash_stmts.append(construct_call_transparent_crc(new_vari))

    return init_stmts, snippet_ast, hash_stmts

    print(snippet_type, '================')
    print(snippet_file_path)
    print('v2t*************************')
    print(snippet_vairable2type)
    print('ori*************************')
    print(snippet)
    print('ok**************************')
    for stmt in init_stmts:
        print(code_generator.visit(stmt) + ';')
    print(code_generator.visit(snippet_ast))
    for stmt in hash_stmts:
        print(code_generator.visit(stmt) + ';')
    print('===============================')
    

def insert_code_snippet_node(global_decl, ast, snippet_type):
    # 1. Insertion point position selection: func -> compound -> idx
    ## select func
    func_def_nodes = get_func_def_nodes(ast)
    if isinstance(func_def_nodes, list) and len(func_def_nodes) > 0:
        select_func_def_node = random.choice(func_def_nodes)
    else:
        return False
    ## select compound
    compound_nodes = get_specify_nodes_from_func([select_func_def_node], c_ast.Compound)
    select_compound_node = random.choice(compound_nodes)
    ## select idx
    len_of_compound_block_items = len(select_compound_node.block_items) \
        if isinstance(select_compound_node.block_items, list) else 0 # done: fix the bug of "TypeError: object of type 'NoneType' has no len()"
    select_idx = random.randint(0, len_of_compound_block_items)

    # print('==============')
    # print('select_func_def_node:', select_func_def_node.decl.name)
    # print('select_compound_node:', code_generator.visit(select_compound_node))
    # print('select_idx:', select_idx)
    # print('==============')

    if snippet_type == 'return':
        # 2. Get the return value type and construct an initialization statement
        return_type_decl = code_generator.visit(select_func_def_node.decl.type.type)
        return_vari_name, init_stmts = construct_variable_init_stmt_node(global_decl, return_type_decl)
        # 3. Perform insertion, insertion order：return -> init
        ## return
        if isinstance(select_compound_node.block_items, list):
            select_compound_node.block_items.insert(select_idx, c_ast.Return(c_ast.ID(return_vari_name)))
        ## init
        for init_stmt in init_stmts:
            if isinstance(select_compound_node.block_items, list):
                select_compound_node.block_items.insert(select_idx, init_stmt)
    else:
        # 2. Initialization statement node list, code snippet's AST and hash statement node list
        init_stmts, snippet_ast, hash_stmts = select_and_adapt_code_snippet(global_decl, snippet_type)
        # 3. Perform insertion, insertion order：hash -> snippet -> init
        func_body = select_func_def_node.body.block_items
        if not isinstance(func_body, list):
            return False
        ## hash
        for hash_stmt in hash_stmts:
            func_body.insert(len(func_body) - 1, hash_stmt)
        ## snippet
        if isinstance(select_compound_node.block_items, list):
            select_compound_node.block_items.insert(select_idx, snippet_ast)
        ## init
        for init_stmt in init_stmts:
            func_body.insert(0, init_stmt)
    return True
# ⬆⬆ ******************** insert snippet nodes ******************** ⬆⬆ #


def insert_sth(global_decl, ast):
    choice = ['for', 'if', 'while', 'assignment', 'doWhile', 'switch', 'return']
    snippet_type = random.choice(choice)
    insert_code_snippet_node(global_decl, ast, snippet_type)
    return 'insert-{}-snippet'.format(snippet_type)


def get_blacklist():
    err_cnt = 0
    global_decl = GlobalDecl({}, {}, {}, {}, {})
    choice = ['for', 'if', 'while', 'assignment', 'doWhile', 'switch']
    for snippet_type in choice:
        cnt = 0
        snippet_type_dir = os.path.join(CODE_SNIPPETS_DIR, snippet_type)
        # random choice snippet file
        snippet_file_paths = os.listdir(snippet_type_dir)
        for file_name in snippet_file_paths:
            snippet_file_path = os.path.join(snippet_type_dir, file_name)
            snippet_variable2type = {}
            sinppet_str = ""
            if os.path.isfile(snippet_file_path):
                with open(snippet_file_path, 'r') as f:
                    lines = f.readlines()
                    if lines is not None and len(lines) < 2:
                        return None, None
                    else:
                        sinppet_str = ''.join(lines[1:])
                        first_line = lines[0].strip()
                        if first_line.startswith('//'):
                            first_line = first_line[2:]
                            if first_line.strip() != '':
                                for variable_type in first_line.split(';'):
                                    variable, type_decl = variable_type.split(':')
                                    snippet_variable2type[variable] = type_decl
                init_stmts, ori_vari2new_vari, new_vari2type_decl = construct_init_stmts_4_snippet(global_decl, snippet_variable2type)
                snippet_ast = transfer_snippet2ast(sinppet_str)
                rename_variable_4_snippet_ast(snippet_ast, ori_vari2new_vari)
                
                new_com = ['']
                for init_stmt in init_stmts:
                    new_com.insert(0, init_stmt)
                new_com = new_com[:-1]
                new_com.append(snippet_ast)
                main_node = c_ast.FuncDef(decl=c_ast.Decl(name='main', quals=[], align=[], storage=[], funcspec=[],
                                type=c_ast.FuncDecl(args=None,
                                             type=c_ast.TypeDecl(declname='main', quals=[],
                                             align=None,
                                             type=c_ast.IdentifierType(names=['int']))
                                             ),
                                init=None,bitsize=None),
                                param_decls=None,
                                body=c_ast.Compound(block_items=new_com))
                main_code = '#include "csmith.h"\n' + code_generator.visit(main_node)
                cnt += 1
                print(snippet_type, '-', cnt, '==============')

                with open('tmp.c', 'w') as f:
                    f.write(main_code)
                
                check_timeout = 60              # 60s
                compiler_mem_limit = 10000000   # 10Gb
                compile_program_cmd = ['clang-18', 'tmp.c', '-I/home/jwzeng/tools/csmith/include', '-w']
                ret_code, output, err_output, is_time_expired, elapsed_time = \
                    run_command(compile_program_cmd, check_timeout, -1, compiler_mem_limit)
                if ret_code != 0:
                    with open('append_hash.log', 'a+') as f:
                        f.write('snippet_file_path: ' + snippet_file_path + '\n')
                        f.write('ret_code: ' + str(ret_code) + '\n')
                        f.write('output: ' + output.decode() + '\n')
                        f.write('err_output: ' + err_output.decode() + '\n')
                        f.write('is_time_expired: ' + str(is_time_expired) + '\n')
                        f.write('elapsed_time: ' + str(elapsed_time) + '\n')
                        f.write(str(err_cnt + 1) + '=====================\n')
                        err_cnt += 1
                        print('now error:', err_cnt)
                    with open('newblacklist.txt', 'a+') as f:
                        f.write('/'.join(snippet_file_path.split('/')[-3:]) + '\n')


if __name__ == '__main__':
    # snippet, snippet_vairable2type, snippet_file_path = select_code_snippet(CODE_SNIPPETS_DIR, 'doWhile')
    # define_snippet, snippet_str, hash_snippet = adapt_code_snippet(snippet, snippet_vairable2type, {})
    # tmp_snippet = "#include <stdint.h>\n"+ "int main{\n" + "int seed = 0;\n"
    # tmp_snippet += define_snippet + snippet_str + hash_snippet
    # tmp_snippet += "}\n"
    # print(tmp_snippet)

    # insert_code_snippet_node(None, None, 'return')
    # cnt = 0
    # for i in range(40000):
    #     choice = ['for', 'if', 'while', 'assignment', 'doWhile', 'switch']
    #     snippet_type = random.choice(choice)
    #     is_in_blacklist = select_code_snippet(CODE_SNIPPETS_DIR, snippet_type)
    #     if is_in_blacklist:
    #         cnt += 1
    # print('total:', cnt)

    get_blacklist()

    exit()
    selects = ['assignment', 'doWhile', 'for', 'if', 'while', 'switch']
    for select in selects:
        for i in range(100):
            insert_code_snippet_node(None, None, select)
            exit()

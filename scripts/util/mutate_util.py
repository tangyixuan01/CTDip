#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from util.config import *
from util.check_program import *
from util.mutator_scheduler import *
from util.mutate.mutate_config import *
from util.mutate.mutate_common import *
from util.mutate.mutate_insert import *
from util.mutate.mutate_prune import *
from util.mutate.mutate_replace import *


# ⬇ ******************* print variables ******************* ⬇ #
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
# ⬆ ******************* print variables ******************* ⬆ #


# ⬇ ******************* extract (all, global, local) variables ******************* ⬇ #
class DeclVisitor(NodeVisitor):
    def __init__(self, target='all'):
        self.target = target

    def visit_Decl(self, node):
        variable = node.name
        type_decl = code_generator.visit(node.type)
        node_class_name = node.type.__class__.__name__
        if node_class_name == 'FuncDecl':
            type_decl = code_generator.visit(node.type.type)
            type_decl = 'func ' + type_decl
        
        if self.target == 'all':
            all_variable2type[variable] = type_decl
        elif self.target == 'local':
            local_variable2type[variable] = type_decl


class FuncDef4LocalVariablesVisitor(NodeVisitor):
    def visit_FuncDef(self, node):
        DeclVisitor(target='local').visit(node)


def extract_variables(ast):
    global all_variable2type, local_variable2type, global_variable2type
    all_variable2type.clear()
    local_variable2type.clear()
    global_variable2type.clear()

    # extract all variables
    DeclVisitor().visit(ast)
    # extract local variables
    FuncDef4LocalVariablesVisitor().visit(ast)
    # extract global variables
    for variable in all_variable2type.keys():
        if variable not in local_variable2type.keys():
            global_variable2type[variable] = all_variable2type[variable]
# ⬆ ******************* extract (all, global, local) variables ******************* ⬆ #
  

# ⬇ ******************* modify files for adapting pycparser ******************* ⬇ #
def modify_init_file_for_adapting_pycparser(init_file_path):
    snippet = 'extern unsigned long long int seed;\n'
    lines = []
    with open(init_file_path, 'r') as f:
        lines = f.readlines()
        lines.insert(0, snippet)
    with open(init_file_path, 'w') as f:
        f.writelines(lines)


def modify_func_file_for_adapting_pycparser(func_file_path):
    snippet = '''\
#include <stdio.h>
#include <stdint.h>
#define max(a, b) ((a) > (b) ? (a) : (b))
#define min(a, b) ((a) < (b) ? (a) : (b))	
'''
    lines = []
    with open(func_file_path, 'r') as f:
        lines = f.readlines()
        
        for i in range(len(lines)):
            if lines[i].startswith('#include "init.h"'):
                del(lines[i + 1 : i + 9])
                break
        lines.insert(i + 1, snippet)
    with open(func_file_path, 'w') as f:
        f.writelines(lines)


def modify_driver_file_for_adapting_tcc_compiler(driver_file_path):
    snippet = ' ' * 4 + 'return 0;\n'
    lines = []
    with open(driver_file_path, 'r') as f:
        lines = f.readlines()
        lines.insert(len(lines) - 1, snippet)
    with open(driver_file_path, 'w') as f:
        f.writelines(lines)
# ⬆ ******************* modify files for adapting pycparser ******************* ⬆ #


def append_hash_4_local_variable(global_decl, root):
    if not isinstance(root, c_ast.Compound):
        return
    nodes = root.block_items
    if not isinstance(nodes, list):
        return

    hash_nodes = []
    for node in nodes:
        new_node = None
        if isinstance(node, c_ast.Decl):
            if node.init is None:
                continue

            vari_name = node.name
            type_decl = code_generator.visit(node.type)
            if type_decl.find('*') != -1:
                continue

            is_array = False if type_decl.find('[') == -1 else True
            simple_type = transform_type_decl(type_decl)
            if is_array:
                dimensions = extract_dimensions_of_type_decl(type_decl)

                last_node = None
                dimensions_str = ''
                for i in range(len(dimensions)):
                    # hash_i, hash_j, hash_k, hash_l, hash_m, hash_n...
                    idx_name = 'hash_' + chr(ord('i') + i)
                    dimensions_str += '[' + idx_name + ']'
                    init_for_stmt_node = construct_init_for_stmt_node(idx_name, dimensions[i])
                    if new_node is None:
                        new_node = init_for_stmt_node
                        last_node = init_for_stmt_node
                    else:
                        last_node.stmt = c_ast.Compound(block_items=[init_for_stmt_node])
                        last_node = init_for_stmt_node

                hash_stmts = []
                last_node.stmt = c_ast.Compound(block_items=hash_stmts)
                ori_name = vari_name + dimensions_str
                if simple_type.find('struct') != -1 or simple_type.find('union') != -1:
                    fields_res = []
                    extract_all_fields(global_decl, ori_name, simple_type, fields_res)
                    for field in fields_res:
                        hash_stmt = construct_call_transparent_crc(field)
                        hash_stmts.append(hash_stmt)
                else:
                    hash_stmt = construct_call_transparent_crc(ori_name)
                    hash_stmts.append(hash_stmt)
                hash_nodes.append(new_node)
            else:

                ori_name = vari_name
                if simple_type.find('struct') != -1 or simple_type.find('union') != -1:
                    fields_res = []
                    extract_all_fields(global_decl, ori_name, simple_type, fields_res)
                    for field in fields_res:
                        hash_stmt = construct_call_transparent_crc(field)
                        hash_nodes.append(hash_stmt)
                else:
                    hash_stmt = construct_call_transparent_crc(ori_name)
                    hash_nodes.append(hash_stmt)
            
    if isinstance(nodes, list) and\
          len(nodes) > 0 and\
          isinstance(nodes[-1], c_ast.Return):
        for hash_node in hash_nodes:
            nodes.insert(-1, hash_node)
    else:
        nodes.extend(hash_nodes)


class FuncDef_Visitor(NodeVisitor):
    def __init__(self, global_decl):
        self.global_decl = global_decl

    def visit_FuncDef(self, node):
        if node.decl.name.startswith('func'):
            append_hash_4_local_variable(self.global_decl, node.body)


class For2Compound_Visitor(NodeVisitor):
    def __init__(self, global_decl):
        self.global_decl = global_decl

    def visit_For(self, node):
        self.generic_visit(node)
        if not isinstance(node.stmt, c_ast.Compound):
            node.stmt = c_ast.Compound([node.stmt])
        append_hash_4_local_variable(self.global_decl, node.stmt)


class While2Compound_Visitor(NodeVisitor):
    def __init__(self, global_decl):
        self.global_decl = global_decl

    def visit_While(self, node):
        self.generic_visit(node)
        if not isinstance(node.stmt, c_ast.Compound):
            node.stmt = c_ast.Compound([node.stmt])
        append_hash_4_local_variable(self.global_decl, node.stmt)


class DoWhile2Compound_Visitor(NodeVisitor):
    def __init__(self, global_decl):
        self.global_decl = global_decl

    def visit_DoWhile(self, node):
        self.generic_visit(node)
        if not isinstance(node.stmt, c_ast.Compound):
            node.stmt = c_ast.Compound([node.stmt])
        append_hash_4_local_variable(self.global_decl, node.stmt)


class If2Compound_Visitor(NodeVisitor):
    def __init__(self, global_decl):
        self.global_decl = global_decl

    def visit_If(self, node):
        self.generic_visit(node)
        if not isinstance(node.iftrue, c_ast.Compound):
            node.iftrue = c_ast.Compound([node.iftrue])
        if node.iffalse is not None and not isinstance(node.iffalse, c_ast.Compound):
            node.iffalse = c_ast.Compound([node.iffalse])
        append_hash_4_local_variable(self.global_decl, node.iftrue)
        if node.iffalse is not None:
            append_hash_4_local_variable(self.global_decl, node.iffalse)


def trans_stmt_to_compound(global_decl, ast):
    FuncDef_Visitor(global_decl).visit(ast)
    For2Compound_Visitor(global_decl).visit(ast)
    While2Compound_Visitor(global_decl).visit(ast)
    DoWhile2Compound_Visitor(global_decl).visit(ast)
    If2Compound_Visitor(global_decl).visit(ast)


def get_global_decl_and_main_node(ast):
    """
    @description: get global decl and main node
    @param {*} ast program ast
    @return {*} main node
    """
    type_decls = {}
    ptr_decls = {}
    array_decls = {}
    func_decls = {}
    union_decls = {}
    struct_decls = {}
    main_node = None
    for node in ast.ext:
        if isinstance(node, c_ast.Decl):
            node_type = node.type
            if isinstance(node_type, c_ast.TypeDecl):
                if node.init == None:
                    continue
                variable = node.name
                type_decl = code_generator.visit(node_type)
                type_decls[variable] = type_decl
            
            elif isinstance(node_type, c_ast.PtrDecl):
                variable = node.name
                type_decl = code_generator.visit(node_type)
                ptr_decls[variable] = type_decl

            elif isinstance(node_type, c_ast.ArrayDecl):
                variable = node.name
                type_decl = code_generator.visit(node_type)
                array_decls[variable] = type_decl

            elif isinstance(node_type, c_ast.FuncDecl):
                func_name = node.name
                func_type = code_generator.visit(node_type.type)
                func_args = []
                if node_type.args is not None:
                    for arg in node_type.args.params:
                        arg_type = code_generator.visit(arg.type)
                        if arg_type != 'void':
                            func_args.append(arg_type)
                func_info = FuncDeclInfo(func_name, func_type, func_args)
                func_decls[func_name] = func_info

            elif isinstance(node_type, c_ast.Union):
                # union
                name = 'union ' + node_type.name
                type_name_bitsize = []
                for decl in node_type.decls:
                    if decl.name is not None:
                        type_name_bitsize.append((code_generator.visit(decl.type),
                                                decl.name,
                                                code_generator.visit(decl.bitsize)))
                union_decls[name] = type_name_bitsize

            elif isinstance(node_type, c_ast.Struct):
                # struct
                name = 'struct ' + node_type.name
                type_name_bitsize = []
                for decl in node_type.decls:
                    if decl.name is not None:
                        type_name_bitsize.append((code_generator.visit(decl.type),
                                                  decl.name, 
                                                  code_generator.visit(decl.bitsize)))
                struct_decls[name] = type_name_bitsize

        elif isinstance(node, c_ast.FuncDef):
            if node.decl.name == 'main':
                main_node = node
    global_decl = GlobalDecl(type_decls, ptr_decls, array_decls, func_decls, struct_decls, union_decls)
    return global_decl, main_node


def call_func_in_main(global_decl, main_node):
    # done: fix the bug of "AttributeError: 'NoneType' object has no attribute 'body'"
    if not isinstance(main_node, c_ast.FuncDef):
        print('main_node is not funcdecl')
        return
    body_block_items = main_node.body.block_items
    for func_name, func_info in global_decl.func_decls.items():
        if not func_name.startswith('func'):
            continue
        func_args = func_info.func_args
        new_args = []
        stmts = []
        # done: fix the ub which can't checked
        used_variables = set()
        for arg in func_args:
            new_vari_name, init_stmts = construct_variable_init_stmt_node(global_decl, arg, used_variables)
            used_variables.add(new_vari_name)
            stmts.extend(init_stmts)
            new_args.append(c_ast.ID(name=new_vari_name))

        body_block_items.insert(0, c_ast.FuncCall(name=c_ast.ID(name=func_name),
                                                  args=c_ast.ExprList(exprs=new_args)))
        for stmt in stmts:
            body_block_items.insert(0, stmt)


def program_preprocessing(test_dir):
    """
    @description: program preprocessing
    @param {*} test_dir
    @return {*}
        ast -> program's ast
        global_decl -> program's global variables
    """
    global program_file_path
    program_file_path.clear()
    program_file_path.append(os.path.join(test_dir, 'test.c'))
    test_program = program_file_path[0]

    ast = parse_c_program_file(test_program)

    global_decl, main_node = get_global_decl_and_main_node(ast)
    global_decl.init()

    trans_stmt_to_compound(global_decl, ast)
    # global_decl.print_all()
    call_func_in_main(global_decl, main_node)

    return ast, global_decl


def random_mutate_program(global_decl, ast):
    """
    @description: Randomly select a mutation operator and perform mutation at the AST level
    @param {*} global_decl
    @param {*} ast
    @return {*}
    """
    mutation_operator_label = ''
    while True:
        opts = ['insert-for', 'insert-if', 'insert-while', 'insert-assignment', 'insert-doWhile', 'insert-switch', 'insert-return',
                'prune-if', 'prune-for', 'prune-assignment', 'prune-compound', 'prune-return', 'replace-assignment']
        opt = random.choice(opts)
        opt = opt.split('-')
        if opt[0] == 'insert':
            insert_code_snippet_node(global_decl, ast, opt[1])
            mutation_operator_label = 'insert-{}-snippet'.format(opt[1])
            break
        elif opt[0] == 'prune':
            is_prune = prune_code_snippet_node(global_decl, ast, opt[1])
            mutation_operator_label = 'prune-{}-snippet'.format(opt[1])
            if is_prune:
                break
        else:
            replace_assignment_with_func(global_decl, ast)
            mutation_operator_label = 'replace-assignment-with-func'
            break
    return mutation_operator_label


def mutate_program_with_selected_mutator(global_decl, ast, selected_mutator):
    """
    @description: Using the selected mutation operator to mutate the program
    @param {*} global_decl
    @param {*} ast
    @param {*} selected_mutator
    @return {*}
    """
    opt = selected_mutator.split('-')
    if opt[0] == 'insert':
        insert_code_snippet_node(global_decl, ast, opt[1])
        mutation_operator_label = 'insert-{}-snippet'.format(opt[1])
    elif opt[0] == 'prune':
        is_prune = prune_code_snippet_node(global_decl, ast, opt[1])
        mutation_operator_label = 'prune-{}-snippet'.format(opt[1])
    else:
        replace_assignment_with_func(global_decl, ast)
        mutation_operator_label = 'replace-assignment-with-func'
    return mutation_operator_label


def mutate_program_csmith(test_dir, proc_num=-1, seed=-1, lock=None):
    # exec_cmd('csmith -s ' + str(seed) + ' -o test.c')
    # exec_cmd('csmith -o test.c')
    
    global program_file_path
    program_file_path.append(os.path.join(test_dir, 'test.c'))
    test_program = program_file_path[0]

    ast = parse_c_program_file(test_program)

    global_decl, main_node = get_global_decl_and_main_node(ast)
    global_decl.init()

    trans_stmt_to_compound(global_decl, ast)
    # global_decl.print_all()
    # call_func_in_main(global_decl, main_node)

    ################## mutation ##################
    mutation_operator_labels = ''
    mutate_num = random.choice([1, 2, 3, 4, 5])
    while mutate_num:
        opts = ['insert-for', 'insert-if', 'insert-while', 'insert-assignment', 'insert-doWhile', 'insert-switch', 'insert-return',
                'prune-if', 'prune-for', 'prune-assignment', 'prune-compound', 'prune-return', 'replace-assignment']
        opt = random.choice(opts)
        opt = opt.split('-')
        if opt[0] == 'insert':
            insert_code_snippet_node(global_decl, ast, opt[1])
            mutation_operator_label = 'insert-{}-snippet'.format(opt[1])
        elif opt[0] == 'prune':
            is_prune = prune_code_snippet_node(global_decl, ast, opt[1])
            if not is_prune:
                continue
            mutation_operator_label = 'prune-{}-snippet'.format(opt[1])
        else:
            replace_assignment_with_func(global_decl, ast)
            mutation_operator_label = 'replace-assignment-with-func'
        mutation_operator_labels += mutation_operator_label + ' -> '
        mutate_num -= 1
    mutation_operator_labels = mutation_operator_labels[:-4]
    ##############################################

    new_code = code_generator.visit(ast)
    lines = new_code.split('\n')
    lines = lines[726:]
    lines.insert(0, '#include "csmith.h"\n')
    new_code = '\n'.join(lines)
    with open(test_program, 'w') as f:
        f.write(new_code)

    is_free = check_program_by_all_sanitizers(
                    SANITIZER, program_file_path, 
                    test_dir, proc_num=proc_num, 
                    seed=seed, lock=lock,
                    mutation_operator_label=mutation_operator_labels)
    program_file_path.clear()
    return is_free, mutation_operator_labels


def mutate_program_csmith_for_test(test_dir, is_first=True, proc_num=-1, seed=-1, is_need_csmith_gen=False, lock=None):
    if is_need_csmith_gen:
        exec_cmd('csmith -s ' + str(seed) + ' -o test.c')
    # exec_cmd('csmith -o test.c')
    
    global program_file_path
    program_file_path.append(os.path.join(test_dir, 'test.c'))
    test_program = program_file_path[0]

    ast = parse_c_program_file(test_program)

    global_decl, main_node = get_global_decl_and_main_node(ast)
    global_decl.init()
    if is_first:
        trans_stmt_to_compound(global_decl, ast)
    # global_decl.print_all()
    # call_func_in_main(global_decl, main_node)

    ################## mutation ##################
    mutation_operator_labels = ''
    # mutate_num = random.choice([1, 2, 3, 4, 5])
    mutate_num = 1
    while mutate_num:
        opts = ['insert-for', 'insert-if', 'insert-while', 'insert-assignment', 'insert-doWhile', 'insert-switch', 'insert-return',
                'prune-if', 'prune-for', 'prune-assignment', 'prune-compound', 'prune-return', 'replace-assignment']
        opt = random.choice(opts)
        opt = opt.split('-')
        if opt[0] == 'insert':
            insert_code_snippet_node(global_decl, ast, opt[1])
            mutation_operator_label = 'insert-{}-snippet'.format(opt[1])
        elif opt[0] == 'prune':
            is_prune = prune_code_snippet_node(global_decl, ast, opt[1])
            if not is_prune:
                continue
            mutation_operator_label = 'prune-{}-snippet'.format(opt[1])
        else:
            replace_assignment_with_func(global_decl, ast)
            mutation_operator_label = 'replace-assignment-with-func'
        mutation_operator_labels += mutation_operator_label + ' -> '
        mutate_num -= 1
    mutation_operator_labels = mutation_operator_labels[:-4]
    ##############################################

    new_code = code_generator.visit(ast)
    lines = new_code.split('\n')
    lines = lines[726:]
    lines.insert(0, '#include "csmith.h"\n')
    new_code = '\n'.join(lines)
    with open(test_program, 'w') as f:
        f.write(new_code)

    is_free = check_program_by_all_sanitizers_with_one_single_threaded(
            SANITIZER, program_file_path, 
            test_dir, proc_num=proc_num, 
            seed=seed, lock=lock,
            mutation_operator_label=mutation_operator_label
    )
    program_file_path.clear()

    return is_free, mutation_operator_labels


def mutate_program_yarpgen(test_dir, proc_num=-1, seed=-1, lock=None):
    global program_file_path
    program_file_path.append(os.path.join(test_dir, 'init.h'))
    program_file_path.append(os.path.join(test_dir, 'func.c'))
    program_file_path.append(os.path.join(test_dir, 'driver.c'))

    modify_init_file_for_adapting_pycparser(program_file_path[0])
    modify_func_file_for_adapting_pycparser(program_file_path[1])
    modify_driver_file_for_adapting_tcc_compiler(program_file_path[2])

    ast = None
    for f in program_file_path:
        ast_file = parse_file(f, use_cpp=True, 
                    cpp_path=PARSER_FILE_CPP_PATH, 
                    cpp_args=['-E',
                              r'-I' + CSMITH_INCLUDE_DIR, 
                              r'-I' + PYCPARSER_INCLUDE_DIR])
        if ast is None:
            ast = ast_file
        else:
            ast.ext.extend(ast_file.ext)
    ast = ast.ext
    # extract all, global, local variables
    extract_variables(ast)

    # show all, global, local variables
    # print_variables()

    # mutation_operator_label = replace_stmt_with_func(ast)
  
    choices = ['insert', 'prune', 'replace']
    choice = random.choice(choices)
    if choice == 'insert':
        # print('>> insert')
        mutation_operator_label = insert(ast)
    elif choice == 'prune':
        # print('>> prune')
        mutation_operator_label = prune(ast)
    elif choice == 'replace':
        # print('>> replace')
        mutation_operator_label = replace(ast)
    
    # program_file_paths = ' '. join(program_file_path)
    is_free = check_program_by_all_sanitizers(
                    SANITIZER, program_file_path, 
                    test_dir, proc_num=proc_num, 
                    seed=seed, lock=lock,
                    mutation_operator_label=mutation_operator_label)
    program_file_path.clear()
    return is_free, mutation_operator_label


def all_files_path(target_dir, file_paths):
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.c'):
                file_paths.append(os.path.join(root, file))


def random_fuzzer_one2one(seed_programs_dir, target_programs_dir):
    if not os.path.exists(target_programs_dir):
        os.makedirs(target_programs_dir)

    seed_program_paths = []
    all_files_path(seed_programs_dir, seed_program_paths)
    
    seed_program_paths = sorted(seed_program_paths, key=lambda x: int(x.split('/')[-1].split('-')[2]))
    
    i = 0
    for seed_program in seed_program_paths:
        test_program = seed_program
        global program_file_path
        program_file_path.append(test_program)

        with open(test_program, 'r') as f:
            lines = f.readlines()
            seed = lines[6].split(':')[-1].strip()
        ast = parse_c_program_file(test_program)

        global_decl, main_node = get_global_decl_and_main_node(ast)
        global_decl.init()

        trans_stmt_to_compound(global_decl, ast)
        # global_decl.print_all()
        call_func_in_main(global_decl, main_node)

        ################## mutation ##################
        mutation_operator_labels = ''
        mutate_num = random.choice([1, 2, 3])
        while mutate_num:
            mutation_operator_label = random_mutate_program(global_decl, ast)
            mutation_operator_labels += mutation_operator_label + ' -> '
            mutate_num -= 1
        mutation_operator_labels = mutation_operator_labels[:-4]
        ##############################################

        new_code = code_generator.visit(ast)
        lines = new_code.split('\n')
        lines = lines[726:]
        lines.insert(0, '#include "csmith.h"\n')
        new_code = '\n'.join(lines)
        
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%d-%m-%y-%H:%M:%S")
        test_program = os.path.join(target_programs_dir, \
                                    'file-{}-{}-S_{}.c'.format(str(i), str(formatted_time), str(seed)))
        with open(test_program, 'w') as f:
            f.write(new_code)
        print(str(i) + 'th', test_program, '===============')
        print(mutation_operator_labels)
        program_file_path.clear()

        i += 1
        if i >= 100000:
            break


def save_csmith_program_file(target_file_path, csmith_program_ast, mutation_operator_labels='none'):
    with open(target_file_path, 'w') as f:
        new_code = code_generator.visit(csmith_program_ast)
        lines = new_code.split('\n')
        lines = lines[726:]
        lines.insert(0, '// ' + mutation_operator_labels + '\n')
        lines.insert(0, '#include "csmith.h"\n')
        new_code = '\n'.join(lines) 
        f.write(new_code)


def log_diversity_guidance_fuzzer_result(tmp_dir, hour_th, running_time, last_running_time, lasting_time, mutator_scheduler):
    with open(os.path.join(tmp_dir, 'res.log'), 'a+') as f:
        f.write(str(hour_th).ljust(2) + '-th ========================================================\n')
        f.write('>> this running time: ' + str(running_time) + '\n')
        f.write('>> last running time: ' + str(last_running_time) + '\n')
        f.write('>>>> lasting time: ' + str(lasting_time) + '\n')
        f.write('>>>> total_cnt   : ' + str(mutator_scheduler.total_cnt) + '\n')
        f.write('=================== mutator2cnt_and_reward ===================\n')
        for mutator, cnt_and_reward in mutator_scheduler.mutator2cnt_and_reward.items():
            f.write(f"{str(mutator).ljust(20)} -> {str(cnt_and_reward)}\n")
        f.write('==============================================================\n\n')


def random_fuzzer(seed_programs_dir, target_programs_dir, 
                  tmp_dir, mutate_num=7, is_need_check=True, 
                  lasting_time=20):
    """
    @description: Program randomly mutates multiple times and saves
    @param {*} seed_programs_dir
    @param {*} target_programs_dir
    @param {*} tmp_dir
    @param {*} mutate_num
    @param {*} is_need_check
    @param {*} lasting_time
    @return {*}
    """

    if not os.path.exists(target_programs_dir):
        os.makedirs(target_programs_dir)
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    os.chdir(tmp_dir)

    seed_program_paths = []
    all_files_path(seed_programs_dir, seed_program_paths)
    seed_program_paths = sorted(seed_program_paths, key=lambda x: int(x.split('/')[-1].split('-')[2]))

    start_time = datetime.datetime.now()
    cnt = 0
    last_running_time = 0
    next_log_time = 60 * 60
    while True:
        for test_program in seed_program_paths:
            global program_file_path
            program_file_path.append(test_program)

            with open(test_program, 'r') as f:
                lines = f.readlines()
                seed = lines[6].split(':')[-1].strip()
            ast = parse_c_program_file(test_program)
            global_decl, main_node = get_global_decl_and_main_node(ast)
            global_decl.init()
            trans_stmt_to_compound(global_decl, ast)

            mutation_operator_labels = ''
            for i in range(mutate_num):
                mutation_operator_label = random_mutate_program(global_decl, ast)
                if i == 0:
                    mutation_operator_labels += mutation_operator_label
                else:
                    mutation_operator_labels += ' -> ' + mutation_operator_label
                
                tmp_test_program_path = os.path.join(tmp_dir, 'test.c')
                save_csmith_program_file(tmp_test_program_path, ast, mutation_operator_labels)

                is_free = True
                if is_need_check:
                    for sanitizer in ['MSAN', 'ASAN', 'UBSAN']:
                        if not check_program_by_sanitizer_with_single_threaded(
                                SANITIZER, sanitizer, [tmp_test_program_path],
                                tmp_dir, -1, -1, None, local_timeout=10):
                            is_free = False
                            break

                current_time = datetime.datetime.now()
                running_time = (current_time - start_time).seconds

                if running_time > lasting_time or last_running_time > running_time:
                    print('>> time expired, running time:', running_time)
                    print('>> last running time:', last_running_time)              
                    return
                elif running_time >= next_log_time:
                    next_log_time += 60 * 60
                last_running_time = running_time


                if is_free:
                    formatted_time = current_time.strftime("%d%m%y-%H_%M_%S")
                    new_test_program_path = os.path.join(target_programs_dir, \
                                                'fuzzer-{}-{}-S_{}-{}.c'.format(
                                                    str(cnt), str(formatted_time), 
                                                    str(seed), str(i)))
                    cnt += 1
                    shutil.move(tmp_test_program_path, new_test_program_path)
                    print(running_time, '->', new_test_program_path, '->', mutation_operator_label)

                else:
                    break


def diversity_guidance_fuzzer(seed_programs_dir, target_programs_dir, 
                              tmp_dir, mutate_num=7, is_need_check=True, 
                              lasting_time=20):
    """
    @description: diversity guided program mutations
    @param {*} seed_programs_dir
    @param {*} target_programs_dir
    @param {*} tmp_dir
    @param {*} mutate_num
    @param {*} is_need_check
    @param {*} lasting_time
    @return {*}
    """
    if not os.path.exists(target_programs_dir):
        os.makedirs(target_programs_dir)
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    os.chdir(tmp_dir)

    global program_file_path
    tmp_test_program_path = os.path.join(tmp_dir, 'test.c')
    program_file_path.append(tmp_test_program_path)

    seed_program_paths = []
    log('diversity_guidance_fuzzer', 'Get all program files. Begin...')
    all_files_path(seed_programs_dir, seed_program_paths)
    log('diversity_guidance_fuzzer', 'Get all program files. End...')
    
    seed_program_paths = sorted(seed_program_paths, key=lambda x: int(x.split('/')[-1].split('-')[2]))

    start_time = datetime.datetime.now()
    cnt = 0
    last_running_time = 0
    next_log_time = 60 * 60
    mutator_scheduler = MutatorScheduler()
    while True:
        for test_program in seed_program_paths:
            with open(test_program, 'r') as f:
                lines = f.readlines()
                seed = lines[6].split(':')[-1].strip()
            ast = parse_c_program_file(test_program)
            global_decl, main_node = get_global_decl_and_main_node(ast)
            global_decl.init()
            trans_stmt_to_compound(global_decl, ast)

            mutation_operator_labels = ''
            save_csmith_program_file(tmp_test_program_path, ast, mutation_operator_labels)
            mutator_scheduler.clear_code_and_cfg()
            mutator_scheduler.add_code_and_cfg(program_file_path)
            for i in range(mutate_num):
                mutator = mutator_scheduler.get_mutator()
                mutation_operator_label = mutate_program_with_selected_mutator(global_decl, ast, mutator)

                if i == 0:
                    mutation_operator_labels += mutation_operator_label
                else:
                    mutation_operator_labels += ' -> ' + mutation_operator_label

                save_csmith_program_file(tmp_test_program_path, ast, mutation_operator_labels)
                print('1-mutation_operator_label:', mutation_operator_label)
                is_free = True
                if is_need_check:
                    for sanitizer in ['MSAN', 'ASAN', 'UBSAN']:
                        if not check_program_by_sanitizer_with_single_threaded(
                                SANITIZER, sanitizer, [tmp_test_program_path],
                                tmp_dir, -1, -1, None, local_timeout=10):
                            is_free = False
                            break
                print('2-is_free:', is_free)

                mutator_scheduler.calc_reward_2(mutator, is_free)

                current_time = datetime.datetime.now()
                running_time = (current_time - start_time).seconds

                if running_time > lasting_time or last_running_time > running_time:
                    print('>> time expired, running time:', running_time)
                    print('>> last running time:', last_running_time)
                    hour_th = int(next_log_time / 3600)
                    log_diversity_guidance_fuzzer_result(tmp_dir, hour_th, running_time, 
                                                         last_running_time, lasting_time, 
                                                         mutator_scheduler)                    
                    return
                elif running_time >= next_log_time:
                    hour_th = int(next_log_time / 3600)
                    log_diversity_guidance_fuzzer_result(tmp_dir, hour_th, running_time, 
                                                         last_running_time, lasting_time, 
                                                         mutator_scheduler)
                    next_log_time += 60 * 60
                last_running_time = running_time

                if is_free:
                    formatted_time = current_time.strftime("%d%m%y-%H_%M_%S")
                    new_test_program_path = os.path.join(target_programs_dir, \
                                                'fuzzer-{}-{}-S_{}-{}.c'.format(
                                                    str(cnt), str(formatted_time), 
                                                    str(seed), str(i)))
                    cnt += 1
                    shutil.move(tmp_test_program_path, new_test_program_path)
                    print(running_time, '->', new_test_program_path, '->', mutation_operator_label)

                else:
                    break       


def random_fuzzer_for_experiment():
    random_fuzzer('/media/workplace/experiment/generator/csmith', 
                  '/media/workplace/experiment/generator/my-mutator/exp-mutants-random-v1', 
                  '/media/workplace/experiment/generator/my-mutator/exp-tmp-random-v1', 
                  10, True, 86400)
    

def diversity_guidance_fuzzer_for_experiment():
    diversity_guidance_fuzzer('/media/workplace/experiment/generator/csmith', 
                              '/media/workplace/experiment/generator/my-mutator/exp-mutants-diversity-guidance-24h-rewardis2-num10-v1', 
                              '/media/workplace/experiment/generator/my-mutator/exp-tmp-diversity-guidance-24h-rewardis2-num10-v1', 
                              10, True, 60 * 60 * 24)


if __name__ == "__main__":
    # program_mutate_and_save('/home/workplace/dataset/experiment/csmith', '/home/workplace/dataset/experiment/csmith-mutate-1')
    # random_fuzzer_for_experiment()
    diversity_guidance_fuzzer_for_experiment()
    exit(0)

    # cnt = 0
    # os.chdir('./test')
    # for i in range(1000):
    #     print('=====================')
    #     seed = random.randint(0, 1000000000)
    #     # seed = '689949167'
    #     # seed = '328480304'
    #     # seed = '1180670756'
    #     print(i, '- seed:', seed)
    #     mutation_operator_label = mutate_program_csmith(test_dir='.', seed=seed)
    #     exit()
    #     print(mutation_operator_label)
    #     compile_program_cmd = ['clang-18', 'test.c', '-I/home/tools/csmith/include', '-w']
    #     ret_code, output, err_output, is_time_expired, elapsed_time = \
    #         run_command(compile_program_cmd, check_timeout, -1, compiler_mem_limit)
    #     if ret_code != 0:
    #         cnt += 1
    #         print('now error:', cnt)
    #         new_name = 'error-' + str(cnt) + '-S_' + str(seed) + '.c'
    #         with open('mutate_prune.log', 'a+') as f:
    #             f.write('seed: ' + str(seed) + '\n')
    #             f.write('mutate_label: ' + str(mutation_operator_label) + '\n')
    #             f.write('ret_code: ' + str(ret_code) + '\n')
    #             f.write('output: ' + output.decode() + '\n')
    #             f.write('err_output: ' + err_output.decode() + '\n')
    #             f.write('is_time_expired: ' + str(is_time_expired) + '\n')
    #             f.write('elapsed_time: ' + str(elapsed_time) + '\n')
    #             f.write(new_name + ' =====================\n')

    #         os.rename('test.c', new_name)
    # print(cnt)
    
    # mutate_program(test_dir='.', seed=30)
    i = 0
    os.chdir('test')
    while True:
        print(i)
        i += 1
        labels = mutate_program_csmith(test_dir='.', seed=2982817382)
        print(labels)
        compile_program_cmd = "icx -I/home/tools/csmith/include -std=c99 -fPIC -mcmodel=large -w -fopenmp-simd -mllvm -vec-threshold=0 -O3 -o icx_opt_o3_test.o -c test.c".split()
        print(compile_program_cmd)
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_command(compile_program_cmd, 10, -1, compiler_mem_limit)
        print(ret_code)
        print(err_output)
        if is_time_expired:
            print('nice!!!')
            break
        print('================')

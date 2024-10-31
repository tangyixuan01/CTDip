import os, sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))
from util.config import *
from util.mutate.mutate_config import *


def parse_c_program_file(program_file_path):
    """
    @description: Parse C program
    @param {*} program_file_path 
    @return {*}
    """
    return parse_file(program_file_path, use_cpp=True, 
                cpp_path=PARSER_FILE_CPP_PATH, 
                cpp_args=['-E',
                          r'-I' + CSMITH_INCLUDE_DIR, 
                          r'-I' + PYCPARSER_INCLUDE_DIR])


def transform_vari_name(vari_name):
    """
    @description: Variable name conversion, e.g., *vari[1][2] -> vari
    @param {*} vari_name: Original variable name
    @return {*} Simplified variable names
    """
    # *vari_name[1][2] => *vari_name
    vari_name = vari_name[:vari_name.find('[')] if '[' in vari_name else vari_name
    # **vari_name => vari_name
    vari_name = vari_name[vari_name.rfind('*') + 1:] if '*' in vari_name else vari_name
    return vari_name.strip()


def transform_type_decl(type_decl):
    """
    @description: Variable type conversion, e.g., const unsigned int [1][2][3] → uint or const long long int → long
    @param {*} type_decl 
    @return {*} Simplified variable types
    """
    # remove const、volatile、restrict、static、enum、signed
    type_decl = re.sub(r'\b(const|volatile|restrict|static|enum|signed)\b', '', type_decl)
    # Remove pointer
    type_decl = re.sub(r'\*', '', type_decl)
    # Remove array
    type_decl = re.sub(r'\[(.*?)\]', '', type_decl)
    type_decl = ' '.join(type_decl.strip().split())
    if type_decl in TYPE_DECL_2_SIMPLE_TYPE.keys():
        return TYPE_DECL_2_SIMPLE_TYPE[type_decl]
    elif type_decl.find('struct') or type_decl.find('union'):
        return type_decl
    else:
        # print('!!! transform_type_decl error:', type_decl)
        return None
    

def extract_dimensions_of_type_decl(type_decl):
    """
    @description: Extract array dimensions
        e.g.,： arr[10][12][13] Extract the numbers in parentheses and store them in a list
        exceptional case： arr[] or arr[N * 4] or arr[23 * 13] or arr[23 * 13 + 1] 
    @param {*} type_decl
    @return {*}
    """
    dimensions = [size for size in re.findall(r'\[(.*?)\]', type_decl)]
    for i in range(len(dimensions)):
        dimension = dimensions[i].strip()
        # Determine whether the string is empty or contains letters
        if dimension == '' or re.search(r'[a-zA-Z]', dimension):
            dimensions[i] = 1
        else:
            dimensions[i] = int(eval(dimension))
    return dimensions
    

def generate_random_variable_name():
    """
    @description: Randomly generate a variable name that includes English letters, numbers, and underscores, and cannot start with a number
    @return {*} New variable name
    """
    variable_name = ''
    chs = string.ascii_letters + string.digits + '_'
    while True:
        variable_name = ''.join(random.sample(chs, 8))
        if not variable_name[0].isdigit():
            break
    return variable_name


def generate_random_value(type_decl):
    """
    @description: Generate random values for variables
    @param {*} type_decl
    @return {*}
    """
    type_decl = transform_type_decl(type_decl)
    rnd_value = 0
    if type_decl in TYPE_2_RANGE.keys():
        choice = random.randint(0, 1)
        if choice == 0:
            # Return boundary value
            rnd_value = random.choice(TYPE_2_RANGE[type_decl])
        else:
            # Return random value
            rnd_value = random.randint(TYPE_2_RANGE[type_decl][0], TYPE_2_RANGE[type_decl][1])
    else:
        rnd_value = random.randint(0, 1)
    rnd_value = str(rnd_value)
    # bool insert (_Bool)，char insert (signed char)，uchar insert (unsigned char)，short insert (short)，
    # ushort insert (unsigned short)，int no change，uint insert U，long insert LL，ulong insert ULL
    if type_decl == 'bool':
        rnd_value = '(_Bool)' + rnd_value
    elif type_decl == 'char':
        rnd_value = '(signed char)' + rnd_value
    elif type_decl == 'uchar':
        rnd_value = '(unsigned char)' + rnd_value
    elif type_decl == 'short':
        rnd_value = '(short)' + rnd_value
    elif type_decl == 'ushort':
        rnd_value = '(unsigned short)' + rnd_value
    elif type_decl == 'uint':
        rnd_value += 'U'
    elif type_decl == 'long':
        rnd_value += 'LL'
    elif type_decl == 'ulong':
        rnd_value += 'ULL'
    return rnd_value


class FuncDeclInfo():
    def __init__(self, func_name, func_type, func_args):
        self.func_name = func_name      # name
        self.func_type = func_type      # func decl type
        self.func_args = func_args      # [type1, type2, ...]
    
    def __str__(self):
        return self.func_name + ' ' + self.func_type + ' ' + str(self.func_args)


class GlobalDecl():

    def __init__(self, type_decls, ptr_decls, array_decls, func_decls, struct_decls, union_decls):
        """
        @description: 
        @param {*} self
        @param {*} type_decls   name -> type
        @param {*} ptr_decls    name -> type
        @param {*} array_decls  name -> type
        @param {*} func_decls   name -> FuncDeclInfo 
        @param {*} struct_decls name -> (type, name, bitsize)
        @param {*} union_decls  name -> (type, name, bitsize)
        @return {*}
        """
        self.type_decls = type_decls            # name -> type
        self.ptr_decls = ptr_decls              # name -> type
        self.array_decls = array_decls          # name -> type
        self.func_decls = func_decls            # name -> FuncDeclInfo
        self.struct_decls = struct_decls        # name -> (type, name, bitsize)
        self.union_decls = union_decls          # name -> (type, name, bitsize)

        self.reverse_type_decls = {}            # type -> [name]
        self.reverse_array_decls = {}           # type -> [name]
        self.global_vari2type = {}              # name -> type

    def init(self):
        # 合并字典
        self.global_vari2type = {**self.type_decls, **self.ptr_decls, **self.array_decls}
        # 反转字典
        for name, type_decl in self.type_decls.items():
            # done: fix the bug of `cannot assign to variable 'xxx' with const-qualified type`
            if type_decl.find("*") == -1 and type_decl.find('const') == -1:
                simple_type = transform_type_decl(type_decl)
                if simple_type not in self.reverse_type_decls.keys():
                    self.reverse_type_decls[simple_type] = [name]
                else:
                    self.reverse_type_decls[simple_type].append(name)
    
    def print_dict(self, name, dict):
        print(name, '=====================')
        for key, value in dict.items():
            print(key, value)

    def print_all(self):
        self.print_dict('type_decls', self.type_decls)
        self.print_dict('array_decls', self.array_decls)
        self.print_dict('func_decls', self.func_decls)
        self.print_dict('struct_decls', self.struct_decls)
        self.print_dict('union_decls', self.union_decls)
        self.print_dict('reverse_type_decls', self.reverse_type_decls)
        self.print_dict('reverse_array_decls', self.reverse_array_decls)


def gen_type_decl_node(name, type_decl, value=None):
    """
    @description: Generate variable declaration
    @param {*} name 
    @param {*} type_decl 
    @param {*} value 
        if isinstance(value, list): -> struct or union
        else: -> normal
    @return {*}
    """
    if value is None:
        init_node = None
    else:
        if isinstance(value, list):
            init_value_node_list = []
            for init_value in value:
                init_value = str(init_value)
                # Determine if all are numbers
                if not init_value.isdigit():
                    init_value_node_list.append(c_ast.ID(name=init_value))
                else:
                    init_value_node_list.append(c_ast.Constant(type=None, value=init_value))
                init_node = c_ast.InitList(exprs=init_value_node_list)
        else:
            init_node = c_ast.ID(name=str(value))
    
    return c_ast.Decl(name=name,
                      quals=None,
                      align=None,
                      storage=None,
                      funcspec=None,
                      type=c_ast.TypeDecl(declname=name,
                                          quals=[],
                                          align=None,
                                          type=c_ast.IdentifierType(names=[type_decl])),
                      init=init_node,
                      bitsize=None)


def construct_normal_variable_init_stmt_node(ori_type, new_vari_name, value=None):
    """
    @description: Build a node for initializing a regular variable statement
    @param {*} ori_type 
    @param {*} new_vari_name
    @return {*} Normal variable declaration node
    """
    simple_type = transform_type_decl(ori_type)
    if value is None:
        init_value = generate_random_value(simple_type)
    else:
        init_value = value
    return gen_type_decl_node(new_vari_name, ori_type, value=init_value)


def construct_struct_or_union_variable_init_stmt_node(global_decl, ori_type, new_vari_name):
    """
    @description: Build struct or union variable initialization statement nodes
    @param {*} ori_type e.g.,： const struct S1
    @param {*} new_vari_name
    @return {*} struct or union
    """
    simple_type = transform_type_decl(ori_type)
    if simple_type.find('struct') != -1:
        # struct
        if simple_type not in global_decl.struct_decls.keys():
            return None
        decls = global_decl.struct_decls[simple_type]
    else:
        # union
        if simple_type not in global_decl.union_decls.keys():
            return None
        decls = global_decl.union_decls[simple_type]
    init_value_list = []
    for decl in decls:
        vari_type = decl[0]
        vari_type = transform_type_decl(vari_type)
        if vari_type in global_decl.reverse_type_decls.keys():
            init_value_list.append(random.choice(global_decl.reverse_type_decls[vari_type]))
        else:
            init_value_list.append(generate_random_value(vari_type))
        if simple_type.find('union') != -1:
            break
    return gen_type_decl_node(new_vari_name, ori_type, init_value_list)


def construct_pointer_variable_init_stmt_node(global_decl, stmts, type_decl, new_vari_name, is_need_normal=False):
    """
    @description: Constructing pointer variable initialization statement nodes
    @param {*} stmts :List of constructed statements stored
    @param {*} type_decl 
    @param {*} new_vari_name 
    @param {*} is_need_normal 
    @return {*}
    """
    if type_decl.find('*') == -1:
        if is_need_normal:
            normal_stmt = construct_normal_variable_init_stmt_node(
                type_decl, new_vari_name)
            stmts.append(normal_stmt)
        return

    if type_decl.count('*') == 1:
        simple_type = transform_type_decl(type_decl)
        if isinstance(global_decl, GlobalDecl) \
                and simple_type in global_decl.reverse_type_decls.keys():
            last_vari_name = random.choice(global_decl.reverse_type_decls[simple_type])
        else:
            is_need_normal = True
            last_vari_name = generate_random_variable_name()
    else:
        last_vari_name = generate_random_variable_name()

    new_decl = gen_type_decl_node(new_vari_name, type_decl, value='&' + last_vari_name)
    r_idx = type_decl.rfind('*')
    type_decl = type_decl[:r_idx]
    if stmts is not None:
        stmts.append(new_decl)
        construct_pointer_variable_init_stmt_node(global_decl, stmts, type_decl, last_vari_name, is_need_normal)


def construct_variable_init_stmt_node(global_decl, type_decl, used_variables=None):
    """
    @description: Construct initialization statement nodes for various types of variables
    @param {*} global_decl 
    @param {*} type_decl  -> str
    @param {*} used_variables  -> set
    @return {*} New variable name, initialization statement node list
    """
    new_vari_name = None
    init_stmts = []

    if type_decl.find('[') != -1:
        pass
        return None
    elif type_decl.find('*') != -1:
        new_vari_name = generate_random_variable_name()
        construct_pointer_variable_init_stmt_node(global_decl, init_stmts, type_decl, new_vari_name)
    else:
        simple_type = transform_type_decl(type_decl)
        new_vari_name = ''
        not_used_variables = set()
        if global_decl is not None and simple_type in global_decl.reverse_type_decls.keys():
            available_variables = set(global_decl.reverse_type_decls[simple_type])
            if used_variables is not None:
                not_used_variables = available_variables - used_variables
            else:
                not_used_variables = available_variables
        
        if len(not_used_variables) > 0:
            # Can be found in global_decl and has not been used
            new_vari_name = random.choice(list(not_used_variables))
        if simple_type.find('struct') == -1 and simple_type.find('union') == -1:
            # Cannot be found and is not of struct or union type
            new_vari_name = generate_random_variable_name()
            new_decl_stmt_node = construct_normal_variable_init_stmt_node(type_decl, new_vari_name)
            init_stmts.append(new_decl_stmt_node)
        else:
            # Cannot find, and it is of struct or union type
            new_vari_name = generate_random_variable_name()
            new_decl_stmt_node = construct_struct_or_union_variable_init_stmt_node(global_decl, type_decl, new_vari_name)
            if new_decl_stmt_node is None:
                return None
            init_stmts.append(new_decl_stmt_node)
    return new_vari_name, init_stmts


def construct_hash_formula(variable):
    """
    @description: construct hash
    @param {*} variable
    @return {*}
    """
    return c_ast.Assignment(op='^=',
                            lvalue=c_ast.ID(name='seed'),
                            rvalue=c_ast.BinaryOp(op='+', 
                                                  left=c_ast.BinaryOp(op='+',
                                                                      left=c_ast.BinaryOp(op='+',
                                                                                          left=c_ast.ID(name=variable),
                                                                                          right=c_ast.Constant(type='int',
                                                                                                            value='0x9e3779b9')
                                                                                         ),
                                                                      right=c_ast.BinaryOp(op='<<',
                                                                                           left=c_ast.ID(name='seed'),
                                                                                           right=c_ast.Constant(type='int',
                                                                                                                value='6')
                                                                                          )
                                                                     ),
                                                  right=c_ast.BinaryOp(op='>>',
                                                                       left=c_ast.ID(name='seed'),
                                                                       right=c_ast.Constant(type='int',
                                                                                            value='2'
                                                                                           )
                                                                       )
                                                 )
                            )


def construct_call_transparent_crc(variable):
    """
    @description: calling hash function
    @param {*} variable
    @return {*}
    """
    return \
    c_ast.FuncCall(name=c_ast.ID(name='transparent_crc'
                    ),
            args=c_ast.ExprList(exprs=[c_ast.ID(name=variable
                                    ),
                                c_ast.Constant(type='string',
                                        value='"' + variable + '"'
                                        ),
                                c_ast.Constant(type='int',
                                        value='0'
                                        )
                                ]
                        )
            )


def construct_init_for_stmt_node(idx_name, dimension):
    return c_ast.For(init=c_ast.DeclList(decls=[
                                            c_ast.Decl(
                                                name=idx_name, 
                                                quals=[], 
                                                align=[], 
                                                storage=[], 
                                                funcspec=[],
                                                type=c_ast.TypeDecl(declname=idx_name, quals=[], align=None, type=c_ast.IdentifierType(names=['int'])),
                                                init=c_ast.Constant(type='int', value='0'),
                                                bitsize=None)
                                        ]),
                     cond=c_ast.BinaryOp(op='<', left=c_ast.ID(name=idx_name), right=c_ast.Constant(type='int', value=str(dimension))),
                     next=c_ast.UnaryOp(op='p++', expr=c_ast.ID(name=idx_name)),
                     stmt=None)


def get_func_def_nodes(ast):
    """
    @description: Retrieve the function definition nodes in AST, excluding the main node and function nodes that are not in the programme_file path file
    @param {*} ast
    @return {*} Function Definition Nodes in AST
    """
    func_def_nodes = []
    simple_program_file_path = [path.split('/')[-1].strip() for path in program_file_path]
    for node in ast.ext:
        file_path = node.coord.file.split('/')[-1].strip()
        # Exclude the main node and function nodes that are not part of the programmable file path file
        if isinstance(node, c_ast.FuncDef) and \
                node.decl.name != 'main' and \
                file_path in simple_program_file_path:
            func_def_nodes.append(node)
    return func_def_nodes


def get_specify_nodes_by_recursion(root, node_type, res_nodes, file_paths=None):
    """
    @description: Retrieve all nodes of a specified type through recursion
    @param {*} root ast
    @param {*} node_type 
    @param {*} res_nodes 
    @param {*} file_paths Used to determine whether the extracted node is in this directory, e.g.,: ['test.c', 'csmith.h', ...]
    """
    for child in root:
        if isinstance(child, node_type):
            if file_paths is None or\
                    (child.coord is not None and\
                    child.coord.file.split('/')[-1].strip() in file_paths):
                res_nodes.append(child)
        get_specify_nodes_by_recursion(child, node_type, res_nodes, file_paths)


def get_specify_nodes_from_func(func_def_nodes, ast_type):
    """
    @description: Retrieve a specific type of node from a function
    @param {*} func_def_nodes 
    @param {*} ast_type 
    @return {*} Return the target node list
    """
    target_nodes = []
    for func_def in func_def_nodes:
        get_specify_nodes_by_recursion(func_def, ast_type, target_nodes)
    return target_nodes


def get_local_decl_from_func(func_node):
    """
    @description: Retrieve variable declaration information within the function
    @param {*} func_node
    @return {*} variable name => variable type
    """
    decl_nodes = []
    get_specify_nodes_by_recursion(func_node, c_ast.Decl, decl_nodes)
    local_vari2type = {}
    for decl_node in decl_nodes:
        vari_name = decl_node.name
        vari_type = code_generator.visit(decl_node.type)
        local_vari2type[vari_name] = vari_type
    return local_vari2type


def get_specify_nodes_pos_from_compound_nodes(compound_nodes, ast_type, file_paths=None):
    """
    @description: Retrieve location information of specific types of nodes from code blocks
    @param {*} compound_nodes
    @param {*} ast_type
    @param {*} file_paths
    @return {*} 
        return: Location information of specific types of nodes
                specify_node_pos = [(compound_nodes1, idx1), (compound_nodes1, idx2), ...]
                Each item in the result is (specific code block node, index value)
    """
    specify_node_pos = []
    for compound_node in compound_nodes:
        nodes = compound_node.block_items
        if not isinstance(nodes, list):
            continue
        for i in range(len(nodes)):
            node = nodes[i]
            if isinstance(node, ast_type):
                if file_paths is None or\
                        (node.coord is not None and\
                         node.coord.file.split('/')[-1].strip() in file_paths):
                    specify_node_pos.append((compound_node, i))
    return specify_node_pos


def get_label2node_pos_from_compound_nodes(compound_nodes, file_paths=None):
    """
    @description: Retrieve node location information containing labels from code blocks
    @param {*} compound_nodes
    @param {*} file_paths
    @return {*} 
        return: Node location information including label
                label2node = {label_name1: [(compound_nodes1, idx1), (compound_nodes1, idx2), ...],
                              label_name2: [(compound_nodes2, idx3), (compound_nodes2, idx4), ...]}
                i.e., Save Goto statements and Label statements with the same label value in the same key value
    """
    label2node_pos = {}
    for compound_node in compound_nodes:
        nodes = compound_node.block_items
        if not isinstance(nodes, list):
            continue
        for i in range(len(nodes)):
            node = nodes[i]
            if isinstance(node, c_ast.Goto) or isinstance(node, c_ast.Label):
                if file_paths is None or\
                        (node.coord is not None and\
                         node.coord.file.split('/')[-1].strip() in file_paths):
                    label_name = node.name
                    if label_name not in label2node_pos.keys():
                        label2node_pos[label_name] = [(compound_node, i)]
                    else:
                        label2node_pos[label_name].append((compound_node, i))
    return label2node_pos


def extract_all_fields(global_decl, ori_name, type_decl, fields_res):
    """
    @description: Extract all fields from struct or union
    @param {*} global_decl
    @param {*} ori_name      
    @param {*} type_decl
    @param {*} fields_res
    e.g.,：
    struct S0
    {
        int f0 : 0;
        long f1;
    }
    union U0
    {
        struct S0 f0;
        int f1;
    }
    variable： union U0 var = {{1, 2}};
    use this variable： extruct_all_fileds(global_decl, 'var', 'union U0', fields_res)
    fields_res is: ['var.f0.f0', 'var.f0.f1']
    """
    simple_type = transform_type_decl(type_decl)
    if simple_type.find('union') != -1:
        fields = global_decl.union_decls[simple_type]
        new_name = ori_name + '.' + fields[0][1]
        field_type = fields[0][0]
        if field_type.find('struct') != -1 or field_type.find('union') != -1:
            extract_all_fields(global_decl, new_name, field_type, fields_res)
        else:
            fields_res.append(new_name)
        return
    elif simple_type.find('struct') != -1:
        fields = global_decl.struct_decls[simple_type]
        for field in fields:
            new_name = ori_name + '.' + field[1]
            field_type = field[0]
            if field_type.find('struct') != -1 or field_type.find('union') != -1:
                extract_all_fields(global_decl, new_name, field_type, fields_res)
            else:
                fields_res.append(new_name)


if __name__ == "__main__":
    stmts = []
    construct_pointer_variable_init_stmt_node('', stmts, 'int ***', 'a')
    for stmt in stmts:
        print(code_generator.visit(stmt))

#!/usr/bin/env python

import os
import re
import sys
import copy
import shutil
import string
import random
import datetime
from pycparser import parse_file, c_generator, c_ast, c_parser, plyparser
from pycparser.c_ast import NodeVisitor

code_generator = c_generator.CGenerator()

# docker paths
# CSMITH_INCLUDE_DIR = '/home/git-workplace/csmith/include'
# PYCPARSER_INCLUDE_DIR = '/home/workplace/emi_mutation_acc/pycparser/utils/fake_libc_include'
# PARSER_FILE_CPP_PATH = '/home/compilers/gcc/gcc-13.1.0/bin/gcc'
# SANITIZER = '/home/compilers/llvm/llvm-16.0.0/bin/clang'
# CODE_SNIPPETS_DIR = '/home/workplace/emi_mutation_acc/code_snippets'

# ubuntu paths
CSMITH_INCLUDE_DIR = '/home/tools/csmith/include'
PYCPARSER_INCLUDE_DIR = '/home/git-workplace/pycparser/utils/fake_libc_include'
PARSER_FILE_CPP_PATH = '/home/compilers/gcc/gcc-13.1.0/bin/gcc'
SANITIZER = '/home/compilers/llvm/llvm-16.0.0/bin/clang'
# SANITIZER = '/home/compilers/gcc/gcc-13.1.0/bin/gcc'
CODE_SNIPPETS_DIR = '/home/workplace/dataset/code_snippets/code_snippets_csmith'
CFG_COMPILER = '/home/compilers/gcc/gcc-13.1.0/bin/gcc'

# variable → type
all_variable2type = {}
# variable → type
local_variable2type = {}
# variable → type
global_variable2type = {}

# yarpgen files: init.h, func.c, driver.c
# csmith file: test.c
program_file_path = []

KNOWN_BUILD_FAILS = { \
# clang
    "Assertion `NodeToMatch\-\>getOpcode\(\) != ISD::DELETED_NODE && \"NodeToMatch was removed partway through selection\"'": "SelectionDAGISel", \
    "replaceAllUses of value with new value of different type": "replaceAllUses", \
    "Concatenation of vectors with inconsistent value types": "FoldCONCAT_VECTORS", \
    "Integer type overpromoted": "PromoteIntRes_SETCC", \
    "Cannot select.*urem": "Cannot_select_urem", \
    "Cannot select.*X86ISD::PCMPEQ": "Cannot_select_pcmpeq", \
    "Binary operator types must match": "Binary_operator_types_must_match", \
    "Deleted Node added to Worklist": "DAGCombiner_AddToWorklist", \
    "Invalid child # of SDNode": "SDNode_getOperand", \
    "DELETED_NODE in CSEMap!": "DELETED_NODE_CSEMap", \
    "The number of nodes scheduled doesn't match the expected number": "VerifyScheduledSequence", \
    "Cannot emit physreg copy instruction": "physreg_copy", \
    "Deleted edge still exists in the CFG": "deleted_cfg_edge", \
    "Cannot convert from scalar to/from vector": "vec_convert", \
    "Invalid constantexpr cast!": "constexpr_cast", \
# gcc
    "compute_live_loop_exits": "compute_live_loop_exits", \
    "ubsan_instrument_division": "ubsan_instrument_division", \
    "non-trivial conversion at assignment": "verify_gimple_assignment", \
    "type mismatch in shift expression": "verify_gimple_shift", \
    "type mismatch in binary expression": "verify_gimple_binary", \
    "REG_BR_PROB does not match": "REG_BR_PROB", \
    "in build_low_bits_mask": "build_low_bits_mask", \
    "non-trivial conversion in unary operation": "verify_gimple_conversion_in_unary", \
    "conversion of register to a different size": "verify_gimple_register_size", \
    "in decompose": "decompose", \
    "mismatching comparison operand types": "verify_gimple_unary_conversion", \
    "qsort checking failed": "qsort", \
    "in immed_wide_int_const, at emit-rtl.c": "immed_wide_int_const", \
    "during RTL pass: cprop": "cprop", \
    "may be used uninitialized in this function": "may_be_uninit", \
    "hoist_memory_references": "hoist_memory_references", \
    "verify_gimple_in_cfg": "verify_gimple_in_cfg", \
    "crash_signal": "crash_signal", \
    "maybe_canonicalize_mem_ref_addr": "maybe_canonicalize_mem_ref_addr",\
# problem with available memory
    "bad_alloc": "memory_problem", \
    "out of memory": "memory_problem", \
    "Out of memory": "memory_problem", \
    "Cannot allocate memory": "memory_problem", \
    "Killed": "killed", \
    "relocation truncated to fit": "inp_alloc_problem", \
}
